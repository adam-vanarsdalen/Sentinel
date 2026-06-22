"""Main proxy endpoint — all AI requests enter through here."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db, get_redis
from schemas.proxy import PipelineError, PipelineResponse
from services.pipeline import process_request

router = APIRouter()


@router.post("/v1/chat/completions", response_model=PipelineResponse)
@router.post("/v1/messages", response_model=PipelineResponse)
async def proxy_request(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> PipelineResponse:
    body: dict[str, Any] = await request.json()
    body["_headers"] = dict(request.headers)

    tenant_id = request.headers.get("X-Tenant-ID", "default")
    source = "api"

    try:
        return await process_request(body, source=source, tenant_id=tenant_id, db=db, redis=redis)
    except PipelineError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal pipeline error: {e}")
