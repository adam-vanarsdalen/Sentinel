from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import DbDep, require_role
from app.db.models import TenantSettings, User
from app.services.alerts import default_settings_json

router = APIRouter()

SettingsReader = Annotated[User, Depends(require_role("super_admin", "org_admin", "compliance_admin", "operator", "reviewer", "auditor"))]
SettingsWriter = Annotated[User, Depends(require_role("super_admin", "org_admin", "compliance_admin"))]


class SettingsResponse(BaseModel):
    tenant_id: str
    settings_json: dict
    updated_at: str
    updated_by_user_id: str | None


class SettingsUpdateRequest(BaseModel):
    settings_json: dict


@router.get("/current", response_model=SettingsResponse)
def get_current(db: DbDep, user: SettingsReader) -> SettingsResponse:
    tenant_id = user.effective_tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")

    row = db.get(TenantSettings, tenant_id)
    if not row:
        row = TenantSettings(tenant_id=tenant_id, settings_json=default_settings_json())
        db.add(row)
        db.commit()
        db.refresh(row)
    return row.to_response()


@router.put("/current", response_model=SettingsResponse)
def update_current(req: SettingsUpdateRequest, db: DbDep, user: SettingsWriter) -> SettingsResponse:
    tenant_id = user.effective_tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")

    row = db.get(TenantSettings, tenant_id)
    incoming = dict(req.settings_json or {})
    if not row:
        stored = default_settings_json()
        stored.update(incoming)
        row = TenantSettings(tenant_id=tenant_id, settings_json=stored, updated_by_user_id=user.id)
    else:
        current = dict(row.settings_json or default_settings_json())
        if "alerts" not in incoming and "alerts" in current:
            incoming["alerts"] = current["alerts"]
        if "notification_email" not in incoming and "notification_email" in current:
            incoming["notification_email"] = current["notification_email"]
        current.update(incoming)
        row.settings_json = current
        row.updated_by_user_id = user.id
    db.add(row)
    db.commit()
    db.refresh(row)
    return row.to_response()
