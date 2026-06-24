# Architecture

## Overview

Sentinel Stack is a 7-layer enforcement pipeline that sits between AI agents and the outside world. Every request travels through all seven layers in sequence before a model is called and before a response is returned.

```
                     ┌──────────────────────────┐
  Agent / Client ───►│   POST /v1/chat/completions   │
                     │   POST /v1/messages            │
                     └──────────────┬───────────────┘
                                    │
                     ┌──────────────▼───────────────┐
                     │         Middleware             │
                     │  UUID4 request_id · Rate limit │
                     └──────────────┬───────────────┘
                                    │
              ┌─────────────────────▼──────────────────────┐
              │               Pipeline Orchestrator         │
              │            (services/pipeline.py)           │
              └──┬────┬────┬────┬────┬────┬───────────────┘
                 │    │    │    │    │    │
                 L1   L2   L3   L4   L5   L6  L7
                 │    │    │    │    │    │    │
                 ▼    ▼    ▼    ▼    ▼    ▼    ▼
```

---

## Data Flow

### Request path

1. **Middleware** attaches a UUID4 `request_id` and enforces per-agent rate limits.
2. **Layer 1 (Ingestion)** normalizes the request (OpenAI or Anthropic format), estimates input tokens via tiktoken, and emits a `PipelineRequest` with provenance tags.
3. **Layer 2 (Routing)** selects the target model and provider, checks RBAC, and enforces hourly/daily/monthly budget limits. Emits a `RoutingDecision`.
4. **Layer 3 (Enforcement)** checks the kill switch state in Redis, validates action count, checks purpose binding, and blocks forbidden tool endpoints — all before touching a provider API. Emits `EnforcementCheck(allowed=True/False)`. If `allowed=False`, execution stops here; the block is written to the audit log and returned to the caller.
5. **Layer 4 (Reasoning)** calls the provider API (Anthropic, OpenAI, or Ollama). If the model wants to invoke a tool, Layer 4 re-runs that tool call through Layer 3 enforcement before executing it. This loop continues up to 20 rounds. Emits `ModelResponse`.
6. **Layer 5 (Grounding)** scores the model's response against any provided RAG sources. Low confidence responses are flagged or blocked and queued for human review.
7. **Layer 6 (Anomaly Detection)** updates the rolling behavioral baseline for the agent and computes z-scores across cost, latency, error rate, new data classes, and tool patterns. If a threshold is crossed, it calls `KillSwitchService` to throttle, pause, or terminate the agent automatically.
8. **Layer 7 (Compliance)** writes a single append-only audit log entry with the final status and all regulation control IDs that apply to this request.

### Response path

After all layers complete, the pipeline orchestrator assembles the response and returns it to the caller. Blocked requests return a structured error indicating which layer blocked them and why.

---

## Key Invariants

These rules are enforced in code and tests. Do not violate them.

**request_id threading** — Every request receives a UUID4 `request_id` at Layer 1. This ID threads through all 6 remaining layers, the audit log, every alert, and every Redis key for the request. It is the primary correlation key.

**Enforcement before execution** — Layer 3 always runs before Layer 4. A request that fails Layer 3 never touches a provider API.

**Audit-first kill switch transitions** — When the kill switch changes state (active → throttled → paused → terminated), the transition is written to the `audit_log` table first. Only if that write succeeds does the new state get written to Redis. If the audit write fails, the state does not change.

**Append-only audit log** — The `audit_log` PostgreSQL table has `UPDATE` and `DELETE` revoked from the application role (`sentinel_app`). Any attempt to modify or delete a row raises a permission error. Rows can only be inserted.

**Anomaly warmup** — A brand-new agent skips containment checks for its first 10 requests while the baseline is being established.

---

## Kill Switch State Machine

States are stored in Redis at `sentinel:agent:{agent_id}:state`.

```
           Layer 6 (≥3.5σ)                Layer 6 (≥5.0σ)
active ──────────────────► throttled ──────────────────► paused
  │                             │                            │
  │ Layer 6 (≥7.0σ)             │ Layer 6 (≥7.0σ)           │ Layer 6 (≥7.0σ)
  │ or operator                 │ or operator                │ or operator
  ▼                             ▼                            ▼
terminated ◄───────────── terminated ◄────────────────── terminated
  │
  │ operator resume (requires operator_id)
  ▼
active
```

`throttled → active` and `paused → active` also require operator resume. `terminated → throttled` and `terminated → paused` are forbidden transitions.

Each transition emits a Redis pub/sub message on `sentinel:alerts:{tenant_id}`.

---

## Anomaly Detection Design

Sentinel tracks five behavioral dimensions per agent using an online Welford algorithm (incremental mean and variance, no stored history):

| Dimension | What is measured |
|---|---|
| Cost | USD cost of each request |
| Latency | End-to-end latency in milliseconds |
| Error rate | Rolling error ratio |
| New data classes | Data classes accessed that have not been seen before |
| New tools | Tool names used that have not been seen before |

The z-score for each dimension is `(observed − mean) / std`. Dimensions are combined into a weighted score. When the combined score exceeds a configurable sigma threshold, `KillSwitchService` is called directly from within Layer 6.

A state snapshot is captured at containment time: the last 20 actions and all in-flight request IDs are stored in the `AnomalyResult` for post-incident analysis.

---

## Compliance Evidence

Layer 7 maps each request to the specific regulatory controls satisfied by the layer that processed it:

```
Layer 1 (Ingestion)   → EU AI Act Art. 12, NIST GOVERN-1.1, HIPAA 164.312(b)
Layer 2 (Routing)     → EU AI Act Art. 9, NIST GOVERN-1.2/1.4, Colorado 6-1-1702(b)
Layer 3 (Enforcement) → EU AI Act Art. 14, NIST MANAGE-1.3, HIPAA 164.308(a)(3), Colorado 6-1-1702(c)
Layer 4 (Reasoning)   → EU AI Act Art. 13, NIST MAP-1.1
Layer 5 (Grounding)   → EU AI Act Art. 15, NIST MEASURE-2.5, Colorado 6-1-1702(a)
Layer 6 (Anomaly)     → EU AI Act Art. 9, NIST MEASURE-2.2/MANAGE-2.2
Layer 7 (Compliance)  → EU AI Act Arts. 11/12, NIST GOVERN-6.1, HIPAA 164.312(b)
```

The `ComplianceGeneratorService` queries the audit log for a tenant and time range, groups entries by control ID, and generates an evidence package with a gap analysis that identifies controls with no qualifying evidence.

---

## Database Schema

Six tables in PostgreSQL. The append-only constraint on `audit_log` is enforced by the Alembic migration — not just application code.

| Table | Purpose |
|---|---|
| `agents` | Agent registry with state, purpose binding, config |
| `policies` | Governance policies: limits, budgets, allowed models, forbidden endpoints |
| `agent_policies` | Many-to-many junction |
| `request_log` | High-volume per-request metrics (tokens, cost, latency, status) |
| `alerts` | Kill switch, anomaly, grounding, and budget alerts |
| `audit_log` | Append-only immutable record of every request (REVOKE UPDATE, DELETE) |
| `compliance_packages` | Generated evidence packages with gap analysis |

---

## WebSocket Feeds

Three real-time feeds (auto-reconnecting via `useWebSocket` hook):

| Path | Payload | Rate |
|---|---|---|
| `/ws/alerts` | Kill switch and anomaly alert objects | On event |
| `/ws/requests` | Completed request summaries (status, latency, model) | Per request |
| `/ws/metrics` | Layer throughput counters | Every 2 s |

---

## Provider Support

Layer 4 supports three provider backends. The target is selected by Layer 2 based on the requested model name:

| Provider | Models | Endpoint |
|---|---|---|
| Anthropic | `claude-*` | `api.anthropic.com/v1/messages` |
| OpenAI | `gpt-*` | `api.openai.com/v1/chat/completions` |
| Ollama | local models | `localhost:11434/api/chat` |
