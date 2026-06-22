"""Layer 3 test coverage — all cases from skills/test-coverage-matrix.md."""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from layers.layer3_enforcement import layer3_enforce
from schemas.proxy import PipelineRequest, RoutingDecision


@pytest.fixture
def req(tenant_id, agent_id):
    return PipelineRequest(
        tenant_id=tenant_id,
        agent_id=agent_id,
        source="api",
        messages=[{"role": "user", "content": "hello"}],
    )


@pytest.fixture
def routing():
    return RoutingDecision(
        target_model="claude-haiku-4-5-20251001",
        target_provider="anthropic",
        routing_reason="test",
        estimated_cost_usd=0.001,
        budget_remaining_usd=100.0,
        rbac_passed=True,
    )


@pytest.fixture
def mock_redis_active():
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)  # None → active
    r.set = AsyncMock()
    return r


# ── Action limits ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_action_limit_n_minus_1_passes(req, routing, mock_redis_active):
    policy = {"action_limit_session": 10}
    result = await layer3_enforce(req, routing, redis=mock_redis_active, policy=policy, action_count=9)
    assert result.allowed is True


@pytest.mark.asyncio
async def test_action_limit_n_blocks(req, routing, mock_redis_active):
    policy = {"action_limit_session": 10}
    result = await layer3_enforce(req, routing, redis=mock_redis_active, policy=policy, action_count=10)
    assert result.allowed is False
    assert "limit" in result.blocked_reason.lower()


@pytest.mark.asyncio
async def test_action_limit_zero_blocks_all(req, routing, mock_redis_active):
    policy = {"action_limit_session": 0}
    result = await layer3_enforce(req, routing, redis=mock_redis_active, policy=policy, action_count=0)
    assert result.allowed is False


@pytest.mark.asyncio
async def test_action_limit_persists_across_calls(req, routing, mock_redis_active):
    policy = {"action_limit_session": 3}
    for i in range(3):
        r = await layer3_enforce(req, routing, redis=mock_redis_active, policy=policy, action_count=i)
        assert r.allowed is True
    blocked = await layer3_enforce(req, routing, redis=mock_redis_active, policy=policy, action_count=3)
    assert blocked.allowed is False


# ── Purpose binding ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_purpose_binding_within_scope_passes(req, routing, mock_redis_active):
    policy = {"action_limit_session": 100, "purpose_binding": "summarize tickets", "forbidden_data_classes": []}
    req.tools = [{"name": "search", "data_class": "tickets"}]
    result = await layer3_enforce(req, routing, redis=mock_redis_active, policy=policy)
    assert result.allowed is True


@pytest.mark.asyncio
async def test_purpose_binding_out_of_scope_blocks(req, routing, mock_redis_active):
    policy = {
        "action_limit_session": 100,
        "purpose_binding": "summarize tickets",
        "forbidden_data_classes": ["financial"],
    }
    req.tools = [{"name": "query_db", "data_class": "financial"}]
    result = await layer3_enforce(req, routing, redis=mock_redis_active, policy=policy)
    assert result.allowed is False


@pytest.mark.asyncio
async def test_purpose_binding_none_blocks_all_tools(req, routing, mock_redis_active):
    policy = {"action_limit_session": 100, "purpose_binding": None, "forbidden_data_classes": []}
    req.tools = [{"name": "any_tool"}]
    result = await layer3_enforce(req, routing, redis=mock_redis_active, policy=policy)
    assert result.allowed is False


@pytest.mark.asyncio
async def test_purpose_binding_message_is_human_readable(req, routing, mock_redis_active):
    policy = {
        "action_limit_session": 100,
        "purpose_binding": "summarize tickets",
        "forbidden_data_classes": ["pii"],
    }
    req.tools = [{"name": "read_user", "data_class": "pii"}]
    result = await layer3_enforce(req, routing, redis=mock_redis_active, policy=policy)
    assert result.allowed is False
    assert result.blocked_reason and len(result.blocked_reason) > 10


# ── Forbidden endpoints ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_forbidden_endpoint_exact_match_blocks(req, routing, mock_redis_active):
    policy = {"action_limit_session": 100, "forbidden_endpoints": ["/admin/delete"], "purpose_binding": "ops"}
    req.tools = [{"name": "call", "url": "/admin/delete"}]
    result = await layer3_enforce(req, routing, redis=mock_redis_active, policy=policy)
    assert result.allowed is False


@pytest.mark.asyncio
async def test_forbidden_endpoint_prefix_match_blocks(req, routing, mock_redis_active):
    policy = {"action_limit_session": 100, "forbidden_endpoints": ["/admin/*"], "purpose_binding": "ops"}
    req.tools = [{"name": "call", "url": "/admin/users/delete"}]
    result = await layer3_enforce(req, routing, redis=mock_redis_active, policy=policy)
    assert result.allowed is False


@pytest.mark.asyncio
async def test_forbidden_endpoint_non_matching_passes(req, routing, mock_redis_active):
    policy = {"action_limit_session": 100, "forbidden_endpoints": ["/admin/*"], "purpose_binding": "search"}
    req.tools = [{"name": "call", "url": "/api/search"}]
    result = await layer3_enforce(req, routing, redis=mock_redis_active, policy=policy)
    assert result.allowed is True


@pytest.mark.asyncio
async def test_forbidden_data_class_blocks(req, routing, mock_redis_active):
    policy = {
        "action_limit_session": 100,
        "forbidden_data_classes": ["pii"],
        "purpose_binding": "support",
    }
    req.tools = [{"name": "read", "data_class": "pii"}]
    result = await layer3_enforce(req, routing, redis=mock_redis_active, policy=policy)
    assert result.allowed is False


# ── Kill switch states ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_kill_switch_active_proceeds_to_policy_checks(req, routing):
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=b"active")
    policy = {"action_limit_session": 100}
    result = await layer3_enforce(req, routing, redis=redis, policy=policy, action_count=0)
    assert result.allowed is True


@pytest.mark.asyncio
async def test_kill_switch_throttled_first_call_passes(req, routing):
    redis = AsyncMock()
    # state=throttled, no throttle_ts yet
    async def mock_get(key):
        if key.endswith(":state"):
            return b"throttled"
        return None  # no throttle_ts
    redis.get = AsyncMock(side_effect=mock_get)
    redis.set = AsyncMock()
    policy = {"action_limit_session": 100}
    result = await layer3_enforce(req, routing, redis=redis, policy=policy)
    assert result.allowed is True


@pytest.mark.asyncio
async def test_kill_switch_throttled_second_call_within_window_blocks(req, routing):
    redis = AsyncMock()
    recent_ts = (datetime.now(timezone.utc) - timedelta(seconds=3)).isoformat()

    async def mock_get(key):
        if key.endswith(":state"):
            return b"throttled"
        if key.endswith(":throttle_ts"):
            return recent_ts.encode()
        return None
    redis.get = AsyncMock(side_effect=mock_get)
    redis.set = AsyncMock()
    policy = {"action_limit_session": 100}
    result = await layer3_enforce(req, routing, redis=redis, policy=policy)
    assert result.allowed is False
    assert "Throttled" in result.blocked_reason


@pytest.mark.asyncio
async def test_kill_switch_throttled_call_after_window_passes(req, routing):
    redis = AsyncMock()
    old_ts = (datetime.now(timezone.utc) - timedelta(seconds=15)).isoformat()

    async def mock_get(key):
        if key.endswith(":state"):
            return b"throttled"
        if key.endswith(":throttle_ts"):
            return old_ts.encode()
        return None
    redis.get = AsyncMock(side_effect=mock_get)
    redis.set = AsyncMock()
    policy = {"action_limit_session": 100}
    result = await layer3_enforce(req, routing, redis=redis, policy=policy)
    assert result.allowed is True


@pytest.mark.asyncio
async def test_kill_switch_paused_all_calls_return_queued(req, routing):
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=b"paused")
    policy = {"action_limit_session": 100}
    result = await layer3_enforce(req, routing, redis=redis, policy=policy)
    assert result.allowed is False
    assert "paused" in result.blocked_reason.lower()


@pytest.mark.asyncio
async def test_kill_switch_paused_nothing_executes(req, routing):
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=b"paused")
    policy = {"action_limit_session": 100}
    result = await layer3_enforce(req, routing, redis=redis, policy=policy)
    assert result.allowed is False


@pytest.mark.asyncio
async def test_kill_switch_terminated_all_calls_blocked(req, routing):
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=b"terminated")
    policy = {"action_limit_session": 100}
    result = await layer3_enforce(req, routing, redis=redis, policy=policy)
    assert result.allowed is False


@pytest.mark.asyncio
async def test_kill_switch_terminated_reason_includes_terminated(req, routing):
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=b"terminated")
    policy = {"action_limit_session": 100}
    result = await layer3_enforce(req, routing, redis=redis, policy=policy)
    assert "terminated" in result.blocked_reason.lower()


# ── Tool call interception ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tool_call_allowed_by_policy_executes(req, routing, mock_redis_active):
    policy = {"action_limit_session": 100, "forbidden_endpoints": [], "purpose_binding": "search"}
    req.tools = [{"name": "allowed_tool", "url": "/api/safe"}]
    result = await layer3_enforce(req, routing, redis=mock_redis_active, policy=policy)
    assert result.allowed is True


@pytest.mark.asyncio
async def test_tool_call_blocked_by_policy_returns_denial(req, routing, mock_redis_active):
    policy = {"action_limit_session": 100, "forbidden_endpoints": ["/danger"], "purpose_binding": "ops"}
    req.tools = [{"name": "danger", "url": "/danger"}]
    result = await layer3_enforce(req, routing, redis=mock_redis_active, policy=policy)
    assert result.allowed is False
    assert result.blocked_reason is not None


@pytest.mark.asyncio
async def test_tool_call_blocked_does_not_appear_in_tool_results(req, routing, mock_redis_active):
    policy = {"action_limit_session": 100, "forbidden_endpoints": ["/secret"], "purpose_binding": "ops"}
    req.tools = [{"name": "secret_call", "url": "/secret"}]
    result = await layer3_enforce(req, routing, redis=mock_redis_active, policy=policy)
    assert result.allowed is False


@pytest.mark.asyncio
async def test_tool_call_denial_message_is_actionable(req, routing, mock_redis_active):
    policy = {"action_limit_session": 100, "forbidden_endpoints": ["/admin/*"], "purpose_binding": "ops"}
    req.tools = [{"name": "admin_op", "url": "/admin/reset"}]
    result = await layer3_enforce(req, routing, redis=mock_redis_active, policy=policy)
    assert result.allowed is False
    assert len(result.blocked_reason) > 20


@pytest.mark.asyncio
async def test_interception_loop_reruns_on_each_tool_call(req, routing, mock_redis_active):
    policy = {"action_limit_session": 100, "forbidden_endpoints": ["/bad"], "purpose_binding": "ops"}
    req.tools = [{"name": "safe", "url": "/ok"}, {"name": "bad", "url": "/bad"}]
    result = await layer3_enforce(req, routing, redis=mock_redis_active, policy=policy)
    assert result.allowed is False


# ── Audit and alert ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_block_writes_to_audit_before_returning(req, routing, mock_redis_active):
    from layers.layer7_compliance import write_block_audit
    written = []

    async def fake_write(r, e, layer, db):
        written.append(e.blocked_reason)

    policy = {"action_limit_session": 0}
    result = await layer3_enforce(req, routing, redis=mock_redis_active, policy=policy, action_count=0)
    assert result.allowed is False


@pytest.mark.asyncio
async def test_block_emits_alert_to_redis_pubsub(req, routing):
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=b"terminated")
    redis.publish = AsyncMock()
    policy = {"action_limit_session": 100}
    result = await layer3_enforce(req, routing, redis=redis, policy=policy)
    assert result.allowed is False
