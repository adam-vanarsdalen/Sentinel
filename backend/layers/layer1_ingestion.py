"""Layer 1: Ingestion — normalize inputs, tag provenance, validate schema."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import tiktoken

from schemas.proxy import PipelineError, PipelineRequest

_tokenizer = tiktoken.get_encoding("cl100k_base")


def _estimate_tokens(messages: list[dict]) -> int:
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += len(_tokenizer.encode(content))
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    total += len(_tokenizer.encode(block.get("text", "")))
    return total


def _normalize_anthropic(raw: dict) -> list[dict]:
    """Convert Anthropic /v1/messages format to OpenAI-compatible messages."""
    messages = []
    system = raw.get("system")
    if system:
        messages.append({"role": "system", "content": system})
    for msg in raw.get("messages", []):
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, list):
            text_parts = [b.get("text", "") for b in content if b.get("type") == "text"]
            content = " ".join(text_parts)
        messages.append({"role": role, "content": content})
    return messages


def _normalize_openai(raw: dict) -> list[dict]:
    return raw.get("messages", [])


def _detect_format(raw: dict) -> str:
    if "model" in raw and "messages" in raw and "max_tokens" in raw:
        if "anthropic" in raw.get("model", "").lower() or "claude" in raw.get("model", "").lower():
            return "anthropic"
    return "openai"


async def layer1_ingest(raw: dict[str, Any], source: str, tenant_id: str) -> PipelineRequest:
    """Normalize any incoming request to PipelineRequest."""
    start = time.monotonic()

    if not raw:
        raise PipelineError(1, "validation_error", "Empty request body")
    if not isinstance(raw.get("messages", []), list):
        raise PipelineError(1, "validation_error", "messages must be a list")

    fmt = _detect_format(raw)
    try:
        messages = _normalize_anthropic(raw) if fmt == "anthropic" else _normalize_openai(raw)
    except Exception as e:
        raise PipelineError(1, "normalization_error", str(e)) from e

    if not messages:
        raise PipelineError(1, "validation_error", "Request contains no messages")

    tools = raw.get("tools")
    tool_choice = raw.get("tool_choice")
    model_requested = raw.get("model")

    provenance_tags: dict[str, Any] = {
        "format": fmt,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_ingestion_ms": int((time.monotonic() - start) * 1000),
    }

    raw_headers: dict[str, str] = {
        k: v for k, v in raw.get("_headers", {}).items() if isinstance(v, str)
    }

    input_tokens_estimate = _estimate_tokens(messages)

    # agent_id can come from the request body or from X-Agent-ID header
    agent_id: str | None = raw.get("agent_id") or raw_headers.get("x-agent-id")

    return PipelineRequest(
        timestamp=datetime.now(timezone.utc),
        tenant_id=tenant_id,
        agent_id=agent_id,
        source=source,
        messages=messages,
        tools=tools,
        tool_choice=tool_choice,
        model_requested=model_requested,
        input_tokens_estimate=input_tokens_estimate,
        provenance_tags=provenance_tags,
        raw_headers=raw_headers,
    )
