#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
COMPOSE_ENV_FILE="${COMPOSE_ENV_FILE:-}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"

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

mkdir -p "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/sentinellaw-postgres-$TIMESTAMP.dump"
MANIFEST_FILE="$BACKUP_DIR/sentinellaw-backup-$TIMESTAMP.txt"

echo "Creating Postgres backup: $BACKUP_FILE"
"${compose_cmd[@]}" exec -T postgres pg_dump \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  --format=custom \
  --no-owner \
  --no-privileges > "$BACKUP_FILE"

{
  echo "timestamp=$TIMESTAMP"
  echo "compose_file=$COMPOSE_FILE"
  echo "backup_file=$(basename "$BACKUP_FILE")"
  echo "postgres_db=$POSTGRES_DB"
  echo "postgres_user=$POSTGRES_USER"
  echo "note=Current pilot stores operational state primarily in Postgres. If you rely on Caddy-managed TLS certificates, also snapshot the caddy_data and caddy_config volumes before major maintenance."
} > "$MANIFEST_FILE"

echo "Backup complete."
echo "Dump: $BACKUP_FILE"
echo "Manifest: $MANIFEST_FILE"
