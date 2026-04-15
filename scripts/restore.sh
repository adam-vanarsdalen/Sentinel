#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 /path/to/sentinellaw-postgres-<timestamp>.dump" >&2
  exit 1
fi

BACKUP_FILE="$1"
if [[ ! -f "$BACKUP_FILE" ]]; then
  echo "Backup file not found: $BACKUP_FILE" >&2
  exit 1
fi

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
COMPOSE_ENV_FILE="${COMPOSE_ENV_FILE:-}"

compose_cmd=(docker compose -f "$COMPOSE_FILE")
if [[ -n "$COMPOSE_ENV_FILE" ]]; then
  compose_cmd=(docker compose --env-file "$COMPOSE_ENV_FILE" -f "$COMPOSE_FILE")
fi

if [[ -n "$COMPOSE_ENV_FILE" ]]; then
  if [[ ! -f "$COMPOSE_ENV_FILE" ]]; then
    echo "Missing env file: $COMPOSE_ENV_FILE" >&2
    exit 1
  fi
  set -a
  # shellcheck disable=SC1090
  source "$COMPOSE_ENV_FILE"
  set +a
fi

: "${POSTGRES_USER:?POSTGRES_USER must be set}"
: "${POSTGRES_DB:?POSTGRES_DB must be set}"

echo "Stopping application services before restore"
"${compose_cmd[@]}" stop caddy frontend backend worker >/dev/null 2>&1 || true

echo "Ensuring Postgres is running"
"${compose_cmd[@]}" up -d postgres >/dev/null

for _ in $(seq 1 30); do
  if "${compose_cmd[@]}" exec -T postgres pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

if ! "${compose_cmd[@]}" exec -T postgres pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; then
  echo "Postgres did not become ready in time" >&2
  exit 1
fi

echo "Dropping and recreating database $POSTGRES_DB"
"${compose_cmd[@]}" exec -T postgres dropdb --if-exists -U "$POSTGRES_USER" "$POSTGRES_DB"
"${compose_cmd[@]}" exec -T postgres createdb -U "$POSTGRES_USER" "$POSTGRES_DB"

echo "Restoring $BACKUP_FILE"
cat "$BACKUP_FILE" | "${compose_cmd[@]}" exec -T postgres pg_restore \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges

echo "Running migrations to align restored data with current app code"
"${compose_cmd[@]}" run --rm backend alembic upgrade head

echo "Starting full stack"
"${compose_cmd[@]}" up -d

echo "Restore complete. Run scripts/smoke-test.sh before reopening access."
