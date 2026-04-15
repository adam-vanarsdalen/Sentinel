#!/usr/bin/env bash
set -Eeuo pipefail

PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-}"
API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
SMOKE_ADMIN_EMAIL="${SMOKE_ADMIN_EMAIL:-}"
SMOKE_ADMIN_PASSWORD="${SMOKE_ADMIN_PASSWORD:-}"

echo "Checking backend health"
curl -fsS "$API_BASE_URL/health" >/dev/null
curl -fsS "$API_BASE_URL/ready" >/dev/null

if [[ -n "$PUBLIC_BASE_URL" ]]; then
  echo "Checking public frontend"
  curl -fsS "$PUBLIC_BASE_URL/" >/dev/null
fi

if [[ -n "$SMOKE_ADMIN_EMAIL" && -n "$SMOKE_ADMIN_PASSWORD" ]]; then
  echo "Checking admin login"
  login_response="$(curl -fsS -X POST "$API_BASE_URL/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$SMOKE_ADMIN_EMAIL\",\"password\":\"$SMOKE_ADMIN_PASSWORD\"}")"
  token="$(printf '%s' "$login_response" | tr -d '\n' | sed -E 's/.*"access_token"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/')"
  if [[ -z "$token" || "$token" == "$login_response" ]]; then
    echo "Failed to parse access token from /auth/login response" >&2
    exit 1
  fi
  curl -fsS "$API_BASE_URL/auth/me" -H "Authorization: Bearer $token" >/dev/null
fi

echo "Smoke test passed."
