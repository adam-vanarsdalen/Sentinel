# Data Handling (Pilot)

This document explains what Sentinel stores, what it does not store by default, and what controls exist for redacted logging.

## What Sentinel stores

Sentinel writes an `audit_events` record for each gateway request (and for certain admin actions). The audit log is tenant-scoped via `tenant_id`.

For a gateway request, the stored fields include:

- **Tenant and actor identifiers**
  - `tenant_id`
  - `api_key_id` (gateway API key ID) and/or `user_id` (UI user ID), when present
  - `request_id` for request correlation (also returned as the `X-Request-Id` response header)

- **Event metadata**
  - `timestamp`
  - `action_type` and `outcome` (e.g., allowed vs blocked)
  - `reason` (short explanation when blocked/failed)
  - `provider` and `model`

- **Matter metadata (optional)**
  - `matter_id`, `practice_group`, `client_name` (if supplied in request metadata/headers)

- **Risk signals**
  - `phi_score` (0–100 heuristic confidential-data risk score)
  - `risk_flags` (e.g., prompt injection suspected, sensitive request, etc.)
  - `severity` (`low`/`med`/`high`)

- **Usage/cost**
  - `tokens_prompt`, `tokens_completion` (actual when the provider returns usage; otherwise estimated)
  - `cost_usd` (estimated)

- **Content fingerprints (hashes)**
  - `prompt_hash` (SHA-256 of the prompt text)
  - `response_hash` (SHA-256 of the response text)

## What Sentinel does NOT store by default

By default, Sentinel does **not** persist:

- raw prompt text
- raw response text

The gateway does handle raw prompt/response in memory to call the provider and to compute risk signals, but it stores only hashes by default.

## Optional: redacted snippets (how it works)

Sentinel can optionally store **redacted snippets** of the prompt and response in the audit log:

- It takes the first ~200 characters of the prompt/response.
- It masks detected patterns (e.g., `[EMAIL]`, `[PHONE]`, `[SSN]`, `[MATTER_NO]`, `[IBAN]`, etc.).
- It stores the masked snippet in:
  - `redacted_prompt`
  - `redacted_response`

This is intended to help operators triage incidents without storing full content.

### How to enable redacted snippets

Redacted snippet storage is controlled per-tenant by the active policy JSON:

- Set `logging.store_redacted_snippets = true`

When enabled, Sentinel stores redacted snippets for both allowed and blocked gateway events.

## Audit log retention and deletion

- **Retention:** Sentinel does not hard-code a retention period. Audit events remain in the database until you remove or archive them using your own database retention procedures.
- **Deletion workflow:** There is no built-in API endpoint to delete individual audit events or to purge audit history. If your organization requires deletion/purge workflows, implement them at the database layer (or add an application-level retention job with explicit approval and change control).

Operational guidance and recommended retention ranges for pilot deployments are documented in `docs/LoggingAndRetention.md`.

## Provider API keys and where they are stored

Sentinel treats *provider* credentials (OpenAI/Anthropic/Azure OpenAI/Ollama) as runtime configuration:

- Provider API keys are read from environment variables (e.g., `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `AZURE_OPENAI_API_KEY`, `OLLAMA_API_KEY`).
- Provider API keys are **not stored in the database**.

Note: Sentinel also has its own **gateway API keys** for client applications. Those are stored in the database in **hashed** form (prefix + salt + hash) so the plaintext token cannot be recovered.

## Tenant isolation model

Sentinel enforces tenant separation using `tenant_id` foreign keys and tenant-scoped queries:

- Core tables that contain customer data (including `audit_events`) include a required `tenant_id`.
- API endpoints that read/write tenant data require tenant context and filter by `tenant_id` before returning results.
- A platform `super_admin` can switch tenant context, but reads are still scoped to the selected `tenant_id`.

This is logical isolation within a shared database. If you require physical isolation (separate databases per tenant), that is an architectural change.

## Important operational note

Even if Sentinel does not store raw prompt/response by default, the selected LLM provider may log or retain request content according to its own policies and your contract/tenant settings. Evaluate provider-side logging/retention as part of your deployment review.
