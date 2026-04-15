from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from fastapi import Depends
from pydantic import BaseModel

from app.api.deps import DbDep, require_role
from app.core.security import create_api_key_token
from sqlalchemy import func

from app.db.models import ApiKey, AuditEvent, User
from app.services.audit_log import write_admin_audit_event

router = APIRouter()


class ApiKeyCreateRequest(BaseModel):
    name: str


class ApiKeyListItem(BaseModel):
    id: str
    name: str
    key_prefix: str
    is_active: bool
    created_at: str
    revoked_at: str | None
    last_used_at: str | None = None


class ApiKeyCreateResponse(BaseModel):
    api_key: ApiKeyListItem
    token: str


AdminReader = Annotated[User, Depends(require_role("super_admin", "org_admin", "compliance_admin", "operator", "reviewer", "auditor"))]
AdminWriter = Annotated[User, Depends(require_role("super_admin", "org_admin", "operator"))]
AdminOwner = Annotated[User, Depends(require_role("super_admin", "org_admin"))]


@router.get("", response_model=list[ApiKeyListItem])
def list_keys(db: DbDep, user: AdminReader) -> list[ApiKeyListItem]:
    tenant_id = user.effective_tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")
    # Add last_used_at derived from audit events (pilot).
    last_used = (
        db.query(AuditEvent.api_key_id, func.max(AuditEvent.timestamp).label("last_used_at"))
        .filter(AuditEvent.tenant_id == tenant_id, AuditEvent.api_key_id.isnot(None), AuditEvent.action_type == "LLM_REQUEST")
        .group_by(AuditEvent.api_key_id)
        .subquery()
    )
    rows = (
        db.query(ApiKey, last_used.c.last_used_at)
        .outerjoin(last_used, last_used.c.api_key_id == ApiKey.id)
        .filter(ApiKey.tenant_id == tenant_id)
        .order_by(ApiKey.created_at.desc())
        .all()
    )
    items = []
    for k, last_used_at in rows:
        d = k.to_list_item()
        d["last_used_at"] = last_used_at.isoformat() if last_used_at else None
        items.append(d)
    return items


@router.post("", response_model=ApiKeyCreateResponse)
def create_key(req: ApiKeyCreateRequest, db: DbDep, user: AdminWriter) -> ApiKeyCreateResponse:
    tenant_id = user.effective_tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")
    token, api_key = create_api_key_token(tenant_id=tenant_id, name=req.name)
    db.add(api_key)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(api_key)
    write_admin_audit_event(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        action_type="ADMIN_CHANGE",
        outcome="success",
        reason="API key created",
        event_data={"api_key_id": api_key.id, "name": api_key.name},
    )
    return ApiKeyCreateResponse(api_key=api_key.to_list_item(), token=token)


@router.post("/{api_key_id}/revoke", response_model=ApiKeyListItem)
def revoke_key(api_key_id: str, db: DbDep, user: AdminOwner) -> ApiKeyListItem:
    tenant_id = user.effective_tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")

    api_key = db.query(ApiKey).filter(ApiKey.id == api_key_id, ApiKey.tenant_id == tenant_id).one_or_none()
    if not api_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    api_key.revoke()
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    write_admin_audit_event(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        action_type="ADMIN_CHANGE",
        outcome="success",
        reason="API key revoked",
        event_data={"api_key_id": api_key.id, "name": api_key.name},
    )
    return api_key.to_list_item()
