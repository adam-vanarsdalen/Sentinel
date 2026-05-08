# Sentinel Polish Backlog (Prioritized)

Date: 2026-02-26

## P0 — Must Fix (pilot credibility / security / data correctness)

### P0-1: Eliminate invalid seeded emails and prevent recurrence
- Component: backend + seed
- User impact: login/session and admin pages can break unexpectedly; confusing errors.
- Security/compliance impact: noisy errors reduce trust; may block access to audit data.
- Likely files:
  - `backend/app/core/seed.py`
  - `backend/app/db/models.py`
  - `backend/app/api/routes/users.py`
- Acceptance criteria:
  - Seeded demo users always use valid email domains (e.g., `@example.com`).
  - If an existing DB contains invalid emails from prior runs, system either:
    - migrates/repairs them safely in a one-time migration, or
    - clearly logs and skips invalid records in non-critical responses.

### P0-2: Enforce RBAC on backend endpoints (no UI-only authorization)
- Component: backend
- User impact: prevents users from performing actions beyond their role.
- Security/compliance impact: critical; reduces risk of privilege escalation.
- Likely files:
  - `backend/app/api/deps.py`
  - `backend/app/api/routes/*.py`
- Acceptance criteria:
  - All admin routes enforce role checks server-side.
  - Add negative tests for each restricted action (403).

### P0-3: Add correlation/request identifiers to backend logs and audit events
- Component: backend + observability
- User impact: faster incident response and investigations.
- Security/compliance impact: improves auditability and traceability.
- Likely files:
  - `backend/app/core/logging.py` (or equivalent)
  - `backend/app/core/metrics.py`
  - `backend/app/db/models.py` (AuditEvent)
- Acceptance criteria:
  - Every HTTP request has a `request_id` in structured logs.
  - Audit events include a request identifier for correlation.
  - No secrets or raw prompts appear in app logs by default.

### P0-4: Make audit events strictly append-only (immutability guard)
- Component: backend + DB
- User impact: preserves audit trail integrity.
- Security/compliance impact: critical for audits.
- Likely files:
  - `backend/app/db/models.py`
  - `backend/app/api/routes/audit.py`
- Acceptance criteria:
  - No endpoint updates or deletes audit events.
  - DB constraints or application safeguards prevent mutation.

### P0-5: Health/readiness endpoints documented and used by compose
- Component: backend + deployment
- User impact: smoother startup and clearer operational status.
- Security/compliance impact: improves reliability.
- Likely files:
  - `backend/app/api/routes/health.py` (add if missing)
  - `docker-compose.yml`
  - `docs/DEPLOYMENT.md`
- Acceptance criteria:
  - `GET /healthz` and `GET /readyz` exist and are documented.
  - Compose uses healthchecks where appropriate.

## P1 — Should Fix (enterprise-clean polish / testing confidence)

### P1-1: Standardize API error shape (consistent, user-friendly)
- Component: backend + frontend
- User impact: clearer errors and fewer “mystery failures”.
- Security/compliance impact: reduces accidental leakage in errors.
- Likely files:
  - `backend/app/api/middleware/errors.py` (or add)
  - `frontend/src/lib/http.ts`
- Acceptance criteria:
  - Errors are consistent and include a stable `code`, `message`, and optional `details`.
  - Frontend displays a friendly message with optional “Show details” for admins.

### P1-2: Expand backend tests for RBAC, tenant isolation, policy blocks, and hashing
- Component: backend tests
- User impact: fewer regressions and more confidence.
- Security/compliance impact: proves tenant isolation and key safety.
- Likely files:
  - `backend/tests/*`
- Acceptance criteria:
  - Add RBAC negative tests (403) for restricted endpoints.
  - Add API key hashing test (token not stored; only hash+salt).

### P1-3: Expand Playwright smoke tests (export + tenant context)
- Component: frontend tests
- User impact: catches broken flows before demos.
- Security/compliance impact: ensures role gating doesn’t regress.
- Likely files:
  - `frontend/tests/*`
  - `frontend/playwright.config.ts`
- Acceptance criteria:
  - E2E covers: login → dashboard → logs export → policy dry-run → create/revoke key.

### P1-4: Improve “first-time user” empty states and guided steps
- Component: frontend
- User impact: faster onboarding for compliance/ops users.
- Likely files:
  - `frontend/src/app/(app)/*/page.tsx`
- Acceptance criteria:
  - When no data exists, each page explains what to do next.
  - Key workflows are visible (create key, send a request, view logs).

### P1-5: Worker runs as non-root (container hygiene)
- Component: infra
- User impact: none; posture improvement.
- Security/compliance impact: improved least privilege.
- Likely files:
  - `backend/Dockerfile`
  - `docker-compose.yml`
- Acceptance criteria:
  - Celery worker runs as non-root user in the container.

## P2 — Nice to Have (future-ready, not required for pilot success)

### P2-1: Optional OpenTelemetry traces from gateway → provider
- Component: backend observability
- User impact: improved troubleshooting.
- Likely files:
  - `backend/app/core/otel.py` (new)
- Acceptance criteria:
  - Minimal OTel instrumentation behind env toggle.

### P2-2: Saved views backed by DB (not local-only)
- Component: backend + frontend
- User impact: shared saved views among auditors.
- Acceptance criteria:
  - Saved filters stored per user/tenant in DB with RBAC controls.
