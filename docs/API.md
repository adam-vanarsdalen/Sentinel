# Sentinel API (Frontend Contract)

This document describes backend endpoints currently implemented in this repo and consumed by the frontend.

If the UI requires additional endpoints, they will be added minimally and documented here.

## Auth

- `POST /auth/login`
  - Body: `{ "email": string, "password": string }`
  - Response: `{ "access_token": string, "token_type": "bearer" }`
- `GET /auth/me`
  - Auth: Bearer JWT
  - Response: `{ "id": string, "email": string, "role": string, "tenant_id": string | null }`
  - Note: For `super_admin`, a tenant context can be selected by sending `X-Tenant-Id: <tenant_uuid>`.
  - Note: Responses include `X-Request-Id` header for correlation.

## Error Envelope

Sentinel API failures use a consistent error shape:

```json
{
  "error": {
    "code": "POLICY_BLOCKED",
    "message": "Blocked by organization rules.",
    "detail": "Prompt blocked by policy",
    "request_id": "req_123",
    "retryable": false
  },
  "detail": "Prompt blocked by policy"
}
```

Notes:
- `error.code` is the stable machine-readable field.
- `error.message` is safe for direct frontend display.
- `error.detail` is a more specific operator-facing explanation.
- `error.request_id` matches `X-Request-Id` when available.
- The top-level `detail` field remains for compatibility with older clients.

Stable error codes:
- `AUTH_REQUIRED`
- `FORBIDDEN`
- `TENANT_SCOPE_ERROR`
- `PROVIDER_UNAVAILABLE`
- `PROVIDER_TIMEOUT`
- `POLICY_BLOCKED`
- `VALIDATION_ERROR`
- `EXPORT_FAILED`
- `INTERNAL_ERROR`

## Tenants (super_admin)

- `GET /admin/tenants`
  - Auth: Bearer JWT, role `super_admin`
  - Response: array of `{ id, name, slug, status, created_at }`

## Platform Organizations (super_admin)

These endpoints are for platform-wide tenant/organization administration. They do not require `X-Tenant-Id` and are restricted to `super_admin`.

- `GET /platform/tenants?query=&status=&page=&page_size=&sort=`
  - Auth: Bearer JWT, role `super_admin`
  - Response: `{ items: [...], total, page, page_size }`
- `POST /platform/tenants`
  - Auth: Bearer JWT, role `super_admin`
  - Body: `{ "name": string, "slug"?: string, "status"?: "active"|"suspended"|"archived" }`
  - Response: `{ tenant: { id, name, slug, status, created_at, updated_at } }`
  - Notes:
    - If `slug` omitted, it is generated from `name` (and de-conflicted if needed).
    - If `slug` provided and already in use, returns `409`.
- `GET /platform/tenants/{tenant_id}`
  - Auth: Bearer JWT, role `super_admin`
  - Response: `{ tenant: { id, name, slug, status, created_at, updated_at, settings_json } }`
- `PATCH /platform/tenants/{tenant_id}`
  - Auth: Bearer JWT, role `super_admin`
  - Body: `{ "name"?: string, "slug"?: string, "status"?: "active"|"suspended"|"archived" }`
  - Response: `{ tenant: { id, name, slug, status, created_at, updated_at } }`
- `POST /platform/tenants/{tenant_id}/switch`
  - Auth: Bearer JWT, role `super_admin`
  - Response: `{ current_tenant: { id, name, slug, status, created_at, updated_at } }`
  - Note: The frontend stores this context and sends it as `X-Tenant-Id` on tenant-scoped admin requests.
- `GET /platform/tenants/{tenant_id}/summary?range=24h|7d|30d`
  - Auth: Bearer JWT, role `super_admin`
  - Response: `{ tenant, summary }` where `summary` matches `/admin/metrics/overview`

## API Keys

- `GET /admin/api-keys`
  - Auth: Bearer JWT
  - Response: array of `{ id, name, key_prefix, is_active, created_at, revoked_at, last_used_at }`
- `POST /admin/api-keys`
  - Auth: Bearer JWT
  - Body: `{ "name": string }`
  - Response: `{ api_key: {...}, token: "sk_..." }` (secret shown once)
- `POST /admin/api-keys/{api_key_id}/revoke`
  - Auth: Bearer JWT, role `tenant_admin` or `super_admin`
  - Response: `{ id, name, key_prefix, is_active, created_at, revoked_at }`

## Provider Settings

These endpoints are tenant-scoped and are intended for the organization administrator role.

- `GET /admin/provider-configs/catalog`
  - Auth: Bearer JWT, role `org_admin | compliance_admin | operator | reviewer | auditor | super_admin`
  - Response: `{ providers: [...] }`
    - each provider includes:
      - `id`
      - `display_name`
      - `default_model_field`
      - `supports_custom_models`
      - `enabled_by_default`
      - `notes`
      - `models[]` with `{ id, display_name, status, aliases }`
  - Notes:
    - This is the canonical provider/model source used by admin UI surfaces.
    - `azure_openai` uses deployment names and intentionally allows custom values.

- `GET /admin/provider-configs`
  - Auth: Bearer JWT, role `org_admin`
  - Response: array of `{ id, tenant_id, provider_type, display_name, is_enabled, is_default, model_allowlist, config_json, secret_configured, secret_status, created_at, updated_at }`
  - Important: secrets are never returned; responses only indicate whether a secret is configured.
- `POST /admin/provider-configs`
  - Auth: Bearer JWT, role `org_admin`
  - Body:
    - `provider_type`: `openai | anthropic | azure_openai`
    - `display_name`: string
    - `is_enabled?`: boolean
    - `is_default?`: boolean
    - `model_allowlist?`: string[]
    - `config_json?`: provider-specific non-secret config
      - Optional `config_json.resilience`:
        - `connect_timeout_seconds`
        - `read_timeout_seconds`
        - `retry_count`
        - `retryable_status_codes`
        - `retryable_error_classes`
        - `fallback_enabled`
        - `fallback_provider`
        - `fallback_model`
    - `secret_json?`: provider-specific secret payload (write-only)
  - Response: masked provider config shape (same as `GET`)
- `PATCH /admin/provider-configs/{id}`
  - Auth: Bearer JWT, role `org_admin`
  - Body: partial update of the create fields plus `clear_secret?` for Azure managed-identity transitions
  - Response: masked provider config shape
- `DELETE /admin/provider-configs/{id}`
  - Auth: Bearer JWT, role `org_admin`
  - Response: `{ ok: true }`
- `POST /admin/provider-configs/{id}/test-connection`
  - Auth: Bearer JWT, role `org_admin`
  - Response: `{ ok: true, provider_type, model }`
- `POST /admin/provider-configs/{id}/set-default`
  - Auth: Bearer JWT, role `org_admin`
  - Response: masked provider config shape
- `GET /admin/provider-configs/policy`
  - Auth: Bearer JWT, role `org_admin`
  - Response:
    - `{ tenant_id, default_provider, providers, warnings }`
    - `providers[]` shape:
      - `provider_type`
      - `provider_config_id`
      - `display_name`
      - `is_configured`
      - `secret_configured`
      - `is_enabled`
      - `is_default`
      - `allowed_models`
      - `default_model`
- `PUT /admin/provider-configs/policy`
  - Auth: Bearer JWT, role `org_admin`
  - Body:
    - `default_provider?`: `openai | anthropic | azure_openai | null`
    - `providers[]`:
      - `provider_type`
      - `is_enabled`
      - `allowed_models`
      - `default_model?`
  - Notes:
    - This updates the tenant’s explicit provider/model approval policy using the existing provider-config rows.
    - A provider must already be configured before it can be enabled/approved.
    - Saving this endpoint writes an audit event with `action_type = "PROVIDER_POLICY_UPDATE"`.

Provider-specific validation:
- `openai`: API key required
- `anthropic`: API key required
- `azure_openai`: `config_json.endpoint` + `config_json.api_version` + (`config_json.default_deployment` or non-empty `model_allowlist`) + either API key or managed-identity metadata
- If a provider config has both an allowlist and a default model/deployment, the default must also appear in the allowlist.
- `config_json.resilience.connect_timeout_seconds` must be between `0.5` and `120`.
- `config_json.resilience.read_timeout_seconds` must be between `1` and `600`.
- `config_json.resilience.retry_count` must be between `0` and `3`.
- If fallback is enabled, both `fallback_provider` and `fallback_model` are required.

UI notes:
- The tenant-admin console presents one card each for OpenAI, Anthropic, and Azure OpenAI.
- Saved secrets are never shown back to the browser; the UI only indicates whether a secret is configured.
- The recommended operator flow is “Save” or “Save and Test” directly from the provider card instead of editing environment variables.

Provider resilience notes:
- Retries and fallback are explicit tenant/provider settings; Sentinel does not silently switch providers by default.
- Retry auditing:
  - `PROVIDER_TIMEOUT`
  - `PROVIDER_RETRY`
- Fallback auditing:
  - `PROVIDER_FALLBACK_USED`
  - `PROVIDER_FALLBACK_DENIED`
- When fallback succeeds, the final `LLM_REQUEST` audit event records the actual provider/model that handled the request, and `event_data.routing.attempts` records the attempted route history.

## Alerts

These endpoints are tenant-scoped and are intended for the organization administrator role.

- `GET /admin/alerts/current`
  - Auth: Bearer JWT, role `tenant_admin`
  - Response: `{ tenant_id, alerts, updated_at, updated_by_user_id }`
  - `alerts` shape:
    - `phi_threshold`
    - `severity_threshold`: `low | med | high`
    - `email_recipients`
    - `webhook_format`: `generic | slack | teams`
    - `webhook_configured`
    - `webhook_status`
    - `webhook_destination_hint`
    - `triggers`
    - `throttle_window_minutes`
    - `provider_failure_threshold`
- `PUT /admin/alerts/current`
  - Auth: Bearer JWT, role `tenant_admin`
  - Body:
    - `phi_threshold`
    - `severity_threshold`
    - `email_recipients`
    - `webhook_url?` (write-only)
    - `clear_webhook?`
    - `webhook_format?`
    - `triggers`
    - `throttle_window_minutes`
    - `provider_failure_threshold`
  - Notes:
    - Webhook URLs are stored in protected form and are never returned to the browser after save.
    - Saving this endpoint writes an audit event with `action_type = "ALERT_SETTINGS_UPDATED"`.
- `GET /admin/alerts/history?limit=20`
  - Auth: Bearer JWT, role `tenant_admin`
  - Response: array of `{ id, timestamp, status, trigger_type, severity, channel, destination, request_id, reason }`
  - Notes:
    - History is derived from tenant-scoped audit events with `action_type = "ALERT_SENT"` and `ALERT_FAILED`.
    - Only the current tenant’s alert deliveries are returned.
- `POST /admin/alerts/test`
  - Auth: Bearer JWT, role `tenant_admin`
  - Response: `{ ok, results }`
  - `results[]` shape: `{ channel, destination, status, error? }`

Alert triggers currently supported:
- high confidentiality exposure (`phi_score >= alerts.phi_threshold`)
- prompt injection detected
- request blocked by organization policy or provider/model approval controls
- repeated provider failures inside the configured throttle window

Alert delivery notes:
- Email uses deployment-level SMTP settings (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`) and tenant-scoped recipient lists.
- Generic, Slack-style, and Teams-style webhook formatting are supported through a single tenant-scoped webhook setting.
- Sentinel applies basic deduplication by alert type inside `throttle_window_minutes` to reduce alert storms.
- Successful and failed deliveries are audited as `ALERT_SENT` and `ALERT_FAILED`.

## Policy

- `GET /admin/policy/current`
  - Auth: Bearer JWT
  - Response: `{ tenant_id, policy_json, updated_at, updated_by_user_id, active_version_id }`
- `PUT /admin/policy/current`
  - Auth: Bearer JWT, role `tenant_admin` or `super_admin`
  - Body: `{ "policy_json": {...}, "change_note"?: string, "source_template_id"?: string }`
  - Response: `{ tenant_id, policy_json, updated_at, updated_by_user_id, active_version_id }`
  - Each successful publish creates a new immutable policy version and marks it active.
  - Audit events written:
    - `POLICY_VERSION_CREATED`
    - `POLICY_VERSION_ACTIVATED`
  - Policy JSON (selected optional fields):
    - `rate_limits`: `{ tenant_per_minute?, api_key_per_minute? }` (overrides global rate limits for this organization)
    - `metadata_requirements`: `{ data_classification: string[] }` (e.g., require `metadata.data_classification`)
    - `security.prompt_injection_action`: `flag | block_high | block_med`
      - `flag`: detect and audit only
      - `block_high`: block only `high` heuristic prompt-injection severity
      - `block_med`: block `med` and `high` heuristic prompt-injection severity
    - `phi.flag_on_any_match`: `true|false` (adds a risk flag when PII-like patterns are detected, even if not blocking)
- `GET /admin/policy/templates`
  - Auth: Bearer JWT
  - Response: array of `{ id, name, description }`
  - Built-in template IDs:
    - `legal_default_policy_v1`
    - `legal_strict_confidentiality_v1`
    - `legal_strict_no_client_data_v1`
- `GET /admin/policy/templates/{template_id}`
  - Auth: Bearer JWT
  - Response: `{ id, name, description, policy_json }`
- `POST /admin/policy/test`
  - Auth: Bearer JWT, role `tenant_admin`/`super_admin`/`developer`
  - Body: `{ "policy_json": {...} }`
  - Response: `{ "ok": true }` if policy validates
- `POST /admin/policy/dry-run`
  - Auth: Bearer JWT, role `tenant_admin`/`super_admin`/`developer`
  - Body: `{ policy_json, model, messages, response_text?, metadata? }`
  - Response: `{ outcome: "ALLOW"|"BLOCK", block_reason?, flags, phi, confidentiality_exposure_level, security, output, effective_messages }`
  - `security` includes:
    - `flags`
    - `severity` (`low | med | high`)
    - `detector_names_triggered`
    - `normalized_match_examples` (redacted snippets derived from normalized text)
- `GET /admin/policy/history?limit=20`
  - Auth: Bearer JWT
  - Response: array of `{ id, tenant_id, created_at, created_by_user_id, created_by_email, change_note, summary, active, source_template_id, source_version_id, policy_json }`
- `GET /admin/policy/history/{id}`
  - Auth: Bearer JWT
  - Response: `{ id, tenant_id, created_at, created_by_user_id, created_by_email, change_note, summary, active, source_template_id, source_version_id, policy_json }`
- `POST /admin/policy/rollback/{id}`
  - Auth: Bearer JWT, role `tenant_admin` or `super_admin`
  - Response: `{ tenant_id, policy_json, updated_at, updated_by_user_id, active_version_id }`
  - Creates a new active version from the selected historical version without mutating the original row.
  - Audit events written:
    - `POLICY_VERSION_CREATED`
    - `POLICY_VERSION_ACTIVATED`
    - `POLICY_ROLLBACK`
- `GET /admin/policy/versions?limit=20`
  - Compatibility alias for `/admin/policy/history`

## Audit Events

- `GET /admin/audit-events`
  - Auth: Bearer JWT
  - Query: `start` (datetime), `end` (datetime), `action_type` (string), `practice_group`, `matter_id`, `matter_query`
  - Response: array of audit event dicts (pilot limit 500)
- `GET /admin/audit-events/search`
  - Auth: Bearer JWT
  - Query: `start`, `end`, `action_type`, `outcome`, `severity`, `api_key_id`, `user_id`, `practice_group`, `matter_id`, `matter_query`, `flag`, `limit`, `offset`
  - Response: `{ items: [...], total, limit, offset }`
  - Note: Tenant context is required for `super_admin` (send `X-Tenant-Id`).
- `GET /admin/audit-events/{event_id}`
  - Auth: Bearer JWT
  - Response: single audit event dict
- `GET /admin/audit-events/export.csv`
  - Auth: Bearer JWT (`auditor`+)
  - Query: same filters as `/search`
  - Response: CSV download (pilot limit 5000)
- `GET /admin/audit-events/export.json?format=sentinel|fhir`
  - Auth: Bearer JWT (`auditor`+)
  - Query: same filters as `/search`
  - Response: JSON array (Sentinel shape; optional legacy `fhir` shape for compatibility)
- `GET /admin/audit-events/report.html`
  - Auth: Bearer JWT (`auditor`+)
  - Query: same filters as `/search`, plus `include_summary=true|false`
  - Response: client-ready HTML audit report with organization name, filter scope, summary metrics, flagged/blocked summaries, top matters/practice groups, detailed appendix, export timestamp, and `report_version`
- `GET /admin/audit-events/report.pdf`
  - Auth: Bearer JWT (`auditor`+)
  - Query: same filters as `/search`, plus `include_summary=true|false`
  - Response: client-ready PDF audit report with the same sections as the HTML report
- `GET /admin/audit-events/export.pdf`
  - Auth: Bearer JWT (`auditor`+)
  - Query: same filters as `/search`
  - Response: legacy flat PDF export of the filtered event list

Audit event fields (selected):
- `id`: unique event ID
- `request_id`: request correlation ID (matches `X-Request-Id` header when event was created)
- `previous_event_hash`: previous event hash in the tenant-local append-only chain
- `event_hash`: current event hash derived from immutable event payload + previous hash
- `timestamp`, `action_type`, `outcome`, `reason`, `risk_flags`, `phi_score`, `cost_usd`, etc.

## Audit Integrity

- `GET /audit/integrity/verify?from=&to=&tenant_id=`
  - Auth: Bearer JWT (`super_admin`, `tenant_admin`, or `auditor`)
  - Query:
    - `from` optional datetime
    - `to` optional datetime
    - `tenant_id` optional; mainly for `super_admin`
  - Response:
    - `{ total_events_checked, chain_valid, first_broken_event_id }`
  - Notes:
    - Verification is tenant-scoped.
    - Running verification writes an audit event with `action_type = "AUDIT_VERIFY_RUN"`.
    - Sentinel rejects normal application-layer update/delete attempts against existing audit rows.

## Metrics

- `GET /admin/metrics/overview?range=24h|7d|30d`
  - Auth: Bearer JWT
  - Response: cards + simple time series used by the dashboard UI
- `GET /admin/metrics/risk-summary?range=24h|7d|30d`
  - Auth: Bearer JWT
  - Response: `{ total_ai_requests, injection_attempts_flagged, blocked_requests, high_confidentiality_exposure, top_matters }` (tenant-scoped)

## Evaluations

- `GET /admin/evals/suites`
  - Auth: Bearer JWT
  - Response: seeded eval test cases for the tenant
- `POST /admin/evals/run`
  - Auth: Bearer JWT (`developer`+)
  - Body: `{ "provider": string, "model": string }`
  - Response: `{ "run_id": string, "status": string }`
- `GET /admin/evals/runs`
  - Auth: Bearer JWT
  - Response: array of `{ id, tenant_id, provider, model, status, started_at, finished_at, summary }`
- `GET /admin/evals/runs/{run_id}`
  - Auth: Bearer JWT
  - Response: `{ run, results }`

## Tenant Settings

- `GET /admin/settings/current`
  - Auth: Bearer JWT
  - Response: `{ tenant_id, settings_json, updated_at, updated_by_user_id }`
- `PUT /admin/settings/current`
  - Auth: Bearer JWT (`tenant_admin`+)
  - Body: `{ settings_json }`
  - Response: `{ tenant_id, settings_json, updated_at, updated_by_user_id }`
  - Note: operational alert recipients, delivery channels, and alert history now live under `/admin/alerts/*`.

## Users & Roles

- `GET /admin/users`
  - Auth: Bearer JWT
  - Note: Tenant-scoped. For `super_admin`, organization context is required (send `X-Tenant-Id`).
  - Response: array of `{ id, email, role, tenant_id, is_active, created_at }`
- `POST /admin/users`
  - Auth: Bearer JWT (`tenant_admin`+)
  - Body: `{ email, role, tenant_id? }`
  - Response: `{ user, temp_password }` (pilot)
- `PUT /admin/users/{user_id}/role`
  - Auth: Bearer JWT (`tenant_admin`+)
  - Body: `{ role }`
  - Response: updated user
- `DELETE /admin/users/{user_id}`
  - Auth: Bearer JWT (`tenant_admin`+)
  - Response: updated user
  - Note: Soft-delete (deactivates the user) to preserve audit trails.

## Gateway (machine-to-machine)

- `POST /v1/chat/completions`
  - Auth: API key (`Authorization: Bearer sk_...`)
  - Body:
    - `provider?`: optional `openai | anthropic | azure_openai`; if omitted, Sentinel uses the tenant’s default enabled provider config
    - `model?`: optional model/deployment name; if omitted, Sentinel uses the approved provider’s default model/deployment when configured
  - Optional metadata (recommended): send in body as `{ metadata: { matter_id?, practice_group?, client_name?, data_classification?, purpose? } }`
    - `data_classification` is required by the `legal_strict_no_client_data_v1` template (allowed values: `PUBLIC`, `INTERNAL_NON_CLIENT`).
  - Convenience headers (optional): `X-Matter-Id`, `X-Practice-Group`, `X-Client-Name` (used only if body metadata fields are not set)
  - Routing rules:
    - If the tenant has provider configs, Sentinel treats enabled configs as the tenant’s approved providers.
    - If the tenant has multiple approved providers and no default provider is configured, requests that omit `provider` are rejected.
    - If the selected approved provider has a non-empty allowlist, requests outside that allowlist are rejected.
    - If `model` is omitted and the selected provider has no default model/deployment configured, the request is rejected.
    - If the tenant has no provider configs, Sentinel may fall back to the old global env-provider behavior in local development only.
  - Blocked response shape (pilot):
    - Status: `400` or `403`
    - Body: `{ error: { code: "POLICY_BLOCKED", message, detail, request_id, retryable }, outcome: "BLOCKED", block_reason: string, reason_code?: string, provider?: string, model?: string, flags: string[], policy: { updated_at?, version_id?, rule?, reason_code? }, security?: { flags, severity, detector_names_triggered, normalized_match_examples }, detail: string }`
  - Provider/model deny reason codes:
    - `provider_not_approved`
    - `default_provider_required`
    - `model_not_approved`
    - `default_model_required`
  - Provider runtime failures:
    - Provider timeouts return `error.code = "PROVIDER_TIMEOUT"` with `retryable = true`.
    - Other provider outages/auth failures return `error.code = "PROVIDER_UNAVAILABLE"`.

## Health and Ops

- `GET /health`
  - Basic liveness check (alias of `/healthz`)
- `GET /healthz`
  - Basic liveness check
- `GET /ready`
  - Readiness check (alias of `/readyz`)
- `GET /readyz`
  - Readiness check (DB + Redis + template availability, plus demo-tenant check when seeding is enabled)
- `GET /metrics`
  - Prometheus-format metrics
