# Curl Examples

Assumes:
- Backend at `http://localhost:${BACKEND_PORT}`
- Frontend at `http://localhost:${FRONTEND_PORT}`

## 1) Login (UI JWT)

```bash
curl -sS -X POST "http://localhost:${BACKEND_PORT}/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@demoorg.com","password":"ChangeMe!12345"}'
```

## 2) Create an API key (tenant admin)

```bash
TOKEN="(paste access_token)"
curl -sS -X POST "http://localhost:${BACKEND_PORT}/admin/api-keys" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"name":"my-app"}'
```

## 3) Update Organization AI Rules (block “ignore previous instructions”)

```bash
TOKEN="(paste access_token)"
curl -sS -X PUT "http://localhost:${BACKEND_PORT}/admin/policy/current" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "policy_json": {
      "allowed_models": ["mock"],
      "max_tokens_per_request": 512,
      "max_prompt_chars": 20000,
      "block_prompt_patterns": ["ignore previous instructions"],
      "require_system_prompt_prefix": "",
      "output_validation_rules": [],
      "logging": { "store_redacted_snippets": false, "store_raw_content": false },
      "phi": { "enabled": true, "threshold_score": 80, "action": "flag" }
    }
  }'
```

## 4) Send a gateway request (API key)

```bash
API_KEY="(paste api key token)"
curl -sS -X POST "http://localhost:${BACKEND_PORT}/v1/chat/completions" \
  -H "X-API-Key: $API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "model":"mock",
    "messages":[{"role":"user","content":"Draft a short internal summary of an approved operations workflow."}],
    "max_tokens": 50
  }'
```

## 5) Export audit events (CSV / JSON)

```bash
TOKEN="(paste access_token)"
curl -sS -H "Authorization: Bearer $TOKEN" "http://localhost:${BACKEND_PORT}/admin/audit-events/export.csv"
curl -sS -H "Authorization: Bearer $TOKEN" "http://localhost:${BACKEND_PORT}/admin/audit-events/export.json?format=sentinel"
```
