"""Alert feed — REST query."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db
from models.alert import Alert

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("/")
async def list_alerts(tenant_id: str, limit: int = 50, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Alert)
        .where(Alert.tenant_id == uuid.UUID(tenant_id))
        .order_by(desc(Alert.created_at))
        .limit(limit)
    )
    alerts = result.scalars().all()
    return [
        {
            "id": str(a.id),
            "alert_type": a.alert_type,
            "severity": a.severity,
            "message": a.message,
            "agent_id": str(a.agent_id) if a.agent_id else None,
            "created_at": a.created_at.isoformat(),
        }
        for a in alerts
    ]
