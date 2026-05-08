# Repo Consolidation Summary

Date: 2026-04-14T17:18:10-0400

## Canonical repo root

The canonical repo root is now:

`~/Desktop/Sentinel/Sentinel.1`

All required generalized Sentinel code/config/docs are consolidated there.

## Folders audited

- `~/Desktop/Sentinel/Sentinel.1`
- `~/Desktop/Sentinel/config`
- `~/Desktop/Sentinel/docs`

## What was moved/merged

- Copied `~/Desktop/Sentinel/config/presets/*` into `~/Desktop/Sentinel/Sentinel.1/config/presets/`
- Copied `~/Desktop/Sentinel/docs/generalization_plan.md` into `~/Desktop/Sentinel/Sentinel.1/docs/generalization_plan.md`
- Updated preset path resolution to internal repo paths:
  - `backend/app/core/presets.py`
  - `frontend/src/lib/app-config-server.ts`
- Updated docs references from external `../config/presets/...` to internal `config/presets/...`:
  - `README.md`
  - `docs/presets.md`
  - `docs/demo_modes.md`

## What was removed/ignored

- Removed duplicate outer folders after merge:
  - `~/Desktop/Sentinel/config`
  - `~/Desktop/Sentinel/docs`
- Removed non-source artifacts from `Sentinel.1`:
  - `frontend/node_modules`
  - `frontend/.next`
  - Playwright reports/test outputs under `frontend/` and `artifacts/validate-release/`
  - Python `__pycache__` and `*.pyc`
  - macOS `.DS_Store`
- Updated `.gitignore` with additional generated artifact patterns:
  - `frontend/playwright-report/`
  - `frontend/test-results/`
  - `artifacts/validate-release/playwright-report/`
  - `artifacts/validate-release/test-results/`
  - `*.tsbuildinfo`

## Consolidation caveats

- `Sentinel.1` currently has no `.git/` directory (repository not initialized in this folder yet).
- A local runtime `.env` file exists at repo root; keep it uncommitted (already ignored by `.gitignore`).
- Backend/frontend dependencies were installed temporarily for validation and then removed from the working tree (`backend/.venv`, `frontend/node_modules`, `frontend/.next`).

## Validation performed

From `~/Desktop/Sentinel/Sentinel.1`:

- Backend compile sanity: passed
  - `python3 -m compileall backend/app`
- Backend test suite: passed after one wording-alignment test update
  - `. backend/.venv/bin/activate && python -m pytest -q`
  - Result: `85 passed`
- Frontend lint: passed
  - `cd frontend && npm run lint`
- Frontend typecheck: passed
  - `cd frontend && npx tsc --noEmit`
- Frontend production build: passed
  - `cd frontend && npm run build`

Note: Backend dependencies were installed in a local Python 3.11 venv due Python 3.14 compatibility issues with `psycopg-binary==3.2.3`.

## Exact run commands

From repo root:

```bash
cd ~/Desktop/Sentinel/Sentinel.1
cp .env.example .env
docker compose up --build
```

Default generalized Sentinel mode (`general`) is already set in `.env.example`.

To run legal mode:

```bash
cd ~/Desktop/Sentinel/Sentinel.1
SENTINEL_PRESET=legal NEXT_PUBLIC_SENTINEL_PRESET=legal docker compose up --build
```

## Exact GitHub init/push commands

If `Sentinel.1` is not yet a git repo:

```bash
cd ~/Desktop/Sentinel/Sentinel.1
git init
git add .
git commit -m "Consolidate generalized Sentinel repo into Sentinel.1"
git branch -M main
git remote add origin git@github.com:<your-org-or-user>/<your-repo>.git
git push -u origin main
```

If remote uses HTTPS:

```bash
git remote add origin https://github.com/<your-org-or-user>/<your-repo>.git
git push -u origin main
```
