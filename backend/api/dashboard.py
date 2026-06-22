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
from models.request_log import RequestLog

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/metrics")
async def get_metrics(tenant_id: str, db: AsyncSession = Depends(get_db)):
    tid = uuid.UUID(tenant_id)
    since = datetime.now(timezone.utc) - timedelta(hours=24)

    total = await db.scalar(
        select(func.count()).select_from(RequestLog)
        .where(RequestLog.tenant_id == tid, RequestLog.created_at >= since)
    )
    blocked = await db.scalar(
        select(func.count()).select_from(RequestLog)
        .where(RequestLog.tenant_id == tid, RequestLog.status == "blocked", RequestLog.created_at >= since)
    )
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
