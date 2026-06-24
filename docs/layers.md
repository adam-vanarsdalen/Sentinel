# Layer Reference

All seven layers are implemented as async functions in `backend/layers/`. Each layer receives a well-defined input and produces a well-defined output. The pipeline orchestrator (`services/pipeline.py`) calls them in order.

---

## Layer 1 — Ingestion

**File:** `backend/layers/layer1_ingestion.py`

**Purpose:** Normalize incoming requests to a canonical internal format, tag provenance, estimate token cost.

**Input:** Raw HTTP request body (OpenAI or Anthropic format)

**Output:** `PipelineRequest`
```python
class PipelineRequest:
    request_id: str          # UUID4, generated here, threads through all layers
    tenant_id: str
    agent_id: str
    messages: list[dict]     # OpenAI-format messages, always
    tools: list[dict]        # Tool definitions if present
    model_requested: str
    source: str              # "openai" | "anthropic"
    input_tokens_estimate: int
    provenance_tags: dict    # metadata about the origin of the request
```

**Behavior:**
- Detects request format (OpenAI vs Anthropic) by inspecting the payload structure.
- Converts Anthropic `/messages` format to OpenAI-compatible internally.
- Uses `tiktoken` (cl100k_base encoding) to estimate input token count.
- Generates UUID4 `request_id` — this is the canonical correlation key for the entire pipeline.

**Regulatory controls:** EU AI Act Art. 12, NIST GOVERN-1.1, HIPAA 164.312(b)

---

## Layer 2 — Routing

**File:** `backend/layers/layer2_routing.py`

**Purpose:** Select the target model and provider, enforce RBAC, check budget limits.

**Input:** `PipelineRequest`

**Output:** `RoutingDecision`
```python
class RoutingDecision:
    target_model: str
    target_provider: str     # "anthropic" | "openai" | "ollama"
    estimated_cost_usd: float
    rbac_passed: bool
    rbac_details: dict       # which checks passed/failed and why
```

**Behavior:**
- Maps the requested model name to a provider.
- Estimates request cost based on model pricing and estimated token count.
- Checks whether the requesting agent's role permits the requested model (RBAC).
- Validates hourly, daily, and monthly budget limits against the agent's policy.
- Rejects the request (allowed=False) if any budget is exceeded.

**Regulatory controls:** EU AI Act Art. 9, NIST GOVERN-1.2/GOVERN-1.4, Colorado SB205 §6-1-1702(b)

---

## Layer 3 — Pre-call Enforcement ★

**File:** `backend/layers/layer3_enforcement.py`

**Purpose:** The last gate before the model is called. Enforces kill switch state, session action limits, purpose binding, and forbidden endpoint policies.

**Input:** `PipelineRequest`, `RoutingDecision`, Redis connection, policy dict, session action count

**Output:** `EnforcementCheck`
```python
class EnforcementCheck:
    allowed: bool
    blocked_reason: str | None
    action_count_session: int
    forbidden_endpoints: list[str]   # patterns that were checked
```

**Checks run in this order:**

1. **Kill switch** — reads agent state from Redis:
   - `terminated` → block immediately
   - `paused` → block (queue for human review)
   - `throttled` → allow if ≥10 s since last call, otherwise block with remaining seconds
   - `active` → proceed

2. **Action limit** — if `action_count_session >= policy.action_limit_session`, block.

3. **Purpose binding** — if the request accesses a data class not in the agent's declared purpose, block.

4. **Forbidden endpoints** — if a tool in the request calls a URL that matches any forbidden pattern, block.

When `allowed=False`, the orchestrator writes a block audit entry (via `layer7_compliance.write_block_audit()`) and returns an error response to the caller. The provider API is never called.

**Tool-call interception:** During Layer 4 execution, each tool call the model wants to make is re-routed through Layer 3 before execution. If Layer 3 blocks the tool call, the model receives a denial message rather than a result.

**Regulatory controls:** EU AI Act Art. 14, NIST MANAGE-1.3, HIPAA 164.308(a)(3), Colorado SB205 §6-1-1702(c)

---

## Layer 4 — Reasoning

**File:** `backend/layers/layer4_reasoning.py`

**Purpose:** Execute the model via the appropriate provider API, with a tool-call interception loop.

**Input:** `PipelineRequest`, `RoutingDecision`

**Output:** `ModelResponse`
```python
class ModelResponse:
    content: str
    tool_calls: list[dict]
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: float
    provider: str
    model: str
    finish_reason: str
```

**Behavior:**
- Routes to `_call_anthropic()`, `_call_openai()`, or `_call_ollama()` based on `RoutingDecision.target_provider`.
- Runs a tool-call interception loop (max 20 rounds): if the model emits a tool call, Layer 4 passes it through Layer 3 enforcement before executing it and returning the result to the model.
- Tracks cumulative token counts and cost across all rounds.

**Regulatory controls:** EU AI Act Art. 13, NIST MAP-1.1

---

## Layer 5 — Grounding

**File:** `backend/layers/layer5_grounding.py`

**Purpose:** Verify model response claims against provided sources; detect hallucinations; escalate low-confidence responses.

**Input:** `PipelineRequest`, `ModelResponse`, `sources: list[str]` (optional)

**Output:** `GroundingResult`
```python
class GroundingResult:
    score: float             # 0.0–1.0
    grounded_claims: list[str]
    ungrounded_claims: list[str]
    grounding_applicable: bool   # False if no sources were provided
```

**Behavior:**
- Splits the response into individual claims (sentences > 20 characters).
- Scores each claim by computing word overlap between the claim and the provided sources.
- Overall score is the fraction of claims that are grounded.
- If no sources are provided, `grounding_applicable=False` and the response passes through.
- Score thresholds (configurable via `.env`):
  - `≥ GROUNDING_WARN_THRESHOLD (0.8)` — pass, no action
  - `0.5–0.8` — pass with a warning attached to the audit entry
  - `< GROUNDING_BLOCK_THRESHOLD (0.5)` — block, queue for human review, emit alert

**Regulatory controls:** EU AI Act Art. 15, NIST MEASURE-2.5, Colorado SB205 §6-1-1702(a)

---

## Layer 6 — Anomaly Detection ★

**File:** `backend/layers/layer6_anomaly.py`

**Purpose:** Detect behavioral drift from established baselines and apply graduated automatic containment.

**Input:** `PipelineRequest`, `ModelResponse`, Redis connection, `KillSwitchService`

**Output:** `AnomalyResult | None` (None if no anomaly detected)
```python
class AnomalyResult:
    agent_id: str
    signals: list[AnomalySignal]   # individual dimension scores
    combined_score: float           # weighted z-score
    recommended_action: str         # "log" | "throttle" | "pause" | "terminate"
    state_snapshot: dict            # last 20 actions + in-flight request IDs
```

**Behavioral dimensions tracked:**
- Request cost (USD)
- Latency (ms)
- Error rate (rolling)
- New data classes (unseen in 7-day baseline)
- New tool patterns (unseen in 7-day baseline)

**Baseline algorithm:** Welford online algorithm stored as JSON in Redis at `sentinel:agent:{agent_id}:baseline`. No raw history is stored — only running count, mean, and M2 (sum of squared deviations). Updated on every request.

**Graduated containment thresholds** (configurable):

| Combined z-score | Action | KillSwitchService call |
|---|---|---|
| ≥ 2.5σ, < 3.5σ | Log | None |
| ≥ 3.5σ, < 5.0σ | Throttle | `kill_switch.throttle()` |
| ≥ 5.0σ, < 7.0σ | Pause | `kill_switch.pause()` |
| ≥ 7.0σ | Terminate | `kill_switch.terminate()` |

**Warmup:** First 10 requests from any agent skip containment checks while the baseline is being established. Anomaly signals are still logged.

**Cross-agent detection:** When 2+ agents in the same tenant trigger anomalies simultaneously, a tenant-level alert is emitted.

**Regulatory controls:** EU AI Act Art. 9, NIST MEASURE-2.2/MANAGE-2.2

---

## Layer 7 — Compliance Output ★

**File:** `backend/layers/layer7_compliance.py`

**Purpose:** Write an immutable, regulation-mapped audit record for every request.

**Input:** `PipelineRequest`, `RoutingDecision`, `EnforcementCheck`, `ModelResponse`, `GroundingResult`, `AnomalyResult`

**Output:** `AuditEntry` (written to database)
```python
class AuditEntry:
    id: int                     # BIGSERIAL, append-only
    request_id: str             # UUID4 from Layer 1
    tenant_id: str
    agent_id: str
    action: str
    layer: int                  # layer that determined the final status
    status: str                 # "passed" | "blocked" | "flagged" | "error"
    model: str
    latency_ms: float
    metadata: dict              # layer-specific details
    regulation_mappings: dict   # control IDs by regulation
    created_at: datetime
```

**Behavior:**
- Determines the request's final status based on outputs from Layers 3, 5, and 6.
- Looks up regulation control IDs for the relevant layer via `regulatory/mapper.py`.
- Writes to `audit_log`. This table has `UPDATE` and `DELETE` revoked at the PostgreSQL role level — the insert will succeed, but any later modification attempt will raise a permission error.

**Append-only enforcement** (from Alembic migration `0001_initial_schema.py`):
```sql
REVOKE UPDATE, DELETE ON audit_log FROM sentinel_app;
GRANT INSERT, SELECT ON audit_log TO sentinel_app;
```

**Compliance package generation** (`services/compliance_generator.py`):
- Accepts a tenant ID, time range, and list of target regulations.
- Queries `audit_log` and groups entries by regulation control ID.
- Runs gap analysis: for each required control ID, checks whether at least one qualifying entry exists (status ≠ "error").
- Produces a `CompliancePackage` with an evidence index and gap descriptions.
- Exports: JSON (always available), PDF (WeasyPrint), CSV (pandas).

**Regulatory controls:** EU AI Act Arts. 11/12, NIST GOVERN-6.1, HIPAA 164.312(b)
