from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import DbDep, require_role
from app.db.models import Tenant, User

router = APIRouter()

SuperAdmin = Annotated[User, Depends(require_role("super_admin"))]
AnyAuthedUser = Annotated[User, Depends(require_role("super_admin", "org_admin", "compliance_admin", "operator", "reviewer", "auditor"))]


@router.get("", response_model=list[dict])
def list_tenants(db: DbDep, user: SuperAdmin) -> list[dict]:
    rows = db.query(Tenant).order_by(Tenant.created_at.desc()).limit(200).all()
    return [t.to_platform_dict() for t in rows]


@router.get("/me", response_model=dict)
def get_my_tenant(db: DbDep, user: AnyAuthedUser) -> dict:
    tenant_id = user.effective_tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")
    t = db.get(Tenant, tenant_id)
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return t.to_platform_dict()
