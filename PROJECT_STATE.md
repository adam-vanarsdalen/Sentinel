# PROJECT_STATE.md — Sentinel Stack

## Current step: 15 — End-to-end demo

## Completed steps
- [x] Step 1: Scaffold directory structure, skill files, CLAUDE.md, docker-compose.yml, .env.example, git init
- [x] Step 2: Infrastructure — Dockerfiles, Alembic migration (all tables + append-only enforcement), requirements.txt
- [x] Step 3: Layer 1 Ingestion — layer1_ingestion.py (tiktoken token estimation, OpenAI/Anthropic normalization)
- [x] Step 4: Layer 2 Routing — layer2_routing.py (RBAC, budget, model selection)
- [x] Step 5: Layer 3 Enforcement + Kill Switch — layer3_enforcement.py, services/kill_switch.py (exact state machine spec)
- [x] Step 6: Layer 4 Reasoning — layer4_reasoning.py (multi-provider, tool-call interception loop)
- [x] Step 7: Layer 5 Grounding — layer5_grounding.py (claim scoring, human review escalation)
- [x] Step 8: Layer 6 Anomaly — layer6_anomaly.py (z-score, graduated containment, state snapshot)
- [x] Step 9: Layer 7 Compliance — layer7_compliance.py, regulatory/ (EU/NIST/CO/HIPAA mappings, gap analysis)
- [x] Step 10: Pipeline orchestrator — services/pipeline.py
- [x] Step 11: API routers + WebSocket — all api/ routers, 3 WS endpoints in main.py
- [x] Step 12: Frontend dashboard — MetricCards, LayerHealth, ThroughputChart, RequestFeed, AlertPanel, AuditTail, KillSwitchButton
- [x] Step 13: Frontend remaining pages — agents, policies, audit, compliance + PackageBuilder
- [x] Step 14: Demo scripts — seed_demo.py, simulate_traffic.py, run_anomaly_scenario.py

## Tests passing
74/74 — Layer 3 (27), Layer 6 (21), Layer 7 (26) all green per test-coverage-matrix.md

## Human review checkpoints
- Layer 3: ✓ Kill switch state machine implemented per spec; audit-first enforced in KillSwitchService
- Layer 6: ✓ Graduated containment (log/throttle/pause/terminate); z-score thresholds from config
- Layer 7: ✓ Append-only enforced via DB migration REVOKE; gap analysis names producing layer

## Next step: Step 15 — End-to-end demo
- `docker compose up` to start all services
- Run migrations: `cd backend && alembic upgrade head`
- Run seed: `python scripts/seed_demo.py`
- Run traffic: `python scripts/simulate_traffic.py`
- Verify dashboard at http://localhost:3000
- Run anomaly scenario: `python scripts/run_anomaly_scenario.py`
- Generate compliance package from UI and download PDF

## Architecture decisions
- Backend: FastAPI + SQLAlchemy async + asyncpg + PostgreSQL 16 + Redis 7
- Frontend: Next.js 14 App Router + TypeScript + Tailwind + Recharts
- Alembic for migrations, pydantic-settings for config
- Layer 3 enforcement fires BEFORE model call — checked in pipeline.py before layer4_reason()
- Kill switch: Redis = current state source of truth; audit_log = history source of truth
- Anomaly baselines: count-based Welford online algorithm stored in Redis JSON per agent
