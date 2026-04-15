# Quickstart

Run Sentinel locally with the default `general` preset.

## Prerequisites

- Docker Desktop running
- Terminal in repo root

## 1. Configure environment

```bash
cp .env.example .env
```

Recommended defaults for first run:

- `SENTINEL_PRESET=general`
- `NEXT_PUBLIC_SENTINEL_PRESET=general`
- `SEED_DEMO=1`

## 2. Start the stack

```bash
docker compose up --build
```

## 3. Open the app

- UI: `http://localhost:${FRONTEND_PORT:-3000}`
- API docs: `http://localhost:${BACKEND_PORT:-8000}/docs`
- Metrics: `http://localhost:${BACKEND_PORT:-8000}/metrics`

Demo logins:

- `admin@demoorg.com` / `ChangeMe!12345`
- `platform-admin@example.com` / `ChangeMe!12345`

## 4. Switch to legal preset (SentinelLaw)

Set and restart:

```bash
SENTINEL_PRESET=legal
NEXT_PUBLIC_SENTINEL_PRESET=legal
```

Legal demo login:

- `admin@demolaw.com` / `ChangeMe!12345`

## 5. Health checks

- `GET /health` or `GET /healthz`
- `GET /ready` or `GET /readyz`

## 6. Optional smoke test

```bash
./scripts/smoke-test.sh
```

## 7. Stop

```bash
docker compose down
```

Use `docker compose down -v` only when you intentionally want to reset local data.
