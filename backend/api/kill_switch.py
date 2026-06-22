"""Manual kill switch API endpoint."""
from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db, get_redis
from services.kill_switch import KillSwitchService

router = APIRouter(prefix="/api/kill_switch", tags=["kill_switch"])


class FireRequest(BaseModel):
    agent_id: str
    operator_id: str
    reason: str
    tenant_id: str = "default"


class ResumeRequest(BaseModel):
    agent_id: str
    operator_id: str
    reason: str
    tenant_id: str = "default"


@router.post("/fire")
async def fire_kill_switch(
    body: FireRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    svc = KillSwitchService(redis, db)
    try:
        await svc.fire_manual(body.agent_id, body.operator_id, body.reason, body.tenant_id)
        await db.commit()
        return {"status": "terminated", "agent_id": body.agent_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/resume")
async def resume_agent(
    body: ResumeRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    svc = KillSwitchService(redis, db)
    try:
        await svc.resume(body.agent_id, body.operator_id, body.reason, body.tenant_id)
        await db.commit()
        return {"status": "active", "agent_id": body.agent_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/state/{agent_id}")
async def get_agent_state(agent_id: str, redis: Redis = Depends(get_redis)):
    svc = KillSwitchService(redis, None)  # type: ignore[arg-type]
    state = await svc.get_agent_state(agent_id)
    return {"agent_id": agent_id, "state": state}
