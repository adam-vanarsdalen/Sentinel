"""Policy CRUD."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db
from models.policy import Policy

router = APIRouter(prefix="/api/policies", tags=["policies"])


class PolicyCreate(BaseModel):
    tenant_id: str
    name: str
    action_limit_session: int = 1000
    budget_hourly_usd: float | None = None
    budget_daily_usd: float | None = None
    budget_monthly_usd: float | None = None
    allowed_models: list[str] = []
    forbidden_endpoints: list[str] = []
    forbidden_data_classes: list[str] = []
    purpose_binding: str | None = None
    config: dict[str, Any] = {}


class PolicyResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    version: int
    action_limit_session: int
    allowed_models: list[str]
    forbidden_endpoints: list[str]
    forbidden_data_classes: list[str]
    is_active: bool


@router.post("/", response_model=PolicyResponse)
async def create_policy(body: PolicyCreate, db: AsyncSession = Depends(get_db)):
    config = dict(body.config)
    if body.purpose_binding:
        config["purpose_binding"] = body.purpose_binding
    policy = Policy(
        tenant_id=uuid.UUID(body.tenant_id),
        name=body.name,
        action_limit_session=body.action_limit_session,
        budget_hourly_usd=body.budget_hourly_usd,
        budget_daily_usd=body.budget_daily_usd,
        budget_monthly_usd=body.budget_monthly_usd,
        allowed_models=body.allowed_models,
        forbidden_endpoints=body.forbidden_endpoints,
        forbidden_data_classes=body.forbidden_data_classes,
        config=config,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return PolicyResponse(
        id=str(policy.id),
        tenant_id=str(policy.tenant_id),
        name=policy.name,
        version=policy.version,
        action_limit_session=policy.action_limit_session,
        allowed_models=policy.allowed_models or [],
        forbidden_endpoints=policy.forbidden_endpoints or [],
        forbidden_data_classes=policy.forbidden_data_classes or [],
        is_active=policy.is_active,
    )


@router.get("/")
async def list_policies(tenant_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Policy).where(Policy.tenant_id == uuid.UUID(tenant_id)))
    return [str(p.id) for p in result.scalars().all()]
