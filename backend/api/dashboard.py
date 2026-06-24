"""Aggregated metrics for the dashboard."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db
from models.alert import Alert
from models.audit_entry import AuditEntry
from models.compliance_package import CompliancePackage

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/metrics")
async def get_metrics(tenant_id: str, db: AsyncSession = Depends(get_db)):
    tid = uuid.UUID(tenant_id)
    since = datetime.now(timezone.utc) - timedelta(hours=24)

    # Count all processed requests (passed + blocked)
    passed = await db.scalar(
        select(func.count()).select_from(AuditEntry)
        .where(AuditEntry.tenant_id == tid, AuditEntry.action == "pipeline_complete",
               AuditEntry.created_at >= since)
    )
    blocked = await db.scalar(
        select(func.count()).select_from(AuditEntry)
        .where(AuditEntry.tenant_id == tid, AuditEntry.action == "request_blocked",
               AuditEntry.created_at >= since)
    )
    total = (passed or 0) + (blocked or 0)
    anomalies = await db.scalar(
        select(func.count()).select_from(Alert)
        .where(Alert.tenant_id == tid, Alert.alert_type == "anomaly", Alert.created_at >= since)
    )
    packages = await db.scalar(
        select(func.count()).select_from(CompliancePackage)
        .where(CompliancePackage.tenant_id == tid)
    )

    return {
        "total_requests": total or 0,
        "blocked_requests": blocked or 0,
        "anomalies_flagged": anomalies or 0,
        "compliance_packages": packages or 0,
        "period_hours": 24,
    }


@router.get("/recent-rps")
async def get_recent_rps(tenant_id: str, db: AsyncSession = Depends(get_db)):
    tid = uuid.UUID(tenant_id)
    since = datetime.now(timezone.utc) - timedelta(seconds=60)
    count = await db.scalar(
        select(func.count()).select_from(AuditEntry)
        .where(
            AuditEntry.tenant_id == tid,
            AuditEntry.action.in_(["pipeline_complete", "request_blocked"]),
            AuditEntry.created_at >= since,
        )
    )
    return {"rps": round((count or 0) / 60, 3)}
