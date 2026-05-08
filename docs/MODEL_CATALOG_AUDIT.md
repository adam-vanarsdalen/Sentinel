# Model/Provider Catalog Audit

Date: 2026-04-15

## Scope

Repo-wide audit across backend, frontend, preset seed data, tests, and docs for:

- provider identifiers
- model identifiers
- hardcoded allowed-model arrays
- provider/model validation paths

## Provider identifiers found before normalization

- `openai`
- `anthropic`
- `azure_openai`
- `ollama`
- `mock` (internal/dev and test path)

## Model identifiers found before normalization

- OpenAI-family IDs: `gpt-4.1`, `gpt-4.1-mini`, `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`, `gpt-4`, `gpt-3.5-turbo`
- Anthropic-family IDs: `claude-sonnet-4-6`, `claude-sonnet-4-5`, `claude-opus-4-6`, `claude-opus-4`, `claude-3-5-sonnet-latest`, `claude-3-haiku-20240307`
- Azure deployment-style IDs: `care-gpt-4o-mini`, `care-gpt-4.1-mini`, `gpt-4o-prod`, `gpt-4.1-review`
- Ollama IDs: `gpt-oss:120b-cloud`
- Internal/dev: `mock`

## Drift hotspots discovered

- Provider config UI examples had hardcoded model strings separate from seed data.
- Evaluations UI used a static provider/model map not sourced from backend config.
- Policy “simple mode” allowed-model checkboxes used a static hardcoded list.
- Backend provider-policy/model allowlist normalization was duplicated and not provider-aware.
- Seed/demo data and tests used mixed generations (`gpt-4o`/`gpt-4-turbo` and `claude-3-5-sonnet-latest`/`claude-sonnet-4-5`/`claude-sonnet-4-6`).
- Docs/examples still referenced older IDs after earlier preset generalization.

## Normalization implemented

Canonical source of truth now lives in:

- `backend/app/core/model_catalog.py`

It defines:

- canonical provider catalog (display names, default model field, supports_custom_models)
- curated model list per provider
- status flags (`active`, `legacy`, `example`)
- provider/model normalization helpers
- provider-aware allowlist normalization
- payload shape for frontend consumption

## Canonical catalog (current)

- `mock`: `mock`
- `openai`: `gpt-4.1-mini`, `gpt-4.1`, `gpt-4o-mini` (legacy), `gpt-4o` (legacy), `gpt-4-turbo` (legacy)
- `anthropic`: `claude-sonnet-4-6`, `claude-opus-4-6`, `claude-3-5-sonnet-latest` (legacy), `claude-sonnet-4-5` (legacy), `claude-opus-4` (legacy), `claude-3-haiku-20240307` (legacy)
- `azure_openai`: deployment-name mode (`supports_custom_models=true`) with seeded examples: `care-gpt-4o-mini`, `care-gpt-4.1-mini`, `gpt-4o-prod`
- `ollama`: `gpt-oss:120b-cloud` (default curated Ollama model for this repo)

## Key repo changes tied to this audit

- Added catalog endpoint: `GET /admin/provider-configs/catalog`
- Refactored backend provider/model normalization to use catalog helpers
- Added eval run provider/model validation against catalog
- Replaced hardcoded frontend provider/eval/policy model lists with catalog-driven data
- Normalized several legacy model strings in tests/docs/examples to current curated IDs

## Remaining intentional flexibility

- Azure OpenAI keeps custom deployment support by design.
- Legacy IDs remain represented in catalog with `status: legacy` for compatibility and historical data continuity.
