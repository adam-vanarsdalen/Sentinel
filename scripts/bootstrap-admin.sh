#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
COMPOSE_ENV_FILE="${COMPOSE_ENV_FILE:-}"

if [[ -z "${BOOTSTRAP_ADMIN_EMAIL:-}" ]]; then
  read -r -p "Super admin email: " BOOTSTRAP_ADMIN_EMAIL
fi
if [[ -z "${BOOTSTRAP_ADMIN_PASSWORD:-}" ]]; then
  read -r -s -p "Super admin password: " BOOTSTRAP_ADMIN_PASSWORD
  echo
fi

: "${BOOTSTRAP_ADMIN_EMAIL:?BOOTSTRAP_ADMIN_EMAIL is required}"
: "${BOOTSTRAP_ADMIN_PASSWORD:?BOOTSTRAP_ADMIN_PASSWORD is required}"

compose_cmd=(docker compose -f "$COMPOSE_FILE")
if [[ -n "$COMPOSE_ENV_FILE" ]]; then
  compose_cmd=(docker compose --env-file "$COMPOSE_ENV_FILE" -f "$COMPOSE_FILE")
fi

echo "Bootstrapping super admin ${BOOTSTRAP_ADMIN_EMAIL}"
BOOTSTRAP_ADMIN_EMAIL="$BOOTSTRAP_ADMIN_EMAIL" \
BOOTSTRAP_ADMIN_PASSWORD="$BOOTSTRAP_ADMIN_PASSWORD" \
  "${compose_cmd[@]}" run --rm \
    -e BOOTSTRAP_ADMIN_EMAIL \
    -e BOOTSTRAP_ADMIN_PASSWORD \
    backend python -m app.scripts.bootstrap_admin
