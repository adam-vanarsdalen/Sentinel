# Sentinel

Sentinel is an AI governance gateway for regulated teams. It sits between internal applications and model providers, applies organization policy before and after model calls, and records audit-ready evidence for security, compliance, and operations teams.

Sentinel is the core product identity. SentinelLaw is included as the legal preset for law-firm terminology, demo data, and policy templates.

> Source available for evaluation only. Reuse, modification, redistribution, and commercial or production use are prohibited without written permission from the repository owner, adam-vanarsdalen.

## Why Sentinel

Regulated organizations are adopting AI faster than their controls can keep up. Sentinel provides a practical enforcement layer for teams that need to use model providers without losing visibility, policy control, or auditability.

Sentinel helps teams:

- enforce provider, model, and usage policy before requests reach an LLM
- flag or block risky prompts and responses using tenant-scoped rules
- route traffic through approved model providers and model allowlists
- keep structured audit records by tenant, user, API key, provider, model, and outcome
- separate durable governance controls from vertical terminology and demo presets

## What It Does

- OpenAI-compatible gateway path for governed chat-completion requests
- Multi-tenant admin console for policies, providers, users, API keys, audit logs, and reports
- Policy engine with `allow`, `block`, `flag`, and review-oriented outcomes
- Provider routing for OpenAI, Anthropic, Azure OpenAI, Ollama, and local mock workflows
- Risk signals for prompt injection, sensitive data exposure, misuse patterns, and policy violations
- Immutable, hash-chained audit trail with export and reporting paths
- Preset system for general, legal, finance, and healthcare demo/terminology profiles

## Who It Is For

- Platform engineering teams adding governed AI access to internal tools
- Security and compliance teams that need operational controls and reviewable evidence
- Product teams integrating LLMs into regulated workflows
- Pilot teams evaluating model-provider governance before broader AI rollout

## Architecture

Sentinel is a Docker Compose application with a FastAPI backend, Next.js frontend, PostgreSQL datastore, Redis broker/cache, and Celery worker.

```text
application clients
        |
        v
Sentinel gateway -> policy engine -> provider router -> model providers
        |
        v
audit trail / reporting / admin console
```

Repository layout:

- `backend/`: FastAPI gateway, admin APIs, policy evaluation, provider integrations, audit/reporting services
- `frontend/`: Next.js admin console
- `config/presets/`: preset manifests, terminology, demo organizations, role labels, and risk taxonomy
- `docs/`: public technical documentation
- `assets/`: diagrams, screenshots, and demo media

See [Architecture](docs/ARCHITECTURE.md) for request flow, trust boundaries, and component details.

Terminology note: the general product uses "organization" for tenant-facing administration. The legacy `/firms` admin route remains available for compatibility, and `/organizations` is the public/default route alias. The legal preset continues to use "firm" where appropriate.

## Quickstart

Prerequisites:

- Docker Desktop or Docker Engine with Compose
- Terminal in the repository root

```bash
cp .env.example .env
docker compose up --build
```

Then open:

- Admin UI: `http://localhost:3000`
- API docs: `http://localhost:8000/docs`
- Metrics: `http://localhost:8000/metrics`

Default demo credentials from `.env.example`:

- Organization admin: `admin@demoorg.com` / `ChangeMe!12345`
- Platform admin: `platform-admin@example.com` / `ChangeMe!12345`

These credentials are for local development only. Production configuration rejects demo seeding and default demo passwords.

See [Quickstart](docs/QUICKSTART.md) for preset-specific run modes and validation steps.

## Presets

Sentinel uses presets to keep the governance platform shared while adapting labels, sample data, policy templates, and demo framing for specific environments.

- `general`: default Sentinel product framing
- `legal`: SentinelLaw legal preset
- `finance`: regulated-finance framing
- `healthcare`: clinical and safety-oriented framing

See [Presets](docs/presets.md), [Demo Modes](docs/demo_modes.md), and [SentinelLaw Legal Preset](docs/legal-preset/README.md).

## Documentation

- [Docs Index](docs/README.md)
- [Quickstart](docs/QUICKSTART.md)
- [Architecture](docs/ARCHITECTURE.md)
- [API](docs/API.md)
- [Policy Engine](docs/POLICY_ENGINE.md)
- [Provider Routing](docs/ProviderRouting.md)
- [Audit and Logging](docs/AUDIT_AND_LOGGING.md)
- [Security Overview](docs/SecurityOverview.md)
- [Threat Model](docs/THREAT_MODEL.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Roadmap](docs/ROADMAP.md)
- [Screenshots](docs/SCREENSHOTS.md)

## Screenshots

Public screenshots are not committed yet. Expected screenshot paths and local capture instructions are documented in [Screenshots](docs/SCREENSHOTS.md).

When real screenshots are added, place them under `assets/screenshots/` using the documented filenames so they can be referenced from this README without changing paths.

## Security and Data Handling

Sentinel is a governance and control layer. It is not a substitute for legal, regulatory, or security review.

Default posture:

- raw prompts and responses are not stored by default
- audit records prioritize metadata, hashes, outcomes, and correlation identifiers
- tenant and role boundaries are enforced server-side
- provider credentials and routing policy are managed through tenant-scoped controls

See [Security](SECURITY.md), [Data Handling](docs/DataHandling.md), and [Threat Model](docs/THREAT_MODEL.md).

## License

Sentinel is source-available for review and evaluation only. The code is not open source, and public repository access does not grant permission to reuse, modify, redistribute, run in production, or use commercially unless separately licensed.

See [LICENSE](LICENSE) for the controlling terms. For commercial licensing or additional usage permissions, contact the repository owner, adam-vanarsdalen.

## Roadmap

Current roadmap themes:

- stronger policy workflow ergonomics
- richer audit and reporting surfaces
- enterprise identity and compliance integrations
- expanded deployment hardening
- broader preset quality across regulated domains

See [Roadmap](docs/ROADMAP.md).

## Assets

Project media belongs in:

- `assets/screenshots/`
- `assets/diagrams/`
- `assets/demo/`

Screenshot capture targets are tracked in [Screenshots](docs/SCREENSHOTS.md).
