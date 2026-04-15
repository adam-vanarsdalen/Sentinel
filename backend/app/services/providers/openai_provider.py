from __future__ import annotations

from fastapi import status
from openai import APIConnectionError, APIStatusError, APITimeoutError, AuthenticationError, OpenAI, RateLimitError

from app.core.config import settings
from app.core.errors import ProviderServiceError
from app.services.providers.base import LlmProvider, ProviderResponse, provider_timeout


class OpenAiProvider(LlmProvider):
    name = "openai"

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
        api_key = (runtime_config.get("api_key") or settings.openai_api_key or "").strip()
        base_url = (runtime_config.get("base_url") or settings.openai_base_url).rstrip("/")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not configured")
        payload = {"model": model, "messages": messages}
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if temperature is not None:
            payload["temperature"] = temperature

        try:
            client = OpenAI(api_key=api_key, base_url=base_url, timeout=provider_timeout(runtime_config), max_retries=0)
            resp = client.chat.completions.create(**payload)
            data = resp.model_dump(mode="json")
        except APITimeoutError as exc:
            raise ProviderServiceError(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                code="PROVIDER_TIMEOUT",
                detail="OpenAI request timed out",
                retryable=True,
                error_class="timeout",
            ) from exc
        except AuthenticationError as exc:
            raise ProviderServiceError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="PROVIDER_UNAVAILABLE",
                detail="OpenAI authentication failed",
                retryable=False,
                provider_status_code=exc.status_code,
                error_class="auth",
            ) from exc
        except RateLimitError as exc:
            raise ProviderServiceError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="PROVIDER_UNAVAILABLE",
                detail="OpenAI rate limited the request",
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
                detail=f"OpenAI request failed with status {provider_status}",
                retryable=retryable,
                provider_status_code=provider_status,
                error_class=error_class,
            ) from exc
        except APIConnectionError as exc:
            raise ProviderServiceError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="PROVIDER_UNAVAILABLE",
                detail="OpenAI request failed",
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
