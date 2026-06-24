# API Reference

Base URL (local): `http://localhost:8000`

All request and response bodies are JSON. All management endpoints that filter by tenant accept `tenant_id` as a query parameter.

---

## Proxy Endpoints

These are the primary entry points. Point your existing AI SDK at them.

### POST /v1/chat/completions

OpenAI-compatible endpoint. Accepts the full OpenAI chat completions request format.

**Request body** (OpenAI format):
```json
{
  "model": "gpt-4o",
  "messages": [{ "role": "user", "content": "Hello" }],
  "tools": [...],
  "stream": false
}
```

**Headers required:**
```
X-Tenant-ID: your-tenant-id
X-Agent-ID: your-agent-id
Authorization: Bearer <your-api-key>
```

**Response:** Standard OpenAI chat completion response, or an error if any enforcement layer blocked the request.

**Blocked response example:**
```json
{
  "error": {
    "type": "enforcement_blocked",
    "layer": 3,
    "message": "Agent paused — queued for human review",
    "request_id": "3f2a1b4c-..."
  }
}
```

---

### POST /v1/messages

Anthropic-compatible endpoint. Accepts the Anthropic Messages API request format. Internally normalized to OpenAI format before entering the pipeline.

---

## Agent Management

### POST /api/agents/

Create a new agent.

**Request body:**
```json
{
  "tenant_id": "acme-corp",
  "name": "support-agent",
  "purpose_binding": "customer support only — no access to financial data",
  "config": {
    "department": "customer-success"
  }
}
```

**Response:**
```json
{
  "id": "uuid",
  "tenant_id": "acme-corp",
  "name": "support-agent",
  "purpose_binding": "customer support only — no access to financial data",
  "state": "active",
  "config": {},
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-01T00:00:00Z"
}
```

---

### GET /api/agents/

List all agents for a tenant.

**Query parameters:**
- `tenant_id` (required)

**Response:** Array of agent objects.

---

### GET /api/agents/{agent_id}

Get a single agent.

---

## Policy Management

### POST /api/policies/

Create a governance policy.

**Request body:**
```json
{
  "tenant_id": "acme-corp",
  "name": "standard-policy",
  "action_limit_session": 50,
  "budget_hourly_usd": 5.0,
  "budget_daily_usd": 50.0,
  "budget_monthly_usd": 500.0,
  "allowed_models": ["gpt-4o", "claude-3-5-sonnet-20241022"],
  "forbidden_endpoints": ["*.competitor.com", "internal.corp/*"],
  "forbidden_data_classes": ["financial", "medical"]
}
```

**Response:** Created policy object.

---

### GET /api/policies/

List all policies for a tenant.

**Query parameters:**
- `tenant_id` (required)

---

## Kill Switch

### POST /api/kill_switch/fire

Operator-initiated agent termination.

**Request body:**
```json
{
  "agent_id": "uuid",
  "operator_id": "ops-user-123",
  "reason": "Suspected data exfiltration",
  "tenant_id": "acme-corp"
}
```

**Response:**
```json
{
  "agent_id": "uuid",
  "previous_state": "active",
  "new_state": "terminated",
  "timestamp": "2025-01-01T00:00:00Z"
}
```

---

### POST /api/kill_switch/resume

Resume a contained agent. Requires `operator_id`.

**Request body:**
```json
{
  "agent_id": "uuid",
  "operator_id": "ops-user-123",
  "reason": "Incident reviewed — resuming operations",
  "tenant_id": "acme-corp"
}
```

---

### GET /api/kill_switch/state/{agent_id}

Get the current kill switch state for an agent.

**Response:**
```json
{
  "agent_id": "uuid",
  "state": "throttled",
  "reason": "Anomaly detected: cost 4.2σ above baseline",
  "triggered_by": "layer6",
  "state_ts": "2025-01-01T00:00:00Z"
}
```

---

## Alerts

### GET /api/alerts/

List recent alerts.

**Query parameters:**
- `tenant_id` (required)
- `limit` (default: 50)
- `resolved` (boolean, optional)

**Response:**
```json
[
  {
    "id": "uuid",
    "tenant_id": "acme-corp",
    "agent_id": "uuid",
    "request_id": "uuid",
    "alert_type": "anomaly",
    "severity": "high",
    "message": "Agent cost 4.2σ above 7-day baseline — throttled",
    "metadata": { "z_score": 4.2, "dimension": "cost" },
    "resolved": false,
    "created_at": "2025-01-01T00:00:00Z"
  }
]
```

**Alert types:** `kill_switch` · `anomaly` · `grounding` · `budget` · `manual`

**Severity levels:** `low` · `medium` · `high` · `critical`

---

## Audit Log

### GET /api/audit/

Query the append-only audit log.

**Query parameters:**
- `tenant_id` (required)
- `agent_id` (optional)
- `status` — `passed` | `blocked` | `flagged` | `error` (optional)
- `start` — ISO 8601 datetime (optional)
- `end` — ISO 8601 datetime (optional)
- `limit` (default: 100)
- `offset` (default: 0)

**Response:**
```json
[
  {
    "id": 1042,
    "request_id": "uuid",
    "tenant_id": "acme-corp",
    "agent_id": "uuid",
    "action": "chat_completion",
    "layer": 7,
    "status": "passed",
    "model": "gpt-4o",
    "latency_ms": 1234.5,
    "metadata": { "input_tokens": 450, "output_tokens": 120 },
    "regulation_mappings": {
      "eu_ai_act": ["Article 9", "Article 12", "Article 13"],
      "nist_ai_rmf": ["GOVERN-1.1", "MAP-1.1"],
      "hipaa": ["164.312(b)"]
    },
    "created_at": "2025-01-01T00:00:00Z"
  }
]
```

---

### GET /api/audit/export/csv

Export audit log entries as a CSV file.

**Query parameters:** Same as `GET /api/audit/`.

**Response:** `Content-Type: text/csv` file download.

---

## Compliance

### POST /api/compliance/generate

Generate a regulation evidence package for a tenant and time range.

**Request body:**
```json
{
  "tenant_id": "acme-corp",
  "time_range_start": "2025-01-01T00:00:00Z",
  "time_range_end": "2025-01-31T23:59:59Z",
  "regulations": ["eu_ai_act", "nist_ai_rmf", "hipaa", "colorado_sb205"]
}
```

**Response:**
```json
{
  "id": "uuid",
  "tenant_id": "acme-corp",
  "time_range_start": "2025-01-01T00:00:00Z",
  "time_range_end": "2025-01-31T23:59:59Z",
  "regulations": ["eu_ai_act", "nist_ai_rmf"],
  "total_requests": 8420,
  "blocked_requests": 134,
  "anomalies_detected": 7,
  "kill_switch_events": 2,
  "evidence_json": {
    "eu_ai_act": {
      "Article 9": { "entry_ids": [1, 42, 107, ...], "count": 8420 },
      "Article 14": { "entry_ids": [8, 22, ...], "count": 134 }
    }
  },
  "gap_analysis": {
    "missing_controls": [],
    "gaps": []
  },
  "created_at": "2025-01-01T00:00:00Z"
}
```

**Gap analysis format when gaps exist:**
```json
{
  "gaps": [
    {
      "control_id": "NIST MEASURE-2.5",
      "regulation": "nist_ai_rmf",
      "description": "No MEASURE-2.5 evidence in range. This control is satisfied by grounding (Layer 5) events. Ensure Layer 5 is active and processing requests."
    }
  ]
}
```

---

### GET /api/compliance/{package_id}/pdf

Download a previously generated evidence package as a PDF.

**Response:** `Content-Type: application/pdf` file download.

---

## Dashboard

### GET /api/dashboard/metrics

Aggregated 24-hour metrics for a tenant.

**Query parameters:**
- `tenant_id` (required)

**Response:**
```json
{
  "total_requests_24h": 8420,
  "blocked_requests_24h": 134,
  "flagged_requests_24h": 42,
  "anomalies_24h": 7,
  "kill_switch_events_24h": 2,
  "compliance_packages_generated": 3,
  "layer_throughput": {
    "layer1": 8420,
    "layer2": 8420,
    "layer3": 8286,
    "layer4": 8244,
    "layer5": 8244,
    "layer6": 8244,
    "layer7": 8420
  }
}
```

---

### GET /api/dashboard/recent-rps

Recent requests per second (for the throughput chart).

**Response:** Array of `{ timestamp, rps }` objects for the last 30 seconds.

---

## WebSocket Feeds

Connect with any WebSocket client. All feeds auto-broadcast; no subscription message is required.

### ws://localhost:8000/ws/alerts

Emits alert objects as they occur. Same schema as `GET /api/alerts/` items.

### ws://localhost:8000/ws/requests

Emits a summary object for each request that completes the pipeline:
```json
{
  "request_id": "uuid",
  "agent_id": "uuid",
  "status": "passed",
  "model": "gpt-4o",
  "latency_ms": 1234,
  "cost_usd": 0.0042,
  "blocked_reason": null
}
```

### ws://localhost:8000/ws/metrics

Emits layer throughput counters every 2 seconds:
```json
{
  "timestamp": "2025-01-01T00:00:00Z",
  "layer_counts": { "1": 84, "2": 84, "3": 78, "4": 77, "5": 77, "6": 77, "7": 84 }
}
```

---

## Health

### GET /health

```json
{ "status": "ok" }
```
