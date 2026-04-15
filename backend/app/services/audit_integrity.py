from __future__ import annotations

import json
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import sha256_text
from app.db.models import AuditEvent


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _canonical_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat()


def _json_default(value: Any):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return _canonical_timestamp(value)
    return str(value)


def canonical_event_payload(event: AuditEvent) -> str:
    payload = {
        "id": event.id,
        "tenant_id": event.tenant_id,
        "api_key_id": event.api_key_id,
        "user_id": event.user_id,
        "request_id": event.request_id,
        "timestamp": _canonical_timestamp(event.timestamp),
        "action_type": event.action_type,
        "outcome": event.outcome,
        "reason": event.reason,
        "provider": event.provider,
        "model": event.model,
        "prompt_hash": event.prompt_hash,
        "response_hash": event.response_hash,
        "matter_id": event.matter_id,
        "practice_group": event.practice_group,
        "client_name": event.client_name,
        "phi_score": event.phi_score,
        "risk_flags": event.risk_flags or [],
        "severity": event.severity,
        "tokens_prompt": event.tokens_prompt,
        "tokens_completion": event.tokens_completion,
        "cost_usd": str(event.cost_usd) if event.cost_usd is not None else None,
        "event_data": event.event_data or {},
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=_json_default)


def compute_event_hash(event: AuditEvent, previous_event_hash: str | None) -> str:
    return sha256_text(f"{previous_event_hash or ''}{canonical_event_payload(event)}")


def _last_event_for_tenant(session: Session, tenant_id: str, *, before: datetime | None = None) -> AuditEvent | None:
    q = session.query(AuditEvent).filter(AuditEvent.tenant_id == tenant_id)
    if before is not None:
        q = q.filter(AuditEvent.timestamp < before)
    return q.order_by(AuditEvent.timestamp.desc(), AuditEvent.id.desc()).first()


def assign_hash_chain_for_new_events(session: Session, events: list[AuditEvent]) -> None:
    by_tenant: dict[str, list[AuditEvent]] = defaultdict(list)
    for event in events:
        if not event.tenant_id:
            raise ValueError("AuditEvent tenant_id is required")
        if not event.id:
            event.id = str(uuid.uuid4())
        if not event.timestamp:
            event.timestamp = _utcnow()
        by_tenant[event.tenant_id].append(event)

    with session.no_autoflush:
        for tenant_id, tenant_events in by_tenant.items():
            tenant_events.sort(key=lambda item: (item.timestamp, item.id))
            previous = _last_event_for_tenant(session, tenant_id)
            previous_hash = previous.event_hash if previous else None
            for event in tenant_events:
                event.previous_event_hash = previous_hash
                event.event_hash = compute_event_hash(event, previous_hash)
                previous_hash = event.event_hash


def assert_append_only(session: Session) -> None:
    for obj in session.deleted:
        if isinstance(obj, AuditEvent):
            raise ValueError("AuditEvent is append-only and cannot be deleted")

    for obj in session.dirty:
        if not isinstance(obj, AuditEvent):
            continue
        state = getattr(obj, "_sa_instance_state", None)
        if state is None or not state.persistent:
            continue
        if session.is_modified(obj, include_collections=False):
            raise ValueError("AuditEvent is append-only and cannot be updated")


def verify_audit_chain(
    db: Session,
    *,
    tenant_id: str,
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict[str, Any]:
    q = db.query(AuditEvent).filter(AuditEvent.tenant_id == tenant_id)
    if start:
        q = q.filter(AuditEvent.timestamp >= start)
    if end:
        q = q.filter(AuditEvent.timestamp <= end)
    rows = q.order_by(AuditEvent.timestamp.asc(), AuditEvent.id.asc()).all()

    previous_hash: str | None = None
    if start is not None:
        predecessor = _last_event_for_tenant(db, tenant_id, before=start)
        previous_hash = predecessor.event_hash if predecessor else None

    first_broken_event_id: str | None = None
    for row in rows:
        if row.previous_event_hash != previous_hash:
            first_broken_event_id = row.id
            break
        if not row.event_hash:
            first_broken_event_id = row.id
            break
        expected_hash = compute_event_hash(row, row.previous_event_hash)
        if row.event_hash != expected_hash:
            first_broken_event_id = row.id
            break
        previous_hash = row.event_hash

    return {
        "total_events_checked": len(rows),
        "chain_valid": first_broken_event_id is None,
        "first_broken_event_id": first_broken_event_id,
    }


def resolve_integrity_tenant_id(
    *,
    user_tenant_id: str | None,
    user_role: str,
    query_tenant_id: str | None,
) -> str:
    tenant_id = (query_tenant_id or "").strip() or None
    if user_role == "super_admin":
        effective = tenant_id or user_tenant_id
        if not effective:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")
        return effective
    if not user_tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")
    if tenant_id and tenant_id != user_tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant verification not permitted")
    return user_tenant_id
