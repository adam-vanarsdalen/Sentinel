from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.request_context import get_request_id
from app.db.models import AuditEvent


def write_admin_audit_event(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    action_type: str,
    outcome: str,
    reason: str | None,
    event_data: dict | None = None,
) -> None:
    ev = AuditEvent(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        user_id=user_id,
        api_key_id=None,
        request_id=get_request_id(),
        action_type=action_type,
        outcome=outcome,
        reason=reason,
        event_data=event_data or {},
    )
    db.add(ev)
    db.commit()


def write_auth_audit_event(
    db: Session,
    *,
    tenant_id: str,
    user_id: str | None,
    action_type: str,
    outcome: str,
    reason: str | None,
    event_data: dict | None = None,
) -> None:
    ev = AuditEvent(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        user_id=user_id,
        api_key_id=None,
        request_id=get_request_id(),
        action_type=action_type,
        outcome=outcome,
        reason=reason,
        event_data=event_data or {},
    )
    db.add(ev)
    db.commit()


def write_system_audit_event(
    db: Session,
    *,
    tenant_id: str,
    api_key_id: str | None,
    action_type: str,
    outcome: str,
    reason: str | None,
    provider: str | None = None,
    model: str | None = None,
    event_data: dict | None = None,
) -> None:
    ev = AuditEvent(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        user_id=None,
        api_key_id=api_key_id,
        request_id=get_request_id(),
        action_type=action_type,
        outcome=outcome,
        reason=reason,
        provider=provider,
        model=model,
        event_data=event_data or {},
    )
    db.add(ev)
    db.commit()
