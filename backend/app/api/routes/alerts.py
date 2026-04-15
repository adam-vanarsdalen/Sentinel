from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import DbDep, require_role
from app.db.models import User
from app.services.alerts import (
    alert_history,
    ensure_tenant_settings_row,
    send_test_alert,
    serialize_alert_settings,
    update_alert_settings,
)
from app.services.audit_log import write_admin_audit_event

router = APIRouter()

AlertAdmin = Annotated[User, Depends(require_role("org_admin", "compliance_admin"))]


class AlertTriggerSettings(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    high_confidentiality_exposure: bool = True
    prompt_injection_detected: bool = True
    policy_blocked: bool = True
    repeated_provider_failures: bool = True
    blocked_request_spike: bool = False


class AlertSettingsBody(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    phi_threshold: int = Field(default=80, ge=0, le=100)
    severity_threshold: str = Field(default="med")
    email_recipients: list[str] = Field(default_factory=list)
    webhook_url: str | None = None
    clear_webhook: bool = False
    webhook_format: str = Field(default="generic")
    triggers: AlertTriggerSettings = Field(default_factory=AlertTriggerSettings)
    throttle_window_minutes: int = Field(default=30, ge=1, le=1440)
    provider_failure_threshold: int = Field(default=3, ge=2, le=20)


class AlertSettingsResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    tenant_id: str
    alerts: dict
    updated_at: str
    updated_by_user_id: str | None


class AlertHistoryItem(BaseModel):
    id: str
    timestamp: str
    status: str
    trigger_type: str | None = None
    severity: str | None = None
    channel: str | None = None
    destination: str | None = None
    request_id: str | None = None
    reason: str | None = None


class AlertTestResponse(BaseModel):
    ok: bool
    results: list[dict]


def _tenant_id_for(user: User) -> str:
    tenant_id = user.effective_tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")
    return tenant_id


def _serialize_response(row) -> AlertSettingsResponse:
    payload = serialize_alert_settings(row.tenant_id, row.settings_json)
    payload["updated_at"] = row.updated_at.isoformat()
    payload["updated_by_user_id"] = row.updated_by_user_id
    return AlertSettingsResponse.model_validate(payload)


@router.get("/current", response_model=AlertSettingsResponse)
def get_current_alert_settings(db: DbDep, user: AlertAdmin) -> AlertSettingsResponse:
    tenant_id = _tenant_id_for(user)
    row = ensure_tenant_settings_row(db, tenant_id)
    return _serialize_response(row)


@router.put("/current", response_model=AlertSettingsResponse)
def put_current_alert_settings(req: AlertSettingsBody, db: DbDep, user: AlertAdmin) -> AlertSettingsResponse:
    tenant_id = _tenant_id_for(user)
    row = update_alert_settings(db, tenant_id=tenant_id, user_id=user.id, payload=req.model_dump())
    write_admin_audit_event(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        action_type="ALERT_SETTINGS_UPDATED",
        outcome="success",
        reason="Alert settings updated",
        event_data=serialize_alert_settings(tenant_id, row.settings_json)["alerts"],
    )
    return _serialize_response(row)


@router.get("/history", response_model=list[AlertHistoryItem])
def get_alert_history(
    db: DbDep,
    user: AlertAdmin,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[AlertHistoryItem]:
    tenant_id = _tenant_id_for(user)
    return [AlertHistoryItem.model_validate(item) for item in alert_history(db, tenant_id=tenant_id, limit=limit)]


@router.post("/test", response_model=AlertTestResponse)
def post_test_alert(db: DbDep, user: AlertAdmin) -> AlertTestResponse:
    tenant_id = _tenant_id_for(user)
    result = send_test_alert(db, tenant_id=tenant_id)
    return AlertTestResponse.model_validate(result)
