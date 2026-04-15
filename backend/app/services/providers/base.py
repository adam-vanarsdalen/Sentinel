from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class ProviderResponse:
    content: str
    raw: dict
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


DEFAULT_CONNECT_TIMEOUT_SECONDS = 5.0
DEFAULT_READ_TIMEOUT_SECONDS = 60.0
DEFAULT_RETRY_COUNT = 0
DEFAULT_RETRYABLE_STATUS_CODES = [408, 409, 425, 429, 500, 502, 503, 504]
DEFAULT_RETRYABLE_ERROR_CLASSES = ["timeout", "connection", "rate_limit", "server_error"]


def provider_timeout(runtime_config: dict | None = None) -> httpx.Timeout:
    runtime_config = runtime_config or {}
    resilience = runtime_config.get("resilience") if isinstance(runtime_config.get("resilience"), dict) else {}
    connect = float(resilience.get("connect_timeout_seconds") or DEFAULT_CONNECT_TIMEOUT_SECONDS)
    read = float(resilience.get("read_timeout_seconds") or DEFAULT_READ_TIMEOUT_SECONDS)
    return httpx.Timeout(connect=connect, read=read, write=read, pool=connect)


class LlmProvider:
    name: str

    def chat_completions(
        self,
        *,
        model: str,
        messages: list[dict],
        max_tokens: int | None,
        temperature: float | None,
        runtime_config: dict | None = None,
    ) -> ProviderResponse:
        raise NotImplementedError
