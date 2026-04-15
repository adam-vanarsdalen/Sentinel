# Sentinel Architecture

## System overview

Sentinel is a governance layer between enterprise applications and LLM providers. It enforces organization policy at request time, records audit metadata, and exposes admin/reporting surfaces.

## Major components

- `frontend/` (Next.js): admin console for auth, policy, provider config, users, logs, and reports
- `backend/` (FastAPI): gateway API, policy evaluation, tenant APIs, audit/report endpoints
- `postgres`: persistent data for tenants, users, policy versions, provider configs, API keys, audit events, eval runs
- `redis`: rate-limit counters and broker/result backend for async work
- `worker` (Celery): asynchronous evaluation execution
- `config/presets/`: preset manifests, terminology, copy, roles, risk taxonomy, demo seed profiles

## Trust boundaries

- Public/browser boundary: user-facing UI and auth endpoints
- Admin/API boundary: JWT-authenticated tenant and platform administration
- Gateway boundary: API-key-authenticated machine-to-machine inference traffic
- Provider boundary: outbound calls to approved model providers (OpenAI/Anthropic/Azure OpenAI/mock)
- Data boundary: tenant-scoped records in shared PostgreSQL

## Core request flow

1. Client app sends `POST /v1/chat/completions` with tenant API key.
2. Backend resolves tenant context from API key.
3. Policy engine runs preflight checks (model/provider approvals, rule checks, risk heuristics, limits).
4. If allowed, provider routing selects approved provider/model and executes request.
5. Postflight checks run output/risk validations.
6. Backend writes structured audit event(s) and returns response or policy/error envelope.

## Tenant and preset model

- Tenant isolation is enforced server-side in query scope and writes.
- Presets (`general`, `legal`, `finance`, `healthcare`) do not fork core logic.
- Presets adjust visible terminology/product framing, demo defaults, and risk taxonomy overlays.
- Sentinel is default product framing; SentinelLaw remains legal preset behavior.

## Provider routing role

Provider routing enforces tenant-approved provider/model controls and optional resilience settings (timeouts/retries/fallback) while maintaining audit traceability for each routing decision.

See supplemental doc: `docs/ProviderRouting.md`.

## Policy engine role

Policy evaluation determines allow/block/flag/review outcomes based on tenant rules, risk signals, and limits.

See `docs/POLICY_ENGINE.md`.

## Audit and logging role

Sentinel captures tenant-scoped governance events with integrity-oriented design (append-only posture, hash-chain verification support, export paths).

See `docs/AUDIT_AND_LOGGING.md`.
