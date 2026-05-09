# Deployment

## Local deployment (development/demo)

```bash
cp .env.example .env
docker compose up --build -d
```

This boots:

- `frontend` (admin UI)
- `backend` (gateway + admin APIs)
- `worker` (async eval tasks)
- `postgres`
- `redis`

## Production-style compose deployment

For VPS/pilot operation, use:

```bash
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
```

Production checklist:

- set strong `JWT_SECRET`
- set `SENTINEL_SECRET_KEY`
- set `METRICS_TOKEN` and configure metrics scrapers to send `X-Metrics-Token`
- set `SEED_DEMO=0`
- set `PROVIDER_DEFAULT` to a real provider, not `mock`
- set `COOKIE_SECURE=1`
- use managed secrets (not committed files)
- terminate TLS at ingress/reverse proxy
- restrict network access to backend and data services

Ollama-specific local deployment notes:

- Runtime API base URL should be OpenAI-compatible (`OLLAMA_BASE_URL=http://localhost:11434/v1/` by default).
- Keep `OLLAMA_API_KEY` in local/runtime env only. Sentinel never returns provider secrets in API responses.
- Even when Ollama has additional local models installed, Sentinel policy/provider allowlists still gate what can run.

## Preset-specific startup

Default shared Sentinel:

```bash
SENTINEL_PRESET=general
NEXT_PUBLIC_SENTINEL_PRESET=general
```

Legal edition (SentinelLaw):

```bash
SENTINEL_PRESET=legal
NEXT_PUBLIC_SENTINEL_PRESET=legal
```

## Operational scripts

- release validation: `./scripts/validate_release.sh`
- smoke checks: `./scripts/smoke-test.sh`
- backup/restore: `./scripts/backup.sh`, `./scripts/restore.sh`
- super admin bootstrap: `./scripts/bootstrap-admin.sh`

## References

- `docs/Troubleshooting.md`
- `docs/DeploymentRunbook.md` (supplemental runbook detail)
