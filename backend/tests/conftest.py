"""Shared test fixtures."""
from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock

import pytest

from schemas.proxy import PipelineRequest, RoutingDecision


@pytest.fixture
def tenant_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def agent_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def base_request(tenant_id, agent_id) -> PipelineRequest:
    return PipelineRequest(
        tenant_id=tenant_id,
        agent_id=agent_id,
        source="api",
        messages=[{"role": "user", "content": "hello"}],
    )


@pytest.fixture
def routing() -> RoutingDecision:
    return RoutingDecision(
        target_model="claude-haiku-4-5-20251001",
        target_provider="anthropic",
        routing_reason="test",
        estimated_cost_usd=0.001,
        budget_remaining_usd=100.0,
        rbac_passed=True,
    )


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.pipeline = AsyncMock()
    pipe = AsyncMock()
    pipe.set = AsyncMock()
    pipe.execute = AsyncMock()
    redis.pipeline.return_value = pipe
    redis.publish = AsyncMock()
    return redis
