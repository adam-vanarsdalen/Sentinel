"""Pipeline orchestrator — routes every request through all 7 layers."""
from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from layers.layer1_ingestion import layer1_ingest
from layers.layer2_routing import layer2_route
from layers.layer3_enforcement import layer3_enforce
from layers.layer4_reasoning import layer4_reason
from layers.layer5_grounding import layer5_ground
from layers.layer6_anomaly import layer6_detect
from layers.layer7_compliance import layer7_record, write_block_audit
from models.agent import Agent as AgentModel
from models.policy import Policy as PolicyModel
from schemas.proxy import PipelineError, PipelineRequest, PipelineResponse
from services.kill_switch import KillSwitchService


async def _get_action_count(agent_id: str | None, redis: Redis | None) -> int:
    if not agent_id or not redis:
        return 0
    raw = await redis.get(f"sentinel:agent:{agent_id}:action_count")
    return int(raw) if raw else 0


async def _increment_action_count(agent_id: str | None, redis: Redis | None) -> None:
    if not agent_id or not redis:
        return
    await redis.incr(f"sentinel:agent:{agent_id}:action_count")


async def _record_action(agent_id: str | None, request_id: str, redis: Redis | None) -> None:
    if not agent_id or not redis:
        return
    entry = json.dumps({"request_id": request_id, "ts": datetime.utcnow().isoformat()})
    await redis.lpush(f"sentinel:agent:{agent_id}:recent_actions", entry)
    await redis.ltrim(f"sentinel:agent:{agent_id}:recent_actions", 0, 19)


async def _emit_request_event(
    redis: Redis | None,
    tenant_id: str,
    request_id: str,
    status: str,
    agent_id: str | None,
    model: str | None,
    latency_ms: int,
) -> None:
    if not redis:
        return
    try:
        await redis.publish(
            f"sentinel:requests:{tenant_id}",
            json.dumps({
                "request_id": request_id,
                "status": status,
                "agent_id": agent_id,
                "model": model,
                "latency_ms": latency_ms,
                "ts": datetime.utcnow().isoformat(),
            }),
        )
    except Exception:
        pass


async def process_request(
    raw_request: dict[str, Any],
    source: str,
    tenant_id: str,
    db: AsyncSession | None = None,
    redis: Redis | None = None,
    policy: dict[str, Any] | None = None,
) -> PipelineResponse:
    """Route a raw request through all 7 sentinel layers."""
    kill_switch = KillSwitchService(redis, db) if redis and db else None
    t0 = time.monotonic()

    try:
        # Layer 1: Ingest and normalize
        pipeline_req = await layer1_ingest(raw_request, source, tenant_id)
        _rid = str(pipeline_req.request_id)
        _aid = str(pipeline_req.agent_id) if pipeline_req.agent_id else None

        # Resolve policy for this agent (caller-supplied takes precedence)
        resolved_policy = policy
        if resolved_policy is None and pipeline_req.agent_id and db:
            agent_row = await db.execute(
                select(AgentModel).where(AgentModel.id == pipeline_req.agent_id)
            )
            agent_obj = agent_row.scalar_one_or_none()
            if agent_obj:
                policy_name = agent_obj.name.replace("agent-", "policy-", 1)
                pol_row = await db.execute(
                    select(PolicyModel)
                    .where(
                        PolicyModel.tenant_id == agent_obj.tenant_id,
                        PolicyModel.name == policy_name,
                        PolicyModel.is_active.is_(True),
                    )
                    .order_by(PolicyModel.created_at.desc())
                    .limit(1)
                )
                pol_obj = pol_row.scalar_one_or_none()
                if pol_obj:
                    resolved_policy = {
                        "action_limit_session": pol_obj.action_limit_session,
                        "allowed_models": pol_obj.allowed_models or [],
                        "forbidden_endpoints": pol_obj.forbidden_endpoints or [],
                        "forbidden_data_classes": pol_obj.forbidden_data_classes or [],
                        "budget_daily_usd": pol_obj.budget_daily_usd,
                        "purpose_binding": agent_obj.purpose_binding,
                    }

        # Layer 2: Route and authorize
        routing = await layer2_route(pipeline_req, db=db, policy=resolved_policy)
        if not routing.rbac_passed:
            await _emit_request_event(redis, tenant_id, _rid, "blocked", _aid, None, int((time.monotonic() - t0) * 1000))
            return PipelineResponse(
                request_id=pipeline_req.request_id,
                blocked=True,
                reason=str(routing.rbac_details),
            )

        # Layer 3: Pre-call enforcement (BEFORE model call)
        action_count = await _get_action_count(pipeline_req.agent_id, redis)
        enforcement = await layer3_enforce(
            pipeline_req,
            routing,
            redis=redis,
            policy=resolved_policy,
            action_count=action_count,
        )
        if not enforcement.allowed:
            await write_block_audit(pipeline_req, enforcement, layer=3, db=db)
            if redis:
                await redis.publish(
                    f"sentinel:alerts:{tenant_id}",
                    json.dumps({
                        "type": "block_event",
                        "request_id": _rid,
                        "reason": enforcement.blocked_reason,
                    }),
                )
            # Auto-pause agent when action limit is exhausted
            if (
                kill_switch
                and pipeline_req.agent_id
                and enforcement.action_count_session > 0
                and enforcement.action_count_session >= enforcement.action_limit_session
            ):
                current_state = await kill_switch.get_agent_state(str(pipeline_req.agent_id))
                if current_state == "active":
                    try:
                        await kill_switch.pause(
                            str(pipeline_req.agent_id),
                            reason=f"Action limit exhausted ({enforcement.action_count_session}/{enforcement.action_limit_session}) — awaiting human review",
                            triggered_by="layer3",
                            tenant_id=tenant_id,
                        )
                    except Exception:
                        pass
            await _emit_request_event(redis, tenant_id, _rid, "blocked", _aid, None, int((time.monotonic() - t0) * 1000))
            return PipelineResponse(
                request_id=pipeline_req.request_id,
                blocked=True,
                reason=enforcement.blocked_reason,
            )

        await _increment_action_count(pipeline_req.agent_id, redis)
        await _record_action(pipeline_req.agent_id, pipeline_req.request_id, redis)

        # Layer 4: Execute model call (with tool-call enforcement loop)
        async def enforce_tool_call(tool_call: dict) -> Any:
            tool_req = PipelineRequest(
                request_id=pipeline_req.request_id,
                tenant_id=pipeline_req.tenant_id,
                agent_id=pipeline_req.agent_id,
                source=pipeline_req.source,
                messages=pipeline_req.messages,
                tools=[tool_call],
            )
            return await layer3_enforce(
                tool_req, routing, redis=redis, policy=resolved_policy, action_count=action_count
            )

        model_response = await layer4_reason(pipeline_req, routing, enforce_fn=enforce_tool_call)

        # Layer 5: Verify grounding
        sources = raw_request.get("_sources", [])
        grounding = await layer5_ground(pipeline_req, model_response, sources=sources or None)
        if grounding.grounding_applicable and grounding.score < grounding.block_threshold:
            await _emit_request_event(redis, tenant_id, _rid, "blocked", _aid, routing.target_model, int((time.monotonic() - t0) * 1000))
            return PipelineResponse(
                request_id=pipeline_req.request_id,
                blocked=True,
                reason=f"Grounding score {grounding.score:.2f} below threshold {grounding.block_threshold}",
            )

        # Layer 6: Anomaly detection
        anomaly = await layer6_detect(
            pipeline_req, model_response, redis=redis, kill_switch=kill_switch
        )

        # Layer 7: Audit + compliance record
        await layer7_record(pipeline_req, routing, enforcement, model_response, grounding, anomaly, db=db)

        await _emit_request_event(redis, tenant_id, _rid, "passed", _aid, routing.target_model, int((time.monotonic() - t0) * 1000))
        return PipelineResponse(
            request_id=pipeline_req.request_id,
            blocked=False,
            response=model_response,
            grounding_score=grounding.score,
            anomaly_signals=anomaly.signals if anomaly else [],
        )

    except PipelineError:
        raise
    except Exception as e:
        raise PipelineError(0, "unexpected_error", str(e)) from e
