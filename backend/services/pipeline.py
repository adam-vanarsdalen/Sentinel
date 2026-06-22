"""Pipeline orchestrator — routes every request through all 7 layers."""
from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from layers.layer1_ingestion import layer1_ingest
from layers.layer2_routing import layer2_route
from layers.layer3_enforcement import layer3_enforce
from layers.layer4_reasoning import layer4_reason
from layers.layer5_grounding import layer5_ground
from layers.layer6_anomaly import layer6_detect
from layers.layer7_compliance import layer7_record, write_block_audit
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
    entry = json.dumps({"request_id": request_id, "ts": __import__("datetime").datetime.utcnow().isoformat()})
    await redis.lpush(f"sentinel:agent:{agent_id}:recent_actions", entry)
    await redis.ltrim(f"sentinel:agent:{agent_id}:recent_actions", 0, 19)


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

    try:
        # Layer 1: Ingest and normalize
        pipeline_req = await layer1_ingest(raw_request, source, tenant_id)

        # Layer 2: Route and authorize
        routing = await layer2_route(pipeline_req, db=db, policy=policy)
        if not routing.rbac_passed:
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
            policy=policy,
            action_count=action_count,
        )
        if not enforcement.allowed:
            await write_block_audit(pipeline_req, enforcement, layer=3, db=db)
            if redis:
                import json as _json
                await redis.publish(
                    f"sentinel:alerts:{tenant_id}",
                    _json.dumps({
                        "type": "block_event",
                        "request_id": pipeline_req.request_id,
                        "reason": enforcement.blocked_reason,
                    }),
                )
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
                tool_req, routing, redis=redis, policy=policy, action_count=action_count
            )

        model_response = await layer4_reason(pipeline_req, routing, enforce_fn=enforce_tool_call)

        # Layer 5: Verify grounding
        sources = raw_request.get("_sources", [])
        grounding = await layer5_ground(pipeline_req, model_response, sources=sources or None)
        if grounding.grounding_applicable and grounding.score < grounding.block_threshold:
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
