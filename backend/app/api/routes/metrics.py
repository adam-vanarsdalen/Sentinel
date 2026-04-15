from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import DbDep, require_role
from app.db.models import User
from app.services.metrics_service import compute_cost_summary, compute_overview, compute_risk_summary

router = APIRouter()

MetricsReader = Annotated[User, Depends(require_role("super_admin", "org_admin", "compliance_admin", "operator", "reviewer", "auditor"))]


@router.get("/overview", response_model=dict)
def overview(
    db: DbDep,
    user: MetricsReader,
    range: str = "7d",
) -> dict:
    tenant_id = user.effective_tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")
    return compute_overview(db=db, tenant_id=tenant_id, range=range)


@router.get("/risk-summary", response_model=dict)
def risk_summary(
    db: DbDep,
    user: MetricsReader,
    range: str = "7d",
) -> dict:
    tenant_id = user.effective_tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")
    return compute_risk_summary(db=db, tenant_id=tenant_id, range=range)


@router.get("/cost-summary", response_model=dict)
def cost_summary(
    db: DbDep,
    user: MetricsReader,
) -> dict:
    tenant_id = user.effective_tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")
    return compute_cost_summary(db=db, tenant_id=tenant_id)
