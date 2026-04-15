from __future__ import annotations

import hashlib

from app.services.providers.base import LlmProvider, ProviderResponse


class MockProvider(LlmProvider):
    name = "mock"

    def chat_completions(
        self,
        *,
        model: str,
        messages: list[dict],
        max_tokens: int | None,
        temperature: float | None,
        runtime_config: dict | None = None,
    ) -> ProviderResponse:
        joined = "\n".join([f"{m.get('role')}: {m.get('content')}" for m in messages])
        digest = hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]
        content = f"[mock:{model}] {digest}"
        return ProviderResponse(content=content, raw={"provider": "mock", "digest": digest})
