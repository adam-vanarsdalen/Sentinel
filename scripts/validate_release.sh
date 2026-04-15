#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ARTIFACTS_DIR="${ARTIFACTS_DIR:-$ROOT_DIR/artifacts/validate-release}"
BACKEND_PORT="${BACKEND_PORT:-18000}"
FRONTEND_PORT="${FRONTEND_PORT:-13000}"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-sentinel_validate}"
PLAYWRIGHT_IMAGE="${PLAYWRIGHT_IMAGE:-mcr.microsoft.com/playwright:v1.50.1-noble}"

resolve_version() {
  if [[ -n "${APP_VERSION:-}" ]]; then
    printf '%s\n' "$APP_VERSION"
    return
  fi
  if git describe --tags --always --dirty >/dev/null 2>&1; then
    git describe --tags --always --dirty
    return
  fi
  sed -n 's/.*"version":[[:space:]]*"\([^"]*\)".*/\1/p' frontend/package.json | head -n1
}

APP_VERSION="$(resolve_version)"
ENV_FILE="$(mktemp /tmp/sentinel-validate-env.XXXXXX)"
COMPOSE_CMD=(docker compose --env-file "$ENV_FILE" -p "$COMPOSE_PROJECT_NAME")

cleanup() {
  mkdir -p "$ARTIFACTS_DIR"
  "${COMPOSE_CMD[@]}" logs --no-color > "$ARTIFACTS_DIR/compose.log" 2>/dev/null || true
  "${COMPOSE_CMD[@]}" down -v >/dev/null 2>&1 || true
  rm -f "$ENV_FILE"
}
trap cleanup EXIT

mkdir -p "$ARTIFACTS_DIR"
cp .env.example "$ENV_FILE"
{
  printf '\nAPP_VERSION=%s\n' "$APP_VERSION"
  printf 'BACKEND_PORT=%s\n' "$BACKEND_PORT"
  printf 'FRONTEND_PORT=%s\n' "$FRONTEND_PORT"
  printf 'NEXT_PUBLIC_API_BASE_URL=http://localhost:%s\n' "$BACKEND_PORT"
} >> "$ENV_FILE"

wait_for_http() {
  local url="$1"
  local label="$2"
  for _ in $(seq 1 90); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  echo "$label did not become ready in time: $url" >&2
  return 1
}

echo "==> Release validation version: $APP_VERSION"
echo "==> Bringing up validation stack"
"${COMPOSE_CMD[@]}" up -d --build

echo "==> Waiting for backend and frontend"
wait_for_http "http://localhost:$BACKEND_PORT/ready" "Backend readiness"
wait_for_http "http://localhost:$FRONTEND_PORT/login" "Frontend login page"

# Source of truth for validation credentials:
# - DEMO_TENANT_ADMIN_* and DEMO_SUPER_ADMIN_* in .env.example / runtime env
SMOKE_ADMIN_EMAIL="${DEMO_TENANT_ADMIN_EMAIL:-admin@demoorg.com}"
SMOKE_ADMIN_PASSWORD="${DEMO_TENANT_ADMIN_PASSWORD:-ChangeMe!12345}"
SMOKE_ADMIN_FALLBACK_EMAILS="${SMOKE_ADMIN_FALLBACK_EMAILS:-admin@northwind.example,platform-admin@example.com}"
E2E_SUPERADMIN_EMAIL="${DEMO_SUPER_ADMIN_EMAIL:-platform-admin@example.com}"
E2E_SUPERADMIN_PASSWORD="${DEMO_SUPER_ADMIN_PASSWORD:-ChangeMe!12345}"

echo "==> Seeding demo data for validation"
"${COMPOSE_CMD[@]}" run --rm --no-deps backend python -m app.scripts.seed_demo

echo "==> Ensuring deterministic super admin credentials for validation"
"${COMPOSE_CMD[@]}" run --rm --no-deps \
  -e BOOTSTRAP_ADMIN_EMAIL="$E2E_SUPERADMIN_EMAIL" \
  -e BOOTSTRAP_ADMIN_PASSWORD="$E2E_SUPERADMIN_PASSWORD" \
  backend python -m app.scripts.bootstrap_admin

echo "==> Ensuring deterministic org admin credentials for validation"
"${COMPOSE_CMD[@]}" run --rm --no-deps \
  -e BOOTSTRAP_TENANT_ADMIN_EMAIL="$SMOKE_ADMIN_EMAIL" \
  -e BOOTSTRAP_TENANT_ADMIN_PASSWORD="$SMOKE_ADMIN_PASSWORD" \
  backend python -m app.scripts.bootstrap_tenant_admin

echo "==> Docker Compose smoke boot check"
API_BASE_URL="http://localhost:$BACKEND_PORT" \
PUBLIC_BASE_URL="http://localhost:$FRONTEND_PORT" \
SMOKE_ADMIN_EMAIL="$SMOKE_ADMIN_EMAIL" \
SMOKE_ADMIN_PASSWORD="$SMOKE_ADMIN_PASSWORD" \
SMOKE_ADMIN_FALLBACK_EMAILS="$SMOKE_ADMIN_FALLBACK_EMAILS" \
  ./scripts/smoke-test.sh

echo "==> Backend tests"
"${COMPOSE_CMD[@]}" run --rm --no-deps backend pytest -q

echo "==> Frontend lint"
"${COMPOSE_CMD[@]}" run --rm --no-deps frontend npm run lint

echo "==> Frontend build"
"${COMPOSE_CMD[@]}" run --rm --no-deps frontend npm run build

rm -rf "$ARTIFACTS_DIR/playwright-report" "$ARTIFACTS_DIR/playwright-results"

echo "==> Playwright smoke tests"
docker run --rm \
  --user "$(id -u):$(id -g)" \
  --network "${COMPOSE_PROJECT_NAME}_default" \
  -e CI=1 \
  -e HOME=/tmp/playwright-home \
  -e npm_config_cache=/tmp/playwright-home/npm-cache \
  -e PLAYWRIGHT_BASE_URL="http://frontend:3000" \
  -e E2E_BACKEND_BASE_URL="http://backend:8000" \
  -e E2E_EMAIL="$SMOKE_ADMIN_EMAIL" \
  -e E2E_PASSWORD="$SMOKE_ADMIN_PASSWORD" \
  -e E2E_SUPERADMIN_EMAIL="$E2E_SUPERADMIN_EMAIL" \
  -e E2E_SUPERADMIN_PASSWORD="$E2E_SUPERADMIN_PASSWORD" \
  -e PLAYWRIGHT_REPORT_DIR="../artifacts/validate-release/playwright-report" \
  -e PLAYWRIGHT_TEST_RESULTS_DIR="../artifacts/validate-release/playwright-results" \
  -v "$ROOT_DIR:/repo" \
  -w /repo/frontend \
  "$PLAYWRIGHT_IMAGE" \
  bash -lc "npm ci && npm run test:e2e"

cat > "$ARTIFACTS_DIR/validation-summary.txt" <<EOF
app_version=$APP_VERSION
backend_port=$BACKEND_PORT
frontend_port=$FRONTEND_PORT
compose_project_name=$COMPOSE_PROJECT_NAME
status=passed
EOF

echo "Release validation passed."
echo "Artifacts: $ARTIFACTS_DIR"
