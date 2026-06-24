# Sentinel Stack

**Open-source enterprise AI governance platform.** Every model call, tool invocation, and data access passes through a 7-layer enforcement pipeline before execution.

---

## Why Sentinel?

Most AI gateway solutions handle routing, rate limiting, and basic content filtering. Sentinel adds three capabilities that are absent from Bifrost, TrueFoundry, Databricks Unity AI Gateway, Portkey, and Credo AI:

| Capability | What it does | Where others stop |
|---|---|---|
| **Pre-call Enforcement** (Layer 3) | Kill switch, purpose binding, action limits, and forbidden-endpoint checks run *before* the model executes | After-the-fact logging |
| **Behavioral Anomaly Detection** (Layer 6) | Rolling 7-day baselines per agent; z-score deviations trigger graduated containment (throttle → pause → terminate) automatically | Static rate limits |
| **Regulation-Mapped Audit** (Layer 7) | Every request writes an append-only audit entry linked to specific EU AI Act articles, NIST AI RMF controls, HIPAA clauses, and Colorado SB205 sections | Generic logs |

---

## The 7-Layer Pipeline

```
Incoming request
      │
      ▼
┌─────────────────────────────────────────────────────────┐
│  Layer 1 │ Ingestion        Normalize, tag, validate     │
│  Layer 2 │ Routing          Model selection, RBAC, budget│
│  Layer 3 │ Enforcement ★    Kill switch, purpose binding │  ← runs BEFORE model
│  Layer 4 │ Reasoning        Provider API execution        │
│  Layer 5 │ Grounding        RAG verify, hallucination     │
│  Layer 6 │ Anomaly ★        Baseline drift, containment  │  ← auto-escalates
│  Layer 7 │ Compliance ★     Append-only regulation audit  │  ← immutable evidence
└─────────────────────────────────────────────────────────┘
      │
      ▼
Response + audit entry
```

★ = novel differentiator

---

## Quick Start

**Requirements:** Docker, Docker Compose, Python 3.11+

```bash
git clone https://github.com/adam-vanarsdalen/Sentinel.git
cd Sentinel

cp .env.example .env
# Add your ANTHROPIC_API_KEY or OPENAI_API_KEY

docker compose up -d
cd backend && alembic upgrade head && cd ..
python scripts/seed_demo.py
```

Open **http://localhost:3000** — the dashboard is live.

Run demo traffic in a second terminal:

```bash
python scripts/simulate_traffic.py        # continuous mixed traffic
python scripts/run_anomaly_scenario.py    # scripted anomaly + kill switch demo
```

---

## Features

### Layer 3 — Pre-call Enforcement
- **Kill switch** with four states: `active → throttled → paused → terminated`
- **Action limits** — block an agent after N tool calls in a session
- **Purpose binding** — block data class access outside the agent's declared purpose
- **Forbidden endpoints** — block tool calls to disallowed URLs before the model sees a result
- All checks run before the model API call; blocked requests never touch a provider

### Layer 6 — Anomaly Detection
- **Welford online algorithm** tracks rolling mean and variance per agent over 7 days
- Dimensions: request cost, latency, error rate, new data classes, new tool patterns
- Graduated automatic containment based on z-score:
  - ≥ 2.5σ → log
  - ≥ 3.5σ → throttle (1 call / 10 s)
  - ≥ 5.0σ → pause (queue for human review)
  - ≥ 7.0σ → terminate
- State snapshot (last 20 actions + in-flight request IDs) captured at containment time
- Cross-agent correlation detection within a tenant

### Layer 7 — Compliance Output
- **Append-only audit log** enforced at the PostgreSQL role level (`REVOKE UPDATE, DELETE`)
- Every entry maps to specific regulatory controls
- One-click evidence package generation covering EU AI Act, NIST AI RMF, HIPAA, Colorado SB205
- Gap analysis: identifies which controls have zero qualifying evidence in a time range
- Export formats: JSON, PDF (WeasyPrint), CSV

### Dashboard
- Real-time WebSocket feeds: live request table, alerts panel, audit tail
- 7-layer health bars (differentiator layers highlighted)
- Throughput chart (30-second rolling window)
- Two-stage kill switch button (arm → confirm)

---

## Tech Stack

| Component | Technology |
|---|---|
| Backend | FastAPI 0.115 · SQLAlchemy 2 async · asyncpg |
| Database | PostgreSQL 16 |
| Cache / State | Redis 7 |
| Frontend | Next.js 14 App Router · TypeScript · Tailwind CSS · Recharts |
| Migrations | Alembic |
| Testing | pytest + pytest-asyncio (74 tests) |
| Deployment | Docker Compose |

---

## API

Sentinel is a drop-in proxy — point your existing SDK at it:

```bash
# OpenAI-compatible
POST http://localhost:8000/v1/chat/completions

# Anthropic-compatible
POST http://localhost:8000/v1/messages
```

Management endpoints:

| Method | Path | Description |
|---|---|---|
| POST | `/api/agents/` | Register an agent |
| POST | `/api/policies/` | Create a governance policy |
| POST | `/api/kill_switch/fire` | Terminate an agent (operator) |
| POST | `/api/kill_switch/resume` | Resume a contained agent |
| POST | `/api/compliance/generate` | Generate evidence package |
| GET | `/api/audit/` | Query append-only audit log |
| GET | `/api/audit/export/csv` | Export audit as CSV |
| GET | `/api/dashboard/metrics` | Aggregated 24-hour metrics |

WebSocket feeds: `/ws/alerts` · `/ws/requests` · `/ws/metrics`

Full reference: [docs/api-reference.md](docs/api-reference.md)

---

## Regulatory Coverage

| Regulation | Controls Mapped |
|---|---|
| EU AI Act | Articles 9, 11, 12, 13, 14, 15 |
| NIST AI RMF | GOVERN-1.1/1.2/1.4/5.1/6.1 · MAP-1.1 · MEASURE-2.2/2.5 · MANAGE-1.3/2.2/2.4 |
| HIPAA | 164.308(a)(3) · 164.312(b) |
| Colorado SB205 | Sections 6-1-1702(a)(b)(c) |

Full mapping: [docs/compliance.md](docs/compliance.md)

---

## Project Structure

```
sentinel-stack/
├── backend/
│   ├── layers/          # 7-layer pipeline (layer1_ingestion.py … layer7_compliance.py)
│   ├── services/        # Kill switch, anomaly engine, compliance generator
│   ├── api/             # FastAPI routers
│   ├── models/          # SQLAlchemy ORM (6 tables)
│   ├── regulatory/      # EU AI Act, NIST, HIPAA, Colorado SB205 mappers
│   └── tests/           # 74 tests across all layers
├── frontend/
│   └── src/
│       ├── app/         # Dashboard, Agents, Policies, Audit, Compliance pages
│       └── components/  # MetricCards, LayerHealth, KillSwitchButton, …
├── scripts/
│   ├── seed_demo.py          # 6 demo agents + policies
│   ├── simulate_traffic.py   # Mixed realistic traffic
│   └── run_anomaly_scenario.py  # Scripted demo scenarios
└── docker-compose.yml
```

---

## Running Tests

```bash
cd backend
pip install -r requirements.txt
pytest --tb=short
```

74 tests across Layer 3 (27), Layer 6 (21), Layer 7 (26), pipeline, kill switch, anomaly engine, and compliance generator.

---

## Configuration

All settings are in `.env` (copy from `.env.example`):

```env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql+asyncpg://sentinel:sentinel@localhost:5432/sentinel
REDIS_URL=redis://localhost:6379/0

# Anomaly thresholds (sigma)
ANOMALY_LOG_SIGMA=2.5
ANOMALY_THROTTLE_SIGMA=3.5
ANOMALY_PAUSE_SIGMA=5.0
ANOMALY_TERMINATE_SIGMA=7.0

# Grounding thresholds
GROUNDING_WARN_THRESHOLD=0.8
GROUNDING_BLOCK_THRESHOLD=0.5
```

---

## Documentation

- [Architecture](docs/architecture.md) — pipeline design, data flow, key invariants
- [Layer Reference](docs/layers.md) — inputs, outputs, and behavior of all 7 layers
- [API Reference](docs/api-reference.md) — all endpoints with request/response shapes
- [Compliance Mapping](docs/compliance.md) — regulation controls per layer
- [Contributing](CONTRIBUTING.md) — development setup, conventions, PR process

---

## License

MIT
