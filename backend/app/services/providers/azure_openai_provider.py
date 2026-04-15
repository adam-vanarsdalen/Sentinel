from __future__ import annotations

import os
from typing import Any

from fastapi import status

from app.core.errors import ProviderServiceError
from app.services.providers.base import LlmProvider, ProviderResponse, provider_timeout


def _as_dict(obj: Any) -> dict:
    if isinstance(obj, dict):
        return obj
    for attr in ("model_dump", "to_dict_recursive", "to_dict", "dict"):
        fn = getattr(obj, attr, None)
        if callable(fn):
            try:
                data = fn()
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
    return {"repr": repr(obj)}


class AzureOpenAiProvider(LlmProvider):
    name = "azure_openai"

    def chat_completions(
        self,
        *,
        model: str,
        messages: list[dict],
        max_tokens: int | None,
        temperature: float | None,
        runtime_config: dict | None = None,
    ) -> ProviderResponse:
        """
        Azure OpenAI: `model` is the Azure deployment name.
        """
        runtime_config = runtime_config or {}
        endpoint = str(runtime_config.get("endpoint") or os.getenv("AZURE_OPENAI_ENDPOINT") or "").strip()
        api_version = str(runtime_config.get("api_version") or os.getenv("AZURE_OPENAI_API_VERSION") or "").strip()
        api_key = str(runtime_config.get("api_key") or os.getenv("AZURE_OPENAI_API_KEY") or "").strip()
        auth_mode = str(runtime_config.get("auth_mode") or "api_key").strip().lower()
        managed_identity_client_id = str(runtime_config.get("managed_identity_client_id") or "").strip()
        if not endpoint:
            raise RuntimeError("AZURE_OPENAI_ENDPOINT not configured")
        if not api_version:
            raise RuntimeError("AZURE_OPENAI_API_VERSION not configured")

        try:
            from openai import AzureOpenAI  # type: ignore
        except Exception as e:
            raise RuntimeError("openai Python SDK not installed") from e

        if auth_mode == "managed_identity":
            try:
                from azure.identity import DefaultAzureCredential, ManagedIdentityCredential, get_bearer_token_provider  # type: ignore
            except Exception as e:
                raise RuntimeError("azure-identity is required for Azure OpenAI managed identity mode") from e

            credential = (
                ManagedIdentityCredential(client_id=managed_identity_client_id)
                if managed_identity_client_id
                else DefaultAzureCredential(exclude_interactive_browser_credential=True)
            )
            token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
            client = AzureOpenAI(
                azure_endpoint=endpoint,
                api_version=api_version,
                azure_ad_token_provider=token_provider,
                timeout=provider_timeout(runtime_config),
            )
        else:
            if not api_key:
                raise RuntimeError("AZURE_OPENAI_API_KEY not configured")
            client = AzureOpenAI(
                azure_endpoint=endpoint,
                api_version=api_version,
                api_key=api_key,
                timeout=provider_timeout(runtime_config),
            )

        payload: dict[str, Any] = {"model": model, "messages": messages}
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if temperature is not None:
            payload["temperature"] = temperature

        try:
            resp = client.chat.completions.create(**payload)
        except Exception as exc:
            exc_name = exc.__class__.__name__
            lowered = exc_name.lower()
            if "timeout" in lowered:
                raise ProviderServiceError(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    code="PROVIDER_TIMEOUT",
                    detail="Azure OpenAI request timed out",
                    retryable=True,
                    error_class="timeout",
                ) from exc
            if "authentication" in lowered or "permission" in lowered:
                raise ProviderServiceError(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    code="PROVIDER_UNAVAILABLE",
                    detail="Azure OpenAI authentication failed",
                    retryable=False,
                    error_class="auth",
                ) from exc
            retryable = "connection" in lowered or "rate" in lowered or "apierror" in lowered or "server" in lowered
            error_class = "connection" if "connection" in lowered else "rate_limit" if "rate" in lowered else "server_error" if ("apierror" in lowered or "server" in lowered) else None
            raise ProviderServiceError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="PROVIDER_UNAVAILABLE",
                detail="Azure OpenAI request failed",
                retryable=retryable,
                error_class=error_class,
            ) from exc
        data = _as_dict(resp)
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}
        return ProviderResponse(
            content=content,
            raw=data,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
        )
