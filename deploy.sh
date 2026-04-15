#!/usr/bin/env bash
set -Eeuo pipefail

FAILED_STEP=""
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
COMPOSE_ENV_FILE="${COMPOSE_ENV_FILE:-}"
COMPOSE_CMD=(docker compose -f "$COMPOSE_FILE")
if [[ -n "$COMPOSE_ENV_FILE" ]]; then
  COMPOSE_CMD=(docker compose --env-file "$COMPOSE_ENV_FILE" -f "$COMPOSE_FILE")
fi

on_error() {
  local exit_code=$?
  if [[ -n "${FAILED_STEP}" ]]; then
    echo "ERROR: step failed: ${FAILED_STEP}" >&2
  else
    echo "ERROR: deploy failed (unknown step)" >&2
  fi
  exit "${exit_code}"
}

trap on_error ERR

run_step() {
  local step="$1"
  shift
  FAILED_STEP="${step}"
  echo "==> ${step}"
  "$@"
  FAILED_STEP=""
}

wait_for_backend_ready() {
  for i in $(seq 1 30); do
    if "${COMPOSE_CMD[@]}" exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/readyz', timeout=2).read()" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  echo "Backend /readyz did not become ready in time" >&2
  return 1
}

run_step "Pull latest git changes" git pull --ff-only
run_step "Build images (prod)" "${COMPOSE_CMD[@]}" build
run_step "Run DB migrations" "${COMPOSE_CMD[@]}" run --rm backend alembic upgrade head
run_step "Start services (prod)" "${COMPOSE_CMD[@]}" up -d
run_step "Wait for backend readiness" wait_for_backend_ready

echo "Deploy complete."
