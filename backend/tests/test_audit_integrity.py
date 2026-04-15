from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models import AuditEvent, Tenant, User
from app.services.audit_integrity import compute_event_hash


def _mk_tenant(db: Session, tenant_id: str, name: str) -> Tenant:
    tenant = Tenant(id=tenant_id, name=name, slug=name.lower().replace(" ", "-"), status="active")
    db.add(tenant)
    db.commit()
    return tenant


def _mk_user(db: Session, user_id: str, tenant_id: str, email: str, password: str, role: str) -> User:
    user = User(
        id=user_id,
        tenant_id=tenant_id,
        email=email.lower(),
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_audit_events_receive_hash_chain_on_insert(db_session: Session):
    tenant = _mk_tenant(db_session, "t_chain", "Tenant Chain")

    first = AuditEvent(
        tenant_id=tenant.id,
        action_type="LLM_REQUEST",
        outcome="success",
        request_id="req-1",
        timestamp=datetime(2026, 4, 3, 12, 0, 0, tzinfo=timezone.utc),
        provider="mock",
        model="mock",
        cost_usd=Decimal("0.010000"),
        event_data={"metadata": {"matter_id": "MAT-1"}},
    )
    second = AuditEvent(
        tenant_id=tenant.id,
        action_type="POLICY_BLOCK",
        outcome="fail",
        request_id="req-2",
        timestamp=datetime(2026, 4, 3, 12, 1, 0, tzinfo=timezone.utc),
        provider="mock",
        model="mock",
        event_data={"metadata": {"matter_id": "MAT-2"}},
    )
    db_session.add_all([first, second])
    db_session.commit()

    rows = db_session.query(AuditEvent).filter(AuditEvent.tenant_id == tenant.id).order_by(AuditEvent.timestamp.asc(), AuditEvent.id.asc()).all()
    assert len(rows) == 2
    assert rows[0].previous_event_hash is None
    assert rows[0].event_hash == compute_event_hash(rows[0], None)
    assert rows[1].previous_event_hash == rows[0].event_hash
    assert rows[1].event_hash == compute_event_hash(rows[1], rows[0].event_hash)


def test_audit_integrity_verify_detects_tampering_and_logs_run(client: TestClient, db_session: Session):
    tenant = _mk_tenant(db_session, "t_verify", "Tenant Verify")
    _mk_user(db_session, "u_verify", tenant.id, "auditor@example.com", "pw12345!", "auditor")

    event = AuditEvent(
        tenant_id=tenant.id,
        user_id="u_verify",
        action_type="LLM_REQUEST",
        outcome="success",
        request_id="req-verify",
        provider="mock",
        model="mock",
        event_data={"metadata": {"matter_id": "MAT-VERIFY"}},
    )
    db_session.add(event)
    db_session.commit()

    db_session.execute(text("UPDATE audit_events SET outcome = 'tampered' WHERE id = :id"), {"id": event.id})
    db_session.commit()

    jwt = _login(client, "auditor@example.com", "pw12345!")
    response = client.get("/audit/integrity/verify", headers={"Authorization": f"Bearer {jwt}"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_events_checked"] == 1
    assert body["chain_valid"] is False
    assert body["first_broken_event_id"] == event.id

    verify_event = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.tenant_id == tenant.id, AuditEvent.action_type == "AUDIT_VERIFY_RUN")
        .order_by(AuditEvent.timestamp.desc(), AuditEvent.id.desc())
        .first()
    )
    assert verify_event is not None
    assert verify_event.outcome == "fail"


def test_audit_events_cannot_be_updated_or_deleted(db_session: Session):
    tenant = _mk_tenant(db_session, "t_append", "Tenant Append")
    event = AuditEvent(tenant_id=tenant.id, action_type="LLM_REQUEST", outcome="success", request_id="req-append")
    db_session.add(event)
    db_session.commit()

    event.reason = "mutated"
    with pytest.raises(ValueError, match="append-only"):
        db_session.commit()
    db_session.rollback()

    db_session.delete(event)
    with pytest.raises(ValueError, match="append-only"):
        db_session.commit()
    db_session.rollback()


def test_audit_exports_include_integrity_fields(client: TestClient, db_session: Session):
    tenant = _mk_tenant(db_session, "t_export", "Tenant Export")
    _mk_user(db_session, "u_export", tenant.id, "exporter@example.com", "pw12345!", "auditor")

    event = AuditEvent(
        tenant_id=tenant.id,
        user_id="u_export",
        action_type="LLM_REQUEST",
        outcome="success",
        request_id="req-export",
        provider="mock",
        model="mock",
    )
    db_session.add(event)
    db_session.commit()

    jwt = _login(client, "exporter@example.com", "pw12345!")

    json_response = client.get("/admin/audit-events/export.json", headers={"Authorization": f"Bearer {jwt}"})
    assert json_response.status_code == 200, json_response.text
    items = json_response.json()
    assert len(items) == 1
    assert items[0]["event_hash"] == event.event_hash
    assert "previous_event_hash" in items[0]

    csv_response = client.get("/admin/audit-events/export.csv", headers={"Authorization": f"Bearer {jwt}"})
    assert csv_response.status_code == 200, csv_response.text
    csv_text = csv_response.text
    assert "previous_event_hash,event_hash" in csv_text
    assert event.event_hash in csv_text
