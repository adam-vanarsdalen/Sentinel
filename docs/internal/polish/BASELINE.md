# Baseline (Pre-Polish)

Date: 2026-02-26

## Services and Ports (local)
Current `docker compose` services:
- `postgres` (internal only)
- `redis` (internal only)
- `backend` (FastAPI) — host port `8001` → container `8000`
- `frontend` (Next.js) — host port `3001` → container `3000`
- `worker` (Celery) — internal only

Notes:
- Host ports are configurable via `.env` (`BACKEND_PORT`, `FRONTEND_PORT`). See `.env.example`.

## Baseline Checks Run
### App boot
- `docker compose up --build` starts all services successfully.
- `frontend` reports “Ready”.
- `backend` reports “Application startup complete”.

### Backend tests
- `docker compose run --rm --no-deps backend pytest -q`
- Result: **3 passed**
- Warnings observed:
  - `pytest-asyncio` deprecation warning about fixture loop scope.
  - `passlib` / `argon2` packaging metadata deprecation warnings.

### Frontend build
- `docker compose run --rm --no-deps frontend npm run build`
- Result: **success** (Next.js build + typecheck)

## Known Issues Observed (P0 candidates)
### Backend response validation error in logs (invalid demo email domain)
Observed a `fastapi.exceptions.ResponseValidationError` referencing an email like `tenant-admin@demohealth.local` (reserved/special-use domain rejected by email validation).

Impact:
- Can cause server errors on endpoints that return user objects validated as emails.
- Creates noisy logs and reduces reliability during demos.

Likely area:
- Demo seed data and/or persisted DB rows created before demo emails were changed to `@example.com`.

### Worker runs as root (container warning)
Celery worker logs a warning about running with superuser privileges.

Impact:
- Not ideal for “enterprise-clean” posture, even in a pilot.

### Frontend error reporting is “pilot verbose”
The app error boundary currently displays the raw error message to the user.

Impact:
- Helps debug, but may expose confusing messages to non-technical users.

## UX Notes (baseline)
- First-time user path is functional, but needs clearer empty states and “what to do next” guidance in key pages.
- Audit Logs UX is functional and fast, but needs consistency around saved views, filters, and export feedback patterns.

