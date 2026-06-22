"""Layer 6: Anomaly Detection — behavioral baseline tracking and graduated containment."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from redis.asyncio import Redis

from config import settings
from schemas.proxy import AnomalyResult, AnomalySignal, ModelResponse, PipelineRequest

NEW_AGENT_WARMUP = 10


def _z_score(observed: float, mean: float, std: float) -> float:
    if std == 0:
        return 0.0
    return (observed - mean) / std


def _action_from_z(z: float) -> str:
    if z >= settings.anomaly_terminate_sigma:
        return "terminate"
    if z >= settings.anomaly_pause_sigma:
        return "pause"
    if z >= settings.anomaly_throttle_sigma:
        return "throttle"
    if z >= settings.anomaly_log_sigma:
        return "log"
    return "none"


async def _get_baseline(agent_id: str, redis: Redis) -> dict[str, Any]:
    raw = await redis.get(f"sentinel:agent:{agent_id}:baseline")
    if not raw:
        return {}
    return json.loads(raw)


async def _update_baseline(
    agent_id: str,
    redis: Redis,
    cost: float,
    data_classes: list[str],
    is_error: bool,
    tools_used: list[str],
    latency_ms: int,
) -> None:
    baseline = await _get_baseline(agent_id, redis)
    count = baseline.get("count", 0) + 1

    def update_rolling(key_mean: str, key_m2: str, val: float) -> None:
        n = count
        mean = baseline.get(key_mean, 0.0)
        m2 = baseline.get(key_m2, 0.0)
        delta = val - mean
        mean += delta / n
        delta2 = val - mean
        m2 += delta * delta2
        baseline[key_mean] = mean
        baseline[key_m2] = m2

    update_rolling("cost_mean", "cost_m2", cost)
    update_rolling("latency_mean", "latency_m2", latency_ms)
    error_rate = baseline.get("error_rate", 0.0)
    baseline["error_rate"] = error_rate + (1 if is_error else 0) / count
    baseline["count"] = count

    seen_classes: set[str] = set(baseline.get("seen_data_classes", []))
    seen_classes.update(data_classes)
    baseline["seen_data_classes"] = list(seen_classes)

    seen_tools: set[str] = set(baseline.get("seen_tools", []))
    seen_tools.update(tools_used)
    baseline["seen_tools"] = list(seen_tools)

    baseline["last_seen"] = datetime.now(timezone.utc).isoformat()

    await redis.set(f"sentinel:agent:{agent_id}:baseline", json.dumps(baseline))


async def _capture_state_snapshot(agent_id: str, redis: Redis) -> dict[str, Any]:
    recent_raw = await redis.lrange(f"sentinel:agent:{agent_id}:recent_actions", 0, 19)
    inflight_raw = await redis.smembers(f"sentinel:agent:{agent_id}:inflight")
    return {
        "last_20_actions": [json.loads(r) for r in recent_raw],
        "inflight_request_ids": [r.decode() for r in inflight_raw],
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }


async def layer6_detect(
    req: PipelineRequest,
    response: ModelResponse,
    redis: Redis | None = None,
    kill_switch: Any = None,
) -> AnomalyResult | None:
    """Detect behavioral anomalies and trigger graduated containment."""
    if not redis or not req.agent_id:
        return None

    agent_id = req.agent_id
    baseline = await _get_baseline(agent_id, redis)
    count = baseline.get("count", 0)

    # Warmup: no containment for first N requests
    if count < NEW_AGENT_WARMUP:
        await _update_baseline(
            agent_id, redis,
            cost=response.cost_usd,
            data_classes=[],
            is_error=response.finish_reason == "error",
            tools_used=[tc.get("name", "") for tc in (response.tool_calls or [])],
            latency_ms=response.latency_ms,
        )
        return None

    signals: list[AnomalySignal] = []

    # Cost anomaly
    cost_mean = baseline.get("cost_mean", 0.0)
    cost_m2 = baseline.get("cost_m2", 0.0)
    cost_std = (cost_m2 / max(count - 1, 1)) ** 0.5
    cost_z = _z_score(response.cost_usd, cost_mean, cost_std)
    if cost_z >= settings.anomaly_log_sigma:
        signals.append(AnomalySignal(
            signal_type="cost",
            severity=min(cost_z / 10, 1.0),
            baseline_value=cost_mean,
            observed_value=response.cost_usd,
            deviation_factor=cost_z,
        ))

    # Data access anomaly (new data class never seen in baseline)
    seen_classes: set[str] = set(baseline.get("seen_data_classes", []))
    new_classes = [dc for dc in req.provenance_tags.get("data_classes", []) if dc not in seen_classes]
    if new_classes:
        signals.append(AnomalySignal(
            signal_type="data_access",
            severity=0.8,
            baseline_value=0.0,
            observed_value=float(len(new_classes)),
            deviation_factor=settings.anomaly_throttle_sigma,
        ))

    # Error rate anomaly
    is_error = response.finish_reason in ("error", "stop_sequence")
    baseline_error_rate = baseline.get("error_rate", 0.0)
    error_m2 = baseline.get("error_m2", 0.0)
    error_std = (error_m2 / max(count - 1, 1)) ** 0.5
    current_error = 1.0 if is_error else 0.0
    error_z = _z_score(current_error, baseline_error_rate, max(error_std, 0.01))
    if error_z >= settings.anomaly_log_sigma:
        signals.append(AnomalySignal(
            signal_type="error_rate",
            severity=min(error_z / 10, 1.0),
            baseline_value=baseline_error_rate,
            observed_value=current_error,
            deviation_factor=error_z,
        ))

    # Tool pattern anomaly (new tool never used in baseline)
    seen_tools: set[str] = set(baseline.get("seen_tools", []))
    new_tools = [
        tc.get("name", "") for tc in (response.tool_calls or [])
        if tc.get("name") and tc.get("name") not in seen_tools
    ]
    if new_tools:
        signals.append(AnomalySignal(
            signal_type="tool_pattern",
            severity=0.7,
            baseline_value=0.0,
            observed_value=float(len(new_tools)),
            deviation_factor=settings.anomaly_throttle_sigma,
        ))

    await _update_baseline(
        agent_id, redis,
        cost=response.cost_usd,
        data_classes=req.provenance_tags.get("data_classes", []),
        is_error=is_error,
        tools_used=[tc.get("name", "") for tc in (response.tool_calls or [])],
        latency_ms=response.latency_ms,
    )

    if not signals:
        return None

    combined_z = max(s.deviation_factor for s in signals)
    action = _action_from_z(combined_z)

    snapshot: dict[str, Any] = {}
    if action != "none" and action != "log":
        snapshot = await _capture_state_snapshot(agent_id, redis)

    result = AnomalyResult(
        agent_id=agent_id,
        signals=signals,
        combined_score=combined_z,
        recommended_action=action,
        state_snapshot=snapshot,
    )

    if kill_switch and action != "none" and action != "log":
        reason = f"Layer 6 anomaly: combined z={combined_z:.2f}σ"
        tenant_id = req.tenant_id
        if action == "throttle":
            await kill_switch.throttle(agent_id, reason, tenant_id=tenant_id)
        elif action == "pause":
            await kill_switch.pause(agent_id, reason, tenant_id=tenant_id)
        elif action == "terminate":
            await kill_switch.terminate(agent_id, reason, tenant_id=tenant_id)

    return result
