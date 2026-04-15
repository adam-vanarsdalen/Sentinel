#!/usr/bin/env bash
set -Eeuo pipefail

PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-}"
API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
SMOKE_ADMIN_EMAIL="${SMOKE_ADMIN_EMAIL:-}"
SMOKE_ADMIN_PASSWORD="${SMOKE_ADMIN_PASSWORD:-}"
SMOKE_ADMIN_FALLBACK_EMAILS="${SMOKE_ADMIN_FALLBACK_EMAILS:-}"

echo "Checking backend health"
curl -fsS "$API_BASE_URL/health" >/dev/null
curl -fsS "$API_BASE_URL/ready" >/dev/null

if [[ -n "$PUBLIC_BASE_URL" ]]; then
  echo "Checking public frontend"
  curl -fsS "$PUBLIC_BASE_URL/" >/dev/null
fi

if [[ -n "$SMOKE_ADMIN_EMAIL" && -n "$SMOKE_ADMIN_PASSWORD" ]]; then
  echo "Checking admin login"
  try_login() {
    local email="$1"
    local http
    local response
    local parsed_token
    http="$(curl -sS -o /tmp/sentinel-smoke-login.json -w "%{http_code}" -X POST "$API_BASE_URL/auth/login" \
      -H 'Content-Type: application/json' \
      -d "{\"email\":\"$email\",\"password\":\"$SMOKE_ADMIN_PASSWORD\"}")"
    response="$(cat /tmp/sentinel-smoke-login.json)"
    parsed_token="$(printf '%s' "$response" | tr -d '\n' | sed -E 's/.*"access_token"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/')"
    if [[ "$parsed_token" == "$response" ]]; then
      parsed_token=""
    fi
    if [[ "$http" == "200" && -n "$parsed_token" ]]; then
      token="$parsed_token"
      echo "Admin login succeeded for $email"
      return 0
    fi
    token=""
    echo "Admin login attempt failed (HTTP $http) for $email" >&2
    echo "Response: $response" >&2
    return 1
  }

  token=""
  if ! try_login "$SMOKE_ADMIN_EMAIL"; then
    IFS=',' read -r -a fallback_emails <<< "$SMOKE_ADMIN_FALLBACK_EMAILS"
    for fallback_email in "${fallback_emails[@]}"; do
      fallback_email="$(printf '%s' "$fallback_email" | xargs)"
      [[ -z "$fallback_email" ]] && continue
      if try_login "$fallback_email"; then
        break
      fi
    done
  fi
  if [[ -z "$token" ]]; then
    echo "All admin login attempts failed against $API_BASE_URL/auth/login" >&2
    echo "Hint: verify DEMO_TENANT_ADMIN_EMAIL / DEMO_TENANT_ADMIN_PASSWORD and seeded preset users." >&2
    exit 1
  fi

  auth_me_http="$(curl -sS -o /tmp/sentinel-smoke-auth-me.json -w "%{http_code}" "$API_BASE_URL/auth/me" -H "Authorization: Bearer $token")"
  if [[ "$auth_me_http" != "200" ]]; then
    echo "Auth verification failed (HTTP $auth_me_http) for $API_BASE_URL/auth/me" >&2
    echo "Response: $(cat /tmp/sentinel-smoke-auth-me.json)" >&2
    exit 1
  fi
fi

echo "Smoke test passed."
