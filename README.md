# Sentinel

Source available for evaluation only. Reuse, modification, redistribution, and commercial or production use are prohibited without written permission from Sentinel.

Governed AI infrastructure for enterprise workflows.

Sentinel is a multi-tenant AI governance platform that sits between applications and model providers, enforces organizational policy, flags risky usage, and produces audit-ready records. Sentinel is the shared product; `SentinelLaw` is a legal preset/vertical edition on the same core.

## Why Sentinel

Enterprise AI adoption is moving faster than governance controls. Teams need a practical layer that can:

- enforce policy before requests hit a model
- apply post-response checks and review gates
- keep auditable traces by tenant, user, key, provider, and outcome
- preserve flexibility across industries with one shared core

## What It Does

- tenant-scoped gateway for model requests
- policy engine with allow/block/flag/review outcomes
- provider routing controls and model allowlists
- first-class providers: OpenAI, Anthropic, Azure OpenAI, and Ollama
- security/risk signals (prompt injection, sensitive data exposure, misuse patterns)
- immutable audit trail and exportable reporting
- preset-driven terminology and demo framing (`general`, `legal`, `finance`, `healthcare`)

## Who It Is For

- platform engineering teams building governed AI workflows
- security/compliance teams needing operational controls and auditability
- product teams requiring policy-aware AI integrations

## Architecture (High Level)

- `frontend/` Next.js admin console
- `backend/` FastAPI gateway + policy + audit APIs
- `postgres` persistent state for tenancy, policy, users, keys, audit metadata
- `redis` rate-limiting and queue backend
- `celery` worker for async evaluation tasks
- `config/presets/` product/preset terminology, copy, role labels, risk taxonomy, and demo seeds

See [ARCHITECTURE](docs/ARCHITECTURE.md) for detailed request flow and trust boundaries.

## Stack

- Backend: FastAPI, SQLAlchemy, Alembic, Celery
- Frontend: Next.js, TypeScript, Tailwind
- Data/Infra: PostgreSQL, Redis, Docker Compose

## Quickstart

```bash
cp .env.example .env
docker compose up --build
```

Optional local Ollama defaults are already scaffolded in `.env.example`:

- `OLLAMA_ENABLED=0`
- `OLLAMA_BASE_URL=http://localhost:11434/v1/`
- `OLLAMA_API_KEY=` (optional; kept local and never committed)
- `OLLAMA_DEFAULT_MODEL=gpt-oss:120b-cloud`

Then open:

- Admin UI: `http://localhost:3000`
- API docs: `http://localhost:8000/docs`
- Metrics: `http://localhost:8000/metrics`

Default demo credentials (from `.env.example`):

- Org admin: `admin@demoorg.com` / `ChangeMe!12345`
- Platform admin: `platform-admin@example.com` / `ChangeMe!12345`

See [QUICKSTART](docs/QUICKSTART.md) for preset-specific run modes and validation steps.

## Product Editions

- `general` (default): Sentinel shared enterprise framing
- `legal`: SentinelLaw legal terminology and legal demo profile
- `finance`: regulated-finance framing
- `healthcare`: clinical/safety framing

Preset behavior is documented in supplemental docs: `docs/presets.md` and `docs/demo_modes.md`.

## Core Documentation

- [QUICKSTART](docs/QUICKSTART.md)
- [ARCHITECTURE](docs/ARCHITECTURE.md)
- [API](docs/API.md)
- [MODEL_CATALOG_AUDIT](docs/MODEL_CATALOG_AUDIT.md)
- [MODEL_PROVIDER_INTEGRATION_NOTES](docs/MODEL_PROVIDER_INTEGRATION_NOTES.md)
- [POLICY_ENGINE](docs/POLICY_ENGINE.md)
- [AUDIT_AND_LOGGING](docs/AUDIT_AND_LOGGING.md)
- [THREAT_MODEL](docs/THREAT_MODEL.md)
- [DEPLOYMENT](docs/DEPLOYMENT.md)
- [DEMO_SCRIPT](docs/DEMO_SCRIPT.md)
- [RELEASE_CHECKLIST](docs/RELEASE_CHECKLIST.md)
- [DECISIONS](docs/DECISIONS.md)
- [ROADMAP](docs/ROADMAP.md)

## Roadmap Snapshot

- Near term: harden policy workflow UX, stronger audit/report ergonomics, preset expansion quality
- Mid term: deeper enterprise controls (SSO/SAML, stronger compliance integrations)
- Longer term: multi-region deployment hardening and broader governance automation

See [ROADMAP](docs/ROADMAP.md) for detail.

## Security and Governance Orientation

Sentinel is built as a governance/control layer, not a replacement for legal/compliance judgment.

- default posture avoids raw prompt/response storage
- audit traces include deterministic metadata and integrity-oriented controls
- tenancy and role boundaries are enforced server-side

See [SECURITY](SECURITY.md) and [THREAT_MODEL](docs/THREAT_MODEL.md).

## Assets

Project media belongs in:

- `assets/screenshots/`
- `assets/diagrams/`
- `assets/demo/`
