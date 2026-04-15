from __future__ import annotations

import os
from typing import Any

from anthropic import Anthropic
from fastapi import status

from app.core.errors import ProviderServiceError
from app.services.providers.base import LlmProvider, ProviderResponse, provider_timeout


def _content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                # OpenAI-style content blocks (rare in this codebase, but tolerate it).
                if item.get("type") == "text" and isinstance(item.get("text"), str):
                    parts.append(item["text"])
            else:
                text = getattr(item, "text", None)
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join([p for p in parts if p])
    text = getattr(content, "text", None)
    if isinstance(text, str):
        return text
    return str(content)


def _response_raw_dict(resp: Any) -> dict:
    # Anthropic SDK returns a model-like object; prefer a plain dict for audit/debug storage.
    for attr in ("model_dump", "dict", "to_dict"):
        fn = getattr(resp, attr, None)
        if callable(fn):
            try:
                data = fn()
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
    return {"repr": repr(resp)}


class AnthropicProvider(LlmProvider):
    name = "anthropic"

    def chat_completions(
        self,
        *,
        model: str,
        messages: list[dict],
        max_tokens: int | None,
        temperature: float | None,
        runtime_config: dict | None = None,
    ) -> ProviderResponse:
        runtime_config = runtime_config or {}
        api_key = str(runtime_config.get("api_key") or os.getenv("ANTHROPIC_API_KEY") or "").strip()
        base_url = str(runtime_config.get("base_url") or "").strip()
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not configured")

        system_parts: list[str] = []
        anthropic_messages: list[dict] = []
        for msg in messages:
            role = (msg.get("role") or "").lower()
            text = _content_to_text(msg.get("content"))
            if role == "system":
                if text:
                    system_parts.append(text)
                continue
            if role not in ("user", "assistant"):
                # Ignore tool/unknown roles for now; gateway currently uses user/assistant/system only.
                continue
            anthropic_messages.append({"role": role, "content": text})

        req: dict[str, Any] = {
            "model": model,
            "messages": anthropic_messages,
            "max_tokens": max_tokens if max_tokens is not None else 1024,
        }
        if temperature is not None:
            req["temperature"] = temperature
        if system_parts:
            req["system"] = "\n\n".join(system_parts)

        client_kwargs: dict[str, Any] = {"api_key": api_key, "timeout": provider_timeout(runtime_config)}
        if base_url:
            client_kwargs["base_url"] = base_url
        try:
            client = Anthropic(**client_kwargs)
            resp = client.messages.create(**req)
        except Exception as exc:
            exc_name = exc.__class__.__name__
            lowered = exc_name.lower()
            if "timeout" in lowered:
                raise ProviderServiceError(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    code="PROVIDER_TIMEOUT",
                    detail="Anthropic request timed out",
                    retryable=True,
                    error_class="timeout",
                ) from exc
            if "authentication" in lowered or "permission" in lowered:
                raise ProviderServiceError(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    code="PROVIDER_UNAVAILABLE",
                    detail="Anthropic authentication failed",
                    retryable=False,
                    error_class="auth",
                ) from exc
            retryable = "connection" in lowered or "rate" in lowered or "apierror" in lowered or "server" in lowered
            error_class = "connection" if "connection" in lowered else "rate_limit" if "rate" in lowered else "server_error" if ("apierror" in lowered or "server" in lowered) else None
            raise ProviderServiceError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="PROVIDER_UNAVAILABLE",
                detail="Anthropic request failed",
                retryable=retryable,
                error_class=error_class,
            ) from exc

        content = ""
        blocks = getattr(resp, "content", None) or []
        if blocks:
            first = blocks[0]
            content = getattr(first, "text", None) or (first.get("text") if isinstance(first, dict) else "")
        usage = getattr(resp, "usage", None)
        prompt_tokens = None
        completion_tokens = None
        if usage is not None:
            # Anthropic Messages API reports token usage as input/output tokens.
            prompt_tokens = getattr(usage, "input_tokens", None) or getattr(usage, "prompt_tokens", None)
            completion_tokens = getattr(usage, "output_tokens", None) or getattr(usage, "completion_tokens", None)

        return ProviderResponse(
            content=content or "",
            raw=_response_raw_dict(resp),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
