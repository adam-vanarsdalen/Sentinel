# Sentinel Stack

Enterprise AI governance platform. Seven layers: ingestion → routing → enforcement → reasoning → grounding → anomaly detection → compliance output.

## Stack
- Backend: FastAPI + SQLAlchemy async + PostgreSQL + Redis
- Frontend: Next.js 14 + TypeScript + Tailwind + Recharts
- Dev: Docker Compose

## Commands
- `docker compose up -d` — start all services
- `cd backend && uvicorn main:app --reload` — run backend locally
- `cd frontend && npm run dev` — run frontend locally
- `cd backend && pytest` — run tests
- `cd backend && alembic upgrade head` — run migrations

## Session recovery
Read PROJECT_STATE.md at the start of every session before writing any code.
Update PROJECT_STATE.md after completing each build step.

## Skills — load before each relevant step
- Steps 3–10: skills/layer-interface.md
- Steps 5, 11, 12: skills/kill-switch-state-machine.md
- Steps 9, 13: skills/compliance-mapper.md
- Steps 5, 8, 9: skills/test-coverage-matrix.md

To load a skill at the start of a step: read the file and internalize its contents
before writing any code. The skill files are canonical — they override any assumption
you might otherwise make about interfaces, state machines, control IDs, or test requirements.

## Architecture rules
- Every request gets a UUID4 request_id at Layer 1. This ID appears in every log, alert, and audit entry
- Layer 3 enforcement runs BEFORE model execution, not after. This is the core architectural differentiator
- The audit_log table is append-only. No UPDATE or DELETE operations ever
- Kill switch state lives in Redis. State transitions write to audit_log BEFORE writing to Redis
- Anomaly baselines use 7-day rolling windows with 1-hour granularity
- All regulation control IDs must match skills/compliance-mapper.md exactly — no abbreviations
- All layer function signatures must match skills/layer-interface.md exactly — no deviations

## Human review checkpoints (do not skip)
- After step 5 (Layer 3): verify kill switch state machine + all Layer 3 test cases green
- After step 8 (Layer 6): verify graduated containment end-to-end + all Layer 6 test cases green
- After step 9 (Layer 7): verify append-only enforcement + gap analysis + all Layer 7 test cases green
