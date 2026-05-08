# Security Overview (Pilot)

This document is written for security reviewers evaluating Sentinel. It describes authentication, authorization, data isolation, safety controls, logging, and deployment recommendations. It should be read alongside `docs/THREAT_MODEL.md` and `docs/DataHandling.md`.

## Authentication and session handling (UI)

Sentinel uses a JWT-based session for the admin UI:

1) A user signs in via `POST /auth/login` (email + password).
2) The backend validates the password hash and returns a signed JWT (`access_token`).
3) The Next.js frontend stores that JWT in an `httpOnly` cookie named `sentinel_access_token` (so JavaScript in the browser cannot read it).
4) UI API calls are proxied through a Next.js `/api/proxy/*` route, which reads the cookie server-side and forwards the request to the backend with an `Authorization: Bearer <JWT>` header.

JWT properties (backend):
- Signed with `JWT_SECRET` (HMAC-SHA256).
- Includes `iss`/`aud` and an `exp` (expiration) enforced on decode.
- Expiration is controlled by `ACCESS_TOKEN_EXPIRES_MINUTES`.

Cookie properties (frontend):
- `httpOnly: true`, `sameSite: "lax"`, `secure: true` when the request is HTTPS (or `COOKIE_SECURE=1`).

## Authorization model and tenant context

Sentinel uses role-based access control (RBAC) for admin actions. Canonical organization roles are:

- `org_admin`: manages users, policies, settings, and API keys within the organization.
- `compliance_admin`: manages governance rules, alerts, and oversight settings.
- `operator`: manages integrations, API keys, and operational testing.
- `auditor`: reads logs and exports audit reports.
- `reviewer`: read-only access to dashboards/logs/policies.

Backward compatibility:
- Legacy aliases (`tenant_admin`, `developer`, `viewer`) are still accepted and normalized to `org_admin`, `operator`, and `reviewer`.

Tenant context:
- Most admin endpoints are tenant-scoped and require an organization context.
- A platform `super_admin` can select organization context by sending `X-Tenant-Id: <tenant_uuid>`; the UI does this via the proxy route when `tenant_id` is provided.

## Gateway API keys (machine-to-machine) and how they are stored

Client applications call the gateway endpoint `POST /v1/chat/completions` using a Sentinel gateway API key token (format `sk_<prefix>_<secret>`).

How keys are stored:
- The plaintext token is **shown once** at creation time.
- The database stores only:
  - `key_prefix` (used to find the key efficiently),
  - a random `key_salt`,
  - and `key_hash = SHA-256(salt + ":" + token)`.
- Verification recomputes the digest and compares using a constant-time comparison.

This means:
- The gateway API key token cannot be recovered from the database.
- A database leak exposes only the prefix + salted hash, not usable plaintext tokens.

User passwords:
- User passwords are stored as Argon2 password hashes (via Passlib).

Provider credentials (OpenAI/Anthropic/Azure OpenAI/Ollama):
- Sentinel now supports per-organization provider credentials in addition to the older global env-based development fallback.
- Organization-scoped provider secrets are stored encrypted at rest in the database using an application-level master secret (`SENTINEL_SECRET_KEY`).
- Provider config API responses never return stored secrets; the UI only receives masked status such as whether a secret is configured.
- Global env provider keys remain supported only as a development fallback when an organization has no provider config.

## Tenant isolation model (data segregation)

Sentinel uses logical isolation in a shared database:
- Core data tables (including `audit_events`) have a `tenant_id` foreign key.
- Organization-scoped provider configs are stored in a tenant-bound table and always looked up by `tenant_id`.
- Admin queries filter by `tenant_id` before returning results.
- Gateway audit events are written with the request’s organization `tenant_id`.

This is appropriate for multi-tenant logical isolation. If your organization requires physical isolation (separate database per tenant), that is an architectural deployment change.

## Prompt injection and confidential-data (PHI-like) detection controls

Sentinel implements controls described in `docs/THREAT_MODEL.md` (OWASP LLM Top 10 categories, using the 2025/v2.0 numbering):

LLM01 (Prompt Injection):
- Heuristic detection flags injection-like cues (`PROMPT_INJECTION_SUSPECTED`).
- Additional detection for injection-like patterns embedded in quoted/bracketed text common in pasted contracts (`EMBEDDED_INJECTION_SUSPECTED`).
- Tenant policy can block known prompt-injection patterns (`block_prompt_patterns`) before calling the provider.
- Tenant policy can enforce a fixed system header (`require_system_prompt_prefix`) to reduce “instruction override” risk.

LLM02 (Sensitive Information Disclosure):
- Confidential-data scanner computes a heuristic `phi_score` (0–100) based on patterns such as email/phone/SSN-like tokens, matter/case/docket numbers, and financial identifiers.
- Tenant policy can flag or block based on threshold and action configuration.
- Sensitive request cues (e.g., “API key”, “password”) are flagged as `SENSITIVE_REQUEST`.

LLM05 (Improper Output Handling):
- Tenant policy can apply postflight output validation (`output_validation_rules`) with “flag” or “block” actions.

Important limitation:
- These are heuristic controls intended for governance/monitoring and policy enforcement. They reduce risk but do not guarantee prevention against novel attacks or data leakage. They should be combined with user training, workflow controls, and provider-side safeguards.

## Rate limiting and DoS protection

Sentinel includes multiple layers intended to mitigate unbounded consumption (ThreatModel: LLM10):

1) Policy-based request bounds (preflight):
   - `max_prompt_chars` enforces maximum prompt size.
   - `max_tokens_per_request` bounds model output tokens.

2) Redis-backed rate limiting:
   - Fixed-window counters per tenant and per API key (bucketed by minute).
   - Defaults are configurable via `RATE_LIMIT_TENANT_PER_MINUTE` and `RATE_LIMIT_APIKEY_PER_MINUTE` and can be overridden per-tenant via policy (`rate_limits`).

Redis availability behavior:
- If Redis is unavailable or times out, the rate limiter **fails open** (request is allowed) and logs a warning. This avoids causing an outage due to Redis downtime, but it also means rate limiting will not protect you during that period.

3) Heuristic DoS signal:
   - Very large prompts or long repeated-character runs are flagged with `DOS_RISK` for monitoring.

## Audit trail: what it captures and integrity properties

What is captured:
- The audit trail is described in `docs/DataHandling.md` and `docs/LoggingAndRetention.md`.
- For each gateway request and certain admin actions, Sentinel writes an `audit_events` record including tenant/actor identifiers, outcome/reason, provider/model, risk flags/scores, token counts/cost, and SHA-256 hashes of prompt/response text.
- Raw prompt/response text is **not stored by default**.
- Optional: redacted snippets can be enabled by organization policy (`logging.store_redacted_snippets = true`).

Integrity and tamper-resistance (current pilot posture):
- Sentinel writes audit events server-side at request time and includes a request correlation ID (`request_id` / `X-Request-Id`).
- The application does not provide an API workflow to delete/purge audit events.
- Sentinel now enforces append-only behavior for `audit_events` at the ORM/session layer and, in PostgreSQL deployments, installs database triggers that reject `UPDATE` and `DELETE`.
- Audit events can be hash-chained per tenant using `previous_event_hash` and `event_hash`, and the chain can be checked through the integrity verification endpoint.
- The database is still the source of truth; a sufficiently privileged database administrator could still tamper by disabling protections or altering schema-level controls.

Recommended hardening for integrity:
- Restrict database write access to only the application role.
- Treat `audit_events` as append-only at the database permission layer.
- Export audit logs periodically to immutable storage (e.g., write-once object storage or SIEM) with access logging.
- Run periodic `GET /audit/integrity/verify` checks and alert on `chain_valid = false`.

## Deployment security recommendations

Transport security (HTTPS):
- Terminate TLS at a reverse proxy (e.g., Caddy/Nginx) and serve the UI/API only over HTTPS.
- Set `COOKIE_SECURE=1` (or ensure `x-forwarded-proto: https` is passed) so the session cookie is marked `Secure`.

Secret handling:
- Provide secrets via environment variables (not in source control).
- Rotate secrets on a regular schedule (JWT signing secret and provider API keys).
- Store gateway API key tokens only in a secret manager; they cannot be recovered from Sentinel later.
- Set `SENTINEL_SECRET_KEY` in production; without it Sentinel will reject startup because it cannot safely encrypt stored provider credentials.

Data minimization defaults:
- Keep raw prompt/response storage disabled unless explicitly required and approved.
- Prefer redacted snippets for triage over full-content retention.
- Apply a documented database retention policy appropriate to your organization’s requirements.

Access control:
- Minimize the number of `org_admin` users.
- Grant `auditor` only to users responsible for compliance/review workflows.
- Use `operator` for integration/testing tasks; do not grant export rights unless necessary.

Monitoring:
- Alert on `PROMPT_INJECTION_SUSPECTED`, `EMBEDDED_INJECTION_SUSPECTED`, `SENSITIVE_REQUEST`, and `DOS_RISK` flags.
- Monitor Redis availability; failing open means rate limiting is temporarily disabled.
