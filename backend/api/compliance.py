"""Evidence package generation and download."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db
from services.compliance_generator import ComplianceGeneratorService

router = APIRouter(prefix="/api/compliance", tags=["compliance"])


class PackageRequest(BaseModel):
    tenant_id: str
    time_range_start: datetime
    time_range_end: datetime
    regulations: list[str] = ["EU_AI_ACT", "NIST_AI_RMF", "COLORADO_SB205", "HIPAA"]


@router.post("/generate")
async def generate_package(body: PackageRequest, db: AsyncSession = Depends(get_db)):
    svc = ComplianceGeneratorService(db)
    package = await svc.generate(
        tenant_id=body.tenant_id,
        start=body.time_range_start,
        end=body.time_range_end,
        regulations=body.regulations,
    )
    return package


@router.get("/{package_id}/pdf")
async def download_pdf(package_id: str, db: AsyncSession = Depends(get_db)):
    svc = ComplianceGeneratorService(db)
    pdf_bytes = await svc.get_pdf(package_id)
    if not pdf_bytes:
        raise HTTPException(status_code=404, detail="Package not found or PDF not generated")
    return Response(content=pdf_bytes, media_type="application/pdf", headers={
        "Content-Disposition": f"attachment; filename=compliance-{package_id}.pdf"
    })
