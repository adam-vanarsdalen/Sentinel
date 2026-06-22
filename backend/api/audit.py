"""Audit log query and export."""
from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db
from models.audit_entry import AuditEntry

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/")
async def query_audit_log(
    tenant_id: str,
    limit: int = 50,
    status: str | None = None,
    agent_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(AuditEntry).where(AuditEntry.tenant_id == uuid.UUID(tenant_id))
    if status:
        q = q.where(AuditEntry.status == status)
    if agent_id:
        q = q.where(AuditEntry.agent_id == uuid.UUID(agent_id))
    q = q.order_by(desc(AuditEntry.created_at)).limit(limit)
    result = await db.execute(q)
    entries = result.scalars().all()
    return [
        {
            "id": e.id,
            "request_id": str(e.request_id),
            "action": e.action,
            "layer": e.layer,
            "status": e.status,
            "model": e.model,
            "regulation_mappings": e.regulation_mappings,
            "created_at": e.created_at.isoformat(),
        }
        for e in entries
    ]


@router.get("/export/csv")
async def export_audit_csv(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AuditEntry)
        .where(AuditEntry.tenant_id == uuid.UUID(tenant_id))
        .order_by(desc(AuditEntry.created_at))
        .limit(10000)
    )
    entries = result.scalars().all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "request_id", "action", "layer", "status", "model", "created_at"])
    for e in entries:
        writer.writerow([e.id, str(e.request_id), e.action, e.layer, e.status, e.model, e.created_at])
    buf.seek(0)
    return StreamingResponse(buf, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=audit.csv"})
