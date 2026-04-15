from __future__ import annotations

from typing import Any

import httpx
from fastapi import status
from openai import APIConnectionError, APIStatusError, APITimeoutError, AuthenticationError, OpenAI, RateLimitError

from app.core.config import settings
from app.core.errors import ProviderServiceError
from app.services.providers.base import LlmProvider, ProviderResponse, provider_timeout


def _native_base_url(openai_base_url: str) -> str:
    base = str(openai_base_url or "").strip().rstrip("/")
    if not base:
        return "http://localhost:11434"
    if base.endswith("/v1"):
        return base[: -len("/v1")]
    return base


class OllamaProvider(LlmProvider):
    name = "ollama"

    def _effective_api_key(self, runtime_config: dict[str, Any]) -> str:
        api_key = str(runtime_config.get("api_key") or settings.ollama_api_key or "").strip()
        # Ollama's local OpenAI-compatible API typically ignores auth but some SDKs require a key.
        return api_key or "ollama-placeholder"

    def _effective_base_url(self, runtime_config: dict[str, Any]) -> str:
        return str(runtime_config.get("base_url") or settings.ollama_base_url or "http://localhost:11434/v1/").strip().rstrip("/")

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
        payload: dict[str, Any] = {"model": model, "messages": messages}
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if temperature is not None:
            payload["temperature"] = temperature

        try:
            client = OpenAI(
                api_key=self._effective_api_key(runtime_config),
                base_url=self._effective_base_url(runtime_config),
                timeout=provider_timeout(runtime_config),
                max_retries=0,
            )
            resp = client.chat.completions.create(**payload)
            data = resp.model_dump(mode="json")
        except APITimeoutError as exc:
            raise ProviderServiceError(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                code="PROVIDER_TIMEOUT",
                detail="Ollama request timed out",
                retryable=True,
                error_class="timeout",
            ) from exc
        except AuthenticationError as exc:
            raise ProviderServiceError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="PROVIDER_UNAVAILABLE",
                detail="Ollama authentication failed",
                retryable=False,
                provider_status_code=exc.status_code,
                error_class="auth",
            ) from exc
        except RateLimitError as exc:
            raise ProviderServiceError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="PROVIDER_UNAVAILABLE",
                detail="Ollama rate limited the request",
                retryable=True,
                provider_status_code=exc.status_code,
                error_class="rate_limit",
            ) from exc
        except APIStatusError as exc:
            provider_status = exc.status_code
            retryable = provider_status >= 500 or provider_status in {408, 409, 425, 429}
            error_class = "server_error" if provider_status >= 500 else "http_status"
            raise ProviderServiceError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="PROVIDER_UNAVAILABLE",
                detail=f"Ollama request failed with status {provider_status}",
                retryable=retryable,
                provider_status_code=provider_status,
                error_class=error_class,
            ) from exc
        except APIConnectionError as exc:
            raise ProviderServiceError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="PROVIDER_UNAVAILABLE",
                detail="Unable to reach Ollama host",
                retryable=True,
                error_class="connection",
            ) from exc

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}
        return ProviderResponse(
            content=content,
            raw=data,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
        )

    def list_models(self, *, runtime_config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        runtime_config = runtime_config or {}
        native_base = _native_base_url(self._effective_base_url(runtime_config))
        try:
            response = httpx.get(
                f"{native_base}/api/tags",
                timeout=provider_timeout(runtime_config),
                headers={"Authorization": f"Bearer {self._effective_api_key(runtime_config)}"},
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ProviderServiceError(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                code="PROVIDER_TIMEOUT",
                detail="Ollama model discovery timed out",
                retryable=True,
                error_class="timeout",
            ) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            raise ProviderServiceError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="PROVIDER_UNAVAILABLE",
                detail=f"Ollama model discovery failed with status {status_code}",
                retryable=status_code >= 500,
                provider_status_code=status_code,
                error_class="http_status",
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderServiceError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="PROVIDER_UNAVAILABLE",
                detail="Unable to reach Ollama for model discovery",
                retryable=True,
                error_class="connection",
            ) from exc

        body = response.json() if response.content else {}
        models: list[dict[str, Any]] = []
        for item in body.get("models") or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            details = item.get("details") if isinstance(item.get("details"), dict) else {}
            models.append(
                {
                    "id": name,
                    "digest": item.get("digest"),
                    "parameter_size": details.get("parameter_size"),
                    "family": details.get("family"),
                    "families": details.get("families") if isinstance(details.get("families"), list) else [],
                }
            )
        return models

    def show_model(self, *, model: str, runtime_config: dict[str, Any] | None = None) -> dict[str, Any]:
        runtime_config = runtime_config or {}
        native_base = _native_base_url(self._effective_base_url(runtime_config))
        try:
            response = httpx.post(
                f"{native_base}/api/show",
                json={"model": model},
                timeout=provider_timeout(runtime_config),
                headers={"Authorization": f"Bearer {self._effective_api_key(runtime_config)}"},
            )
            response.raise_for_status()
            return response.json() if response.content else {}
        except Exception as exc:
            raise ProviderServiceError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="PROVIDER_UNAVAILABLE",
                detail="Ollama model detail lookup failed",
                retryable=True,
                error_class="connection",
            ) from exc

