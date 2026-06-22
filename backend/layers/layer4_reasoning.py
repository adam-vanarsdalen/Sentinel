"""Layer 4: Reasoning — LLM execution with tool-call interception loop."""
from __future__ import annotations

import time
from typing import Any

import httpx

from config import settings
from schemas.proxy import (
    EnforcementCheck,
    ModelResponse,
    PipelineError,
    PipelineRequest,
    RoutingDecision,
)

MAX_TOOL_ROUNDS = 20


async def _call_anthropic(
    messages: list[dict],
    tools: list[dict] | None,
    model: str,
    client: httpx.AsyncClient,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": 4096,
        "messages": messages,
    }
    if tools:
        payload["tools"] = tools

    resp = await client.post(
        "https://api.anthropic.com/v1/messages",
        json=payload,
        headers={
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
        },
        timeout=60.0,
    )
    resp.raise_for_status()
    return resp.json()


async def _call_openai(
    messages: list[dict],
    tools: list[dict] | None,
    model: str,
    client: httpx.AsyncClient,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"model": model, "messages": messages}
    if tools:
        payload["tools"] = tools

    resp = await client.post(
        "https://api.openai.com/v1/chat/completions",
        json=payload,
        headers={"Authorization": f"Bearer {settings.openai_api_key}"},
        timeout=60.0,
    )
    resp.raise_for_status()
    return resp.json()


def _parse_response(raw: dict, provider: str, model: str, latency_ms: int) -> ModelResponse:
    if provider == "anthropic":
        content_blocks = raw.get("content", [])
        text = " ".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")
        tool_calls = [b for b in content_blocks if b.get("type") == "tool_use"]
        usage = raw.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        finish_reason = raw.get("stop_reason", "end_turn")
    else:
        choice = raw.get("choices", [{}])[0]
        msg = choice.get("message", {})
        text = msg.get("content", "") or ""
        tool_calls = msg.get("tool_calls") or []
        usage = raw.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        finish_reason = choice.get("finish_reason", "stop")

    cost = (input_tokens * 0.000001 + output_tokens * 0.000003)

    return ModelResponse(
        content=text,
        tool_calls=tool_calls if tool_calls else None,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
        latency_ms=latency_ms,
        provider=provider,
        model=model,
        finish_reason=finish_reason,
    )


async def layer4_reason(
    req: PipelineRequest,
    routing: RoutingDecision,
    enforce_fn: Any = None,  # callable: (tool_call) -> EnforcementCheck
    client: httpx.AsyncClient | None = None,
) -> ModelResponse:
    """Execute LLM call with tool-call interception loop."""
    provider = routing.target_provider
    model = routing.target_model
    messages = list(req.messages)
    tools = req.tools

    _client = client or httpx.AsyncClient()
    total_input = 0
    total_output = 0
    total_cost = 0.0
    start = time.monotonic()

    try:
        for _round in range(MAX_TOOL_ROUNDS):
            round_start = time.monotonic()
            try:
                if provider == "anthropic":
                    raw = await _call_anthropic(messages, tools, model, _client)
                elif provider == "openai":
                    raw = await _call_openai(messages, tools, model, _client)
                else:
                    raise PipelineError(4, "unsupported_provider", f"Provider '{provider}' not supported")
            except httpx.TimeoutException as e:
                raise PipelineError(4, "provider_timeout", str(e)) from e
            except httpx.HTTPStatusError as e:
                raise PipelineError(4, "provider_error", f"{e.response.status_code}: {e.response.text}") from e

            latency_ms = int((time.monotonic() - round_start) * 1000)
            parsed = _parse_response(raw, provider, model, latency_ms)
            total_input += parsed.input_tokens
            total_output += parsed.output_tokens
            total_cost += parsed.cost_usd

            # Tool-call interception loop
            if parsed.tool_calls and enforce_fn:
                tool_results = []
                for tc in parsed.tool_calls:
                    enforcement: EnforcementCheck = await enforce_fn(tc)
                    if not enforcement.allowed:
                        # Return denial message to model; blocked call never executes
                        tool_results.append({
                            "role": "tool",
                            "tool_use_id": tc.get("id", ""),
                            "content": f"Tool call denied by policy: {enforcement.blocked_reason}",
                        })
                    else:
                        tool_results.append({
                            "role": "tool",
                            "tool_use_id": tc.get("id", ""),
                            "content": "[tool executed]",
                        })

                messages.append({"role": "assistant", "content": parsed.content, "tool_calls": parsed.tool_calls})
                messages.extend(tool_results)
                continue  # re-enter loop with tool results

            # Final response — no more tool calls
            total_latency = int((time.monotonic() - start) * 1000)
            return ModelResponse(
                content=parsed.content,
                tool_calls=parsed.tool_calls,
                input_tokens=total_input,
                output_tokens=total_output,
                cost_usd=total_cost,
                latency_ms=total_latency,
                provider=provider,
                model=model,
                finish_reason=parsed.finish_reason,
            )

        raise PipelineError(4, "max_tool_rounds", f"Exceeded {MAX_TOOL_ROUNDS} tool-call rounds")
    finally:
        if not client:
            await _client.aclose()
