# Kill Switch State Machine

## States
active      — normal operation, all calls pass to Layer 3 enforcement checks
throttled   — 1 call per 10 seconds max, enforced via Layer 3 rate check
paused      — all calls queued for human review, no execution until resumed
terminated  — all calls blocked, session credentials revoked, permanent until manual resume

## Redis key format
sentinel:agent:{agent_id}:state        → string: "active"|"throttled"|"paused"|"terminated"
sentinel:agent:{agent_id}:state_reason → string: human-readable reason
sentinel:agent:{agent_id}:state_ts     → string: ISO timestamp of last transition
sentinel:agent:{agent_id}:throttle_ts  → string: timestamp of last allowed call (for throttle enforcement)

## Transition rules
active      → throttled: Layer 6 z-score 3.5–5.0σ, or operator action
active      → paused:    Layer 6 z-score 5.0–7.0σ, or operator action
active      → terminated: Layer 6 z-score >7.0σ, or operator manual fire
throttled   → paused:    Layer 6 escalation or operator action
throttled   → active:    operator resume only
paused      → active:    operator resume only (requires operator_id)
paused      → terminated: operator action or Layer 6 escalation
terminated  → active:    operator resume only (requires operator_id + reason)

## Audit requirement
Every state transition MUST write to audit_log BEFORE the Redis write.
If the audit write fails, abort the transition. Redis is the source of truth for
current state. PostgreSQL audit_log is the source of truth for history.

## Layer 3 check pattern
state = await redis.get(f"sentinel:agent:{agent_id}:state")
if state == "terminated": block, reason="Agent terminated"
if state == "paused": queue for review, reason="Agent paused pending review"
if state == "throttled": check throttle_ts, enforce 10s window
if state == "active" or state is None: proceed to policy checks
