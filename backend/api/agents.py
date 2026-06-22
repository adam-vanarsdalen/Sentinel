"""Agent identity management."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db
from models.agent import Agent

router = APIRouter(prefix="/api/agents", tags=["agents"])


class AgentCreate(BaseModel):
    tenant_id: str
    name: str
    purpose_binding: str | None = None
    config: dict[str, Any] = {}


class AgentResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    purpose_binding: str | None
    state: str
    config: dict[str, Any]

    class Config:
        from_attributes = True


@router.post("/", response_model=AgentResponse)
async def create_agent(body: AgentCreate, db: AsyncSession = Depends(get_db)):
    agent = Agent(
        tenant_id=uuid.UUID(body.tenant_id),
        name=body.name,
        purpose_binding=body.purpose_binding,
        config=body.config,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return AgentResponse(
        id=str(agent.id),
        tenant_id=str(agent.tenant_id),
        name=agent.name,
        purpose_binding=agent.purpose_binding,
        state=agent.state,
        config=agent.config,
    )


@router.get("/", response_model=list[AgentResponse])
async def list_agents(tenant_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.tenant_id == uuid.UUID(tenant_id)))
    agents = result.scalars().all()
    return [
        AgentResponse(
            id=str(a.id),
            tenant_id=str(a.tenant_id),
            name=a.name,
            purpose_binding=a.purpose_binding,
            state=a.state,
            config=a.config,
        )
        for a in agents
    ]


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.id == uuid.UUID(agent_id)))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentResponse(
        id=str(agent.id),
        tenant_id=str(agent.tenant_id),
        name=agent.name,
        purpose_binding=agent.purpose_binding,
        state=agent.state,
        config=agent.config,
    )
