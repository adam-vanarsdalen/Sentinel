# Model Provider Integration Notes

Date verified: 2026-04-14

## Integrations present in this repo

- OpenAI (`backend/app/services/providers/openai_provider.py`)
- Anthropic (`backend/app/services/providers/anthropic_provider.py`)
- Azure OpenAI (`backend/app/services/providers/azure_openai_provider.py`)
- Mock provider for local/test workflows

## Web-verified references

- OpenAI Python SDK (official): https://github.com/openai/openai-python
- OpenAI Chat Completions reference/overview: https://developers.openai.com/api/reference/chat-completions/overview
- Anthropic Python SDK (official): https://github.com/anthropics/anthropic-sdk-python
- Anthropic model IDs overview: https://platform.claude.com/docs/en/about-claude/models/overview
- Azure OpenAI via OpenAI Python SDK (`AzureOpenAI`): https://github.com/openai/openai-python
- Azure OpenAI REST/API versioning reference: https://learn.microsoft.com/azure/ai-services/openai/reference

## What was checked

- request/response call shape for current SDK usage
- model argument semantics (including Azure deployment-name behavior)
- timeout/auth/error handling patterns
- base URL / endpoint handling
- compatibility of current provider IDs and model IDs used in Sentinel

## Changes made

1. OpenAI provider integration updated to official SDK path
- `OpenAiProvider` now uses `openai.OpenAI(...).chat.completions.create(...)` instead of raw `httpx` POST.
- Added explicit mapping for SDK exceptions:
  - `APITimeoutError` -> `PROVIDER_TIMEOUT`
  - `AuthenticationError` -> non-retryable auth failure
  - `RateLimitError` / `APIStatusError` -> retryable/non-retryable classification by status
  - `APIConnectionError` -> retryable connection failure

2. Catalog-driven provider/model validation
- Added canonical backend catalog and normalization helpers in `backend/app/core/model_catalog.py`.
- Provider config and gateway resolution now normalize model IDs per provider through this catalog.
- Eval run API now validates provider/model values before creating runs.

3. Frontend model selection is now backend-catalog-driven
- Provider settings UI, Evaluations UI, and Policy simple-mode model options now consume catalog-derived data.
- Removed hardcoded model arrays in these surfaces.

## Current caveats (intentional)

- Azure OpenAI uses deployment names as `model`; custom deployment IDs must remain allowed (`supports_custom_models=true`).
- Legacy model IDs are still represented in the catalog with `status=legacy` for backward compatibility (existing seeded data/tests/history).
- Anthropic and Azure providers still use broad exception-name classification for some non-auth timeout cases; this is functional but less granular than strict provider-specific typed exception mapping.

## Practical support truth

- Sentinel currently supports provider routing and policy controls for OpenAI, Anthropic, and Azure OpenAI.
- Supported model choices are curated by the catalog and intentionally limited; this is not “all provider models automatically.”
- Mock provider remains available for local/test/demo safety workflows.
