"""Layer 7: Compliance Output — append-only audit log, regulation-mapped evidence packages."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from regulatory.mapper import get_controls_for_layer
from schemas.proxy import (
    AnomalyResult,
    AuditEntry,
    EnforcementCheck,
    GroundingResult,
    ModelResponse,
    PipelineRequest,
    RoutingDecision,
)


async def layer7_record(
    req: PipelineRequest,
    routing: RoutingDecision,
    enforcement: EnforcementCheck,
    response: ModelResponse,
    grounding: GroundingResult,
    anomaly: AnomalyResult | None,
    db: AsyncSession | None = None,
) -> AuditEntry:
    """Write immutable audit record for this request through all layers."""
    status = "passed"
    if not enforcement.allowed:
        status = "blocked"
    elif grounding.grounding_applicable and grounding.score < grounding.block_threshold:
        status = "flagged"
    elif anomaly and anomaly.recommended_action not in ("none", "log"):
        status = "flagged"

    layer = 7
    regulation_mappings = get_controls_for_layer(layer)

    metadata: dict[str, Any] = {
        "routing_reason": routing.routing_reason,
        "enforcement_allowed": enforcement.allowed,
        "grounding_score": grounding.score,
        "grounding_applicable": grounding.grounding_applicable,
        "anomaly_action": anomaly.recommended_action if anomaly else None,
        "anomaly_z": anomaly.combined_score if anomaly else None,
        "cost_usd": response.cost_usd,
    }

    entry = AuditEntry(
        request_id=req.request_id,
        tenant_id=req.tenant_id,
        agent_id=req.agent_id,
        action="pipeline_complete",
        layer=layer,
        status=status,
        model=response.model,
        source=req.source,
        latency_ms=response.latency_ms,
        metadata=metadata,
        regulation_mappings=regulation_mappings,
    )

    if db:
        from models.audit_entry import AuditEntry as AuditEntryModel
        row = AuditEntryModel(
            request_id=req.request_id,  # type: ignore[arg-type]
            tenant_id=req.tenant_id,  # type: ignore[arg-type]
            agent_id=req.agent_id,  # type: ignore[arg-type]
            action=entry.action,
            layer=entry.layer,
            status=entry.status,
            model=entry.model,
            source=entry.source,
            latency_ms=entry.latency_ms,
            metadata_=entry.metadata,
            regulation_mappings=entry.regulation_mappings,
        )
        db.add(row)
        await db.flush()

    return entry


async def write_block_audit(
    req: PipelineRequest,
    enforcement: EnforcementCheck,
    layer: int,
    db: AsyncSession | None = None,
) -> None:
    """Write audit entry for a blocked request. Called before returning the block."""
    regulation_mappings = get_controls_for_layer(layer)

    if db:
        from models.audit_entry import AuditEntry as AuditEntryModel
        row = AuditEntryModel(
            request_id=req.request_id,  # type: ignore[arg-type]
            tenant_id=req.tenant_id,  # type: ignore[arg-type]
            agent_id=req.agent_id,  # type: ignore[arg-type]
            action="request_blocked",
            layer=layer,
            status="blocked",
            source=req.source,
            metadata_={"blocked_reason": enforcement.blocked_reason},
            regulation_mappings=regulation_mappings,
        )
        db.add(row)
        await db.flush()
