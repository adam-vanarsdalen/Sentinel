# Sentinel Frontend (Next.js)

## Requirements
- Node.js 20+ (for local runs outside Docker), or use `docker compose up --build` from repo root.

## Environment
Frontend reads:
- `NEXT_PUBLIC_API_BASE_URL` (browser-side; shown in `.env.example`)
- `API_BASE_URL` (server-side route handlers; in Docker Compose should be `http://backend:8000`)
- `NEXT_PUBLIC_SENTINEL_PRESET` / `SENTINEL_PRESET` (default visible preset framing)

For local dev, copy `.env.example` to `.env` at the repo root and adjust `FRONTEND_PORT`/`BACKEND_PORT` if you have conflicts.

## Run (recommended)
From repo root:
- `docker compose up --build`

Then open the UI at `http://localhost:${FRONTEND_PORT:-3000}`.

## Demo login
Demo users are configured via `.env.example`/`.env` and seeded by the backend when `SEED_DEMO=1`.
- Default shared demo: `admin@demoorg.com` / `ChangeMe!12345`
- Legal preset demo: `admin@demolaw.com` / `ChangeMe!12345`

## E2E smoke test (Playwright)
Prereqs:
- `docker compose up --build` running
- Install Playwright browsers once: `cd frontend && npx playwright install`

Run:
- `cd frontend && PLAYWRIGHT_BASE_URL=http://localhost:3000 E2E_BACKEND_BASE_URL=http://localhost:8000 E2E_EMAIL=admin@demoorg.com E2E_PASSWORD='ChangeMe!12345' npm run test:e2e`

## Troubleshooting
- If login succeeds but pages show “Select a tenant…”, you are logged in as `super_admin`. Pick a tenant in the top bar.
- If you changed demo passwords after first run, set `DEMO_PASSWORD_SYNC=1` and restart the backend container.
