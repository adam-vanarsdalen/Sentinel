# Sentinel Deployment Runbook (Docker Compose / VPS)

This runbook is for Sentinel pilot deployments on a single VPS or a small number of VPS instances using Docker Compose. It assumes the existing repo artifacts remain the source of truth:

- `docker-compose.prod.yml`
- `.env.production.template`
- `deploy.sh`
- `scripts/backup.sh`
- `scripts/restore.sh`
- `scripts/smoke-test.sh`
- `scripts/bootstrap-admin.sh`

This is intentionally not a Kubernetes guide.

## 1) Prerequisites

### Server prerequisites
- Ubuntu/Debian-class VPS with current security updates.
- DNS name already assigned for the pilot, for example `pilot.examplelaw.com`.
- Docker Engine with the Compose plugin installed.
- Git installed.
- Outbound internet access for:
  - container image pulls
  - Python/npm dependency install during image build
  - Let’s Encrypt certificate issuance via Caddy
  - external model provider APIs
- Inbound ports:
  - `80/tcp`
  - `443/tcp`
  - `443/udp`

### Operator prerequisites
- Access to the repo on the deployment host.
- A completed production env file derived from `.env.production.template`.
- Strong secrets prepared for:
  - `POSTGRES_PASSWORD`
  - `JWT_SECRET`
  - `SENTINEL_SECRET_KEY`
  - optional `METRICS_TOKEN`
- A decision on whether demo seed data must be disabled.

## 2) Deployment Layout

The production stack in `docker-compose.prod.yml` runs:
- `postgres`
- `redis`
- `backend`
- `worker`
- `frontend`
- `caddy`

Traffic flow:
- Caddy terminates TLS and reverse-proxies the UI and API.
- The backend serves the API, gateway, audit/export, and health/readiness endpoints.
- The worker runs Celery jobs.

Persistent state today:
- Postgres data volume
- Caddy data/config volumes for certificate state

Current pilot note:
- Sentinel does not store uploaded client documents as a separate file store in this repo.
- Audit exports are generated on demand; they are not persisted as durable artifacts by default.

## 3) DNS Setup

1. Create an `A` record from the public hostname to the VPS public IP.
2. If IPv6 is in use, create the matching `AAAA` record.
3. Wait for propagation before first boot.
4. Set `PUBLIC_DOMAIN` in the env file to that exact hostname.

Example:

```env
PUBLIC_DOMAIN=pilot.examplelaw.com
```

## 4) TLS Setup

TLS is handled by Caddy in `docker-compose.prod.yml`.

Required env:

```env
PUBLIC_DOMAIN=pilot.examplelaw.com
CADDY_EMAIL=ops@examplelaw.com
```

Notes:
- Caddy will request and renew Let’s Encrypt certificates automatically.
- Port `80` must be reachable for ACME HTTP challenge.
- Port `443` must be reachable for HTTPS.
- Back up the `caddy_data` and `caddy_config` volumes before major infra changes if you want to preserve certificate/account state.

## 5) Environment Variables

Create a real env file, for example:

```bash
cp .env.production.template .env.production
```

Minimum production settings to review carefully:
- Postgres:
  - `POSTGRES_USER`
  - `POSTGRES_PASSWORD`
  - `POSTGRES_DB`
  - `DATABASE_URL`
- Redis:
  - `REDIS_URL`
- App/auth:
  - `ENVIRONMENT=production`
  - `JWT_SECRET`
  - `SENTINEL_SECRET_KEY`
  - `CORS_ORIGINS`
- Public routing:
  - `PUBLIC_DOMAIN`
  - `CADDY_EMAIL`
  - `NEXT_PUBLIC_GATEWAY_URL`
- Optional but recommended:
  - `METRICS_TOKEN`
  - `APP_VERSION`
  - `SUPPORT_EMAIL`
- Demo:
  - set `SEED_DEMO=0` unless you explicitly want demo data in the pilot

Important production notes:
- `SENTINEL_SECRET_KEY` is required in production because tenant-scoped provider credentials are encrypted at rest.
- Environment-variable model provider keys are now development fallback only. Preferred production pattern is per-firm provider config in the UI.
- Avoid wildcard CORS in production.
- If the pilot will use email alerts, configure `SMTP_HOST`, `SMTP_PORT`, and, when applicable, `SMTP_USER` / `SMTP_PASSWORD`.

## 6) First Boot

### Standard first boot

From the repo root on the server:

```bash
COMPOSE_ENV_FILE=.env.production ./deploy.sh
```

What this does:
1. pulls the latest git changes
2. builds images
3. runs Alembic migrations
4. starts the production Compose stack
5. waits for backend readiness

### Manual first boot

If you do not want to use `deploy.sh`:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml build
docker compose --env-file .env.production -f docker-compose.prod.yml run --rm backend alembic upgrade head
docker compose --env-file .env.production -f docker-compose.prod.yml up -d
```

## 7) Creating / Bootstrapping the Super Admin

If `SEED_DEMO=0`, bootstrap an initial platform super admin after first boot:

```bash
COMPOSE_ENV_FILE=.env.production ./scripts/bootstrap-admin.sh
```

The script:
- prompts for email/password if not already exported
- creates the user if missing
- or resets the existing user to:
  - `role = super_admin`
  - `tenant_id = null`
  - `is_active = true`

Non-interactive example:

```bash
BOOTSTRAP_ADMIN_EMAIL=platform-admin@examplelaw.com \
BOOTSTRAP_ADMIN_PASSWORD='use-a-long-random-password' \
COMPOSE_ENV_FILE=.env.production \
./scripts/bootstrap-admin.sh
```

After bootstrap:
1. sign in to the admin UI
2. create or verify the pilot firm
3. create tenant admins for that firm
4. configure per-firm provider credentials, approvals, and resilience settings

Provider resilience checklist:
- Set reasonable connect/read timeouts for each provider.
- Keep retry counts low for legal-review traffic to avoid long waits.
- Enable fallback only when the fallback provider/model has already been approved by the firm.
- Document any cross-provider fallback choice in the pilot change log so legal/compliance reviewers know alternate routing is possible.

## 8) Migrations

Current startup behavior:
- the backend container command runs `alembic upgrade head` before starting Uvicorn

Recommended deployment practice:
- still run migrations explicitly before `up -d` during upgrades
- do not rely only on container startup for operational migrations

Manual migration command:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml run --rm backend alembic upgrade head
```

Rules:
- backup first
- run migrations before reopening traffic
- if a migration fails, stop and investigate before continuing
- after provider-routing changes, verify at least one tenant can still complete:
  - a direct provider request
  - a provider connection test
  - a request with the intended fallback disabled/enabled posture

## 9) Smoke Test Steps

Use the helper script:

```bash
API_BASE_URL=https://pilot.examplelaw.com \
PUBLIC_BASE_URL=https://pilot.examplelaw.com \
SMOKE_ADMIN_EMAIL=platform-admin@examplelaw.com \
SMOKE_ADMIN_PASSWORD='use-a-long-random-password' \
./scripts/smoke-test.sh
```

What it checks:
- `GET /health`
- `GET /ready`
- frontend root page, if `PUBLIC_BASE_URL` is set
- admin login + `GET /auth/me`, if admin creds are supplied

Recommended additional manual smoke checks:
1. open the UI and confirm `/login` loads
2. sign in as the super admin
3. create/select the pilot firm
4. open **Provider Settings**
5. open **AI Activity Log**
6. send one test request through `/v1/chat/completions`
7. confirm the audit event is written

## 10) Health Checks

Backend endpoints:
- `GET /health`
- `GET /healthz`
- `GET /ready`
- `GET /readyz`

Current meaning:
- `/health` and `/healthz`: lightweight liveness
- `/ready` and `/readyz`: dependency-aware readiness

Readiness currently checks:
- database reachability
- Redis reachability
- demo tenant presence when `SEED_DEMO=1`
- built-in policy template availability

Examples:

```bash
curl -fsS https://pilot.examplelaw.com/health
curl -fsS https://pilot.examplelaw.com/ready
```

## 11) Backup Procedure

### What to back up

Required:
- Postgres database

Recommended:
- `.env.production` stored in your secure secrets system
- Caddy volumes (`caddy_data`, `caddy_config`) before major infra changes

Current artifact note:
- there is no separate uploaded-document store in this repo today

### Postgres backup

Run:

```bash
COMPOSE_ENV_FILE=.env.production ./scripts/backup.sh
```

Output:
- `backups/sentinel-postgres-<timestamp>.dump`
- `backups/sentinel-backup-<timestamp>.txt`

### Backup retention guidance

For pilots, a practical baseline is:
- daily backups retained for 7 days
- weekly backups retained for 4 weeks
- before every deployment, upgrade, restore, or migration-heavy maintenance window

Store backups:
- off-host if possible
- encrypted at rest
- with access limited to ops/admin personnel

## 12) Restore Procedure

Warning:
- restore is destructive to the target database
- stop application traffic first
- confirm you are restoring to the correct environment

Run:

```bash
COMPOSE_ENV_FILE=.env.production ./scripts/restore.sh ./backups/sentinel-postgres-<timestamp>.dump
```

What the restore script does:
1. stops app services
2. ensures Postgres is running
3. drops and recreates the configured database
4. restores the supplied dump
5. runs `alembic upgrade head`
6. starts the stack again

After restore:
1. run `./scripts/smoke-test.sh`
2. sign in manually
3. verify recent audit events
4. verify tenant/provider settings for the pilot firm

## 13) Upgrade Procedure

### Safe order

1. confirm the working tree on the server is clean enough for deployment
2. create a fresh backup
3. review `.env.production` for any new required env vars
4. deploy:

```bash
COMPOSE_ENV_FILE=.env.production ./deploy.sh
```

### Downtime expectations

Pilot Compose upgrades are typically short but not zero-downtime:
- backend restarts during image rollout
- frontend restarts during rollout
- migrations may hold locks depending on schema change

For pilot expectations, plan a short maintenance window.

### Validation after upgrade

After deployment:
1. run `./scripts/smoke-test.sh`
2. check `docker compose -f docker-compose.prod.yml ps`
3. confirm `/ready` returns `ok: true`
4. log in as super admin
5. send one test gateway request
6. verify an audit event is present

## 14) Rollback Procedure

Rollback strategy for this pilot is image/code rollback plus database restore when needed.

### When rollback is appropriate
- application build is broken
- migrations applied but app behavior is not acceptable
- smoke tests fail after deploy

### Basic rollback

1. identify the last known good git commit
2. create a fresh backup of the current database before changing anything
3. check out the last known good commit
4. rebuild and restart using the same env file

Example:

```bash
git checkout <last-known-good-commit>
COMPOSE_ENV_FILE=.env.production ./deploy.sh
```

### Database rollback

If the failed deployment changed data/schema incompatibly, restore the pre-upgrade Postgres backup:

```bash
COMPOSE_ENV_FILE=.env.production ./scripts/restore.sh ./backups/sentinel-postgres-<pre-upgrade-timestamp>.dump
```

Important:
- some migrations are not guaranteed to be safely reversible through Alembic downgrade alone
- the safest pilot rollback path is restore-from-backup

## 15) Log Locations

Container logs:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml logs backend
docker compose --env-file .env.production -f docker-compose.prod.yml logs worker
docker compose --env-file .env.production -f docker-compose.prod.yml logs frontend
docker compose --env-file .env.production -f docker-compose.prod.yml logs caddy
docker compose --env-file .env.production -f docker-compose.prod.yml logs postgres
```

Follow logs live:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml logs -f backend worker caddy
```

Operational notes:
- backend logs are JSON-formatted structured logs on stdout
- request correlation uses `request_id`
- audit events are stored in Postgres and exported through the app, not written as flat files by default

## 16) Troubleshooting

### Caddy never gets a certificate
- confirm `PUBLIC_DOMAIN` resolves to the VPS
- confirm ports 80 and 443 are open
- confirm no other reverse proxy is already binding those ports
- check `docker compose ... logs caddy`

### `/ready` fails with database error
- confirm `DATABASE_URL` points at the Compose `postgres` service
- check Postgres health:
  - `docker compose ... ps`
  - `docker compose ... logs postgres`
- verify credentials in `.env.production`

### `/ready` fails with Redis error
- check `REDIS_URL`
- verify the `redis` container is running
- review `docker compose ... logs redis`

### Frontend loads but login fails
- verify `JWT_SECRET`, `JWT_ISSUER`, and `JWT_AUDIENCE` are consistent
- confirm the backend is reachable behind Caddy
- review backend logs for auth errors

### Admin UI loads but provider calls fail
- verify firm-scoped provider config in **Provider Settings**
- confirm per-firm provider approval/default settings
- verify `SENTINEL_SECRET_KEY` is set and stable across restarts

### Metrics endpoint should not be public
- set `METRICS_TOKEN`
- front the endpoint with network controls if needed

### Deploy fails on migration
- stop the rollout
- inspect the migration error in backend logs/output
- restore from the pre-upgrade backup if needed

### You accidentally deployed with `SEED_DEMO=1`
- disable it in `.env.production`
- redeploy
- remove unwanted demo users/tenant data intentionally through admin or direct ops procedure

## 17) Operator Checklist

Before go-live:
- DNS resolves
- `.env.production` completed
- `SEED_DEMO=0` unless explicitly required
- `JWT_SECRET` and `SENTINEL_SECRET_KEY` are strong and stored safely
- first backup plan agreed

After go-live:
- bootstrap super admin
- create pilot firm and tenant admins
- configure per-firm provider credentials
- run smoke tests
- document the backup file location and rollback point
