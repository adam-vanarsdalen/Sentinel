"""Layer 3: Pre-call Enforcement — kill switch, purpose binding, action limits, endpoint blocking."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from redis.asyncio import Redis

from schemas.proxy import EnforcementCheck, PipelineRequest, RoutingDecision


async def _check_kill_switch(agent_id: str, redis: Redis) -> EnforcementCheck | None:
    """Check kill switch state per spec. Returns EnforcementCheck if blocked, None if clear."""
    state_raw = await redis.get(f"sentinel:agent:{agent_id}:state")
    state = state_raw.decode() if state_raw else "active"

    if state == "terminated":
        return EnforcementCheck(
            allowed=False,
            blocked_reason="Agent terminated — all calls blocked",
        )

    if state == "paused":
        return EnforcementCheck(
            allowed=False,
            blocked_reason="Agent paused — queued for human review",
        )

    if state == "throttled":
        last_ts_raw = await redis.get(f"sentinel:agent:{agent_id}:throttle_ts")
        if last_ts_raw:
            elapsed = (
                datetime.now(timezone.utc)
                - datetime.fromisoformat(last_ts_raw.decode())
            ).total_seconds()
            if elapsed < 10:
                return EnforcementCheck(
                    allowed=False,
                    blocked_reason=f"Throttled — {10 - elapsed:.1f}s remaining in window",
                )
        await redis.set(
            f"sentinel:agent:{agent_id}:throttle_ts",
            datetime.now(timezone.utc).isoformat(),
        )

    return None  # active or throttled-but-window-passed — proceed to policy checks


def _check_action_limit(
    action_count: int, action_limit: int
) -> EnforcementCheck | None:
    if action_limit == 0:
        return EnforcementCheck(
            allowed=False,
            blocked_reason="Action limit is 0 — all calls blocked by policy",
            action_count_session=action_count,
            action_limit_session=action_limit,
        )
    if action_count >= action_limit:
        return EnforcementCheck(
            allowed=False,
            blocked_reason=f"Session action limit reached ({action_count}/{action_limit})",
            action_count_session=action_count,
            action_limit_session=action_limit,
        )
    return None


def _check_purpose_binding(
    req: PipelineRequest,
    purpose: str | None,
    data_classes_requested: list[str],
    forbidden_data_classes: list[str],
) -> EnforcementCheck | None:
    if purpose is None and req.tools:
        return EnforcementCheck(
            allowed=False,
            blocked_reason="Agent has no declared purpose — tool calls are blocked",
        )

    for dc in data_classes_requested:
        if dc in forbidden_data_classes:
            return EnforcementCheck(
                allowed=False,
                blocked_reason=f"Data class '{dc}' is outside agent's declared purpose: {purpose}",
            )
    return None


def _check_forbidden_endpoints(
    endpoints_requested: list[str], forbidden_endpoints: list[str]
) -> EnforcementCheck | None:
    for ep in endpoints_requested:
        for pattern in forbidden_endpoints:
            if pattern.endswith("/*"):
                prefix = pattern[:-2]
                if ep.startswith(prefix):
                    return EnforcementCheck(
                        allowed=False,
                        blocked_reason=f"Endpoint '{ep}' matches forbidden pattern '{pattern}'",
                        forbidden_endpoints=[pattern],
                    )
            elif ep == pattern:
                return EnforcementCheck(
                    allowed=False,
                    blocked_reason=f"Endpoint '{ep}' is on the forbidden list",
                    forbidden_endpoints=[pattern],
                )
    return None


def _extract_tool_endpoints(tools: list[dict[str, Any]] | None) -> list[str]:
    if not tools:
        return []
    endpoints = []
    for tool in tools:
        if url := tool.get("url") or tool.get("endpoint"):
            endpoints.append(url)
        name = tool.get("name") or tool.get("function", {}).get("name", "")
        if name:
            endpoints.append(name)
    return endpoints


def _extract_data_classes(tools: list[dict[str, Any]] | None) -> list[str]:
    if not tools:
        return []
    classes = []
    for tool in tools:
        dc = tool.get("data_class") or tool.get("function", {}).get("data_class")
        if dc:
            classes.append(dc)
    return classes


async def layer3_enforce(
    req: PipelineRequest,
    routing: RoutingDecision,
    redis: Redis | None = None,
    policy: dict[str, Any] | None = None,
    action_count: int = 0,
) -> EnforcementCheck:
    """Pre-call enforcement. Runs BEFORE provider API call."""
    p = policy or {}
    action_limit = p.get("action_limit_session", 1000)
    forbidden_endpoints = p.get("forbidden_endpoints", [])
    forbidden_data_classes = p.get("forbidden_data_classes", [])
    purpose = p.get("purpose_binding") or (
        req.agent_id and p.get("purpose_binding")
    )

    # 1. Kill switch check (requires Redis)
    if redis and req.agent_id:
        block = await _check_kill_switch(req.agent_id, redis)
        if block:
            return block

    # 2. Action limit
    block = _check_action_limit(action_count, action_limit)
    if block:
        block.action_count_session = action_count
        block.action_limit_session = action_limit
        return block

    # 3. Purpose binding
    data_classes = _extract_data_classes(req.tools)
    block = _check_purpose_binding(req, purpose, data_classes, forbidden_data_classes)
    if block:
        block.purpose_binding = purpose
        return block

    # 4. Forbidden endpoints
    endpoints = _extract_tool_endpoints(req.tools)
    block = _check_forbidden_endpoints(endpoints, forbidden_endpoints)
    if block:
        return block

    return EnforcementCheck(
        allowed=True,
        action_count_session=action_count,
        action_limit_session=action_limit,
        purpose_binding=purpose,
        data_classes_accessed=data_classes,
    )
