from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models import AuditEvent, Tenant, TenantSettings, User
from app.services.alerts import default_settings_json, maybe_send_alerts_for_event


def _mk_tenant(db: Session, tenant_id: str, name: str) -> Tenant:
    tenant = Tenant(id=tenant_id, name=name, slug=name.lower().replace(" ", "-"), status="active")
    db.add(tenant)
    db.commit()
    return tenant


def _mk_user(db: Session, user_id: str, tenant_id: str | None, email: str, password: str, role: str) -> User:
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


def _configure_smtp(monkeypatch) -> None:
    from app.services import alerts as alerts_service

    monkeypatch.setattr(alerts_service.settings, "smtp_host", "smtp.test")
    monkeypatch.setattr(alerts_service.settings, "smtp_port", 2525)
    monkeypatch.setattr(alerts_service.settings, "smtp_user", None)
    monkeypatch.setattr(alerts_service.settings, "smtp_password", None)


def test_high_confidentiality_event_triggers_email_alert_and_audits(db_session: Session, monkeypatch):
    import aiosmtplib

    delivered: list[dict[str, str]] = []

    async def fake_send(msg, **kwargs):
        delivered.append(
            {
                "to": msg["To"],
                "subject": msg["Subject"],
                "body": msg.get_content(),
                "host": kwargs["hostname"],
            }
        )

    monkeypatch.setattr(aiosmtplib, "send", fake_send)
    _configure_smtp(monkeypatch)

    tenant = _mk_tenant(db_session, "tenant-alert-high", "Tenant Alert High")
    settings_json = default_settings_json()
    settings_json["alerts"]["email_recipients"] = ["alerts@example.com"]
    db_session.add(TenantSettings(tenant_id=tenant.id, settings_json=settings_json))
    db_session.commit()

    event = AuditEvent(
        tenant_id=tenant.id,
        request_id="req-high",
        action_type="LLM_REQUEST",
        outcome="success",
        provider="openai",
        model="gpt-4.1",
        phi_score=96,
        severity="low",
        risk_flags=[],
    )
    db_session.add(event)
    db_session.commit()

    results = maybe_send_alerts_for_event(db_session, event)

    assert len(results) == 1
    assert results[0]["status"] == "sent"
    assert delivered[0]["to"] == "alerts@example.com"
    assert "High confidentiality exposure detected" in delivered[0]["subject"]
    assert "Request ID: req-high" in delivered[0]["body"]
    assert delivered[0]["host"] == "smtp.test"

    audit = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.tenant_id == tenant.id, AuditEvent.action_type == "ALERT_SENT")
        .order_by(AuditEvent.timestamp.desc())
        .first()
    )
    assert audit is not None
    assert (audit.event_data or {}).get("trigger_type") == "high_confidentiality_exposure"


def test_prompt_injection_alerts_are_throttled(db_session: Session, monkeypatch):
    import aiosmtplib

    deliveries: list[str] = []

    async def fake_send(msg, **kwargs):
        deliveries.append(msg["Subject"])

    monkeypatch.setattr(aiosmtplib, "send", fake_send)
    _configure_smtp(monkeypatch)

    tenant = _mk_tenant(db_session, "tenant-alert-throttle", "Tenant Alert Throttle")
    settings_json = default_settings_json()
    settings_json["alerts"]["email_recipients"] = ["alerts@example.com"]
    settings_json["alerts"]["phi_threshold"] = 99
    settings_json["alerts"]["throttle_window_minutes"] = 60
    db_session.add(TenantSettings(tenant_id=tenant.id, settings_json=settings_json))
    db_session.commit()

    for idx in range(2):
        event = AuditEvent(
            tenant_id=tenant.id,
            request_id=f"req-prompt-{idx}",
            action_type="LLM_REQUEST",
            outcome="success",
            provider="openai",
            model="gpt-4.1",
            severity="high",
            risk_flags=["PROMPT_INJECTION_SUSPECTED"],
        )
        db_session.add(event)
        db_session.commit()
        maybe_send_alerts_for_event(db_session, event)

    assert len(deliveries) == 1
    sent_events = db_session.query(AuditEvent).filter(AuditEvent.tenant_id == tenant.id, AuditEvent.action_type == "ALERT_SENT").all()
    assert len(sent_events) == 1
    assert (sent_events[0].event_data or {}).get("trigger_type") == "prompt_injection_detected"


def test_repeated_provider_failures_alert_on_threshold(db_session: Session, monkeypatch):
    import aiosmtplib

    deliveries: list[str] = []

    async def fake_send(msg, **kwargs):
        deliveries.append(msg["Subject"])

    monkeypatch.setattr(aiosmtplib, "send", fake_send)
    _configure_smtp(monkeypatch)

    tenant = _mk_tenant(db_session, "tenant-alert-provider", "Tenant Alert Provider")
    settings_json = default_settings_json()
    settings_json["alerts"]["email_recipients"] = ["alerts@example.com"]
    settings_json["alerts"]["triggers"] = {
        "high_confidentiality_exposure": False,
        "prompt_injection_detected": False,
        "policy_blocked": False,
        "repeated_provider_failures": True,
        "blocked_request_spike": False,
    }
    settings_json["alerts"]["provider_failure_threshold"] = 3
    db_session.add(TenantSettings(tenant_id=tenant.id, settings_json=settings_json))
    db_session.commit()

    for idx in range(3):
        event = AuditEvent(
            tenant_id=tenant.id,
            request_id=f"req-provider-{idx}",
            action_type="LLM_REQUEST",
            outcome="fail",
            reason="Provider timeout",
            provider="openai",
            model="gpt-4.1",
            severity="med",
        )
        db_session.add(event)
        db_session.commit()
        maybe_send_alerts_for_event(db_session, event)

    assert len(deliveries) == 1
    sent = db_session.query(AuditEvent).filter(AuditEvent.tenant_id == tenant.id, AuditEvent.action_type == "ALERT_SENT").one()
    assert (sent.event_data or {}).get("trigger_type") == "repeated_provider_failures"


def test_alert_test_endpoint_and_history_are_tenant_scoped(client: TestClient, db_session: Session, monkeypatch):
    import aiosmtplib

    delivered_to: list[str] = []

    async def fake_send(msg, **kwargs):
        delivered_to.append(msg["To"])

    monkeypatch.setattr(aiosmtplib, "send", fake_send)
    _configure_smtp(monkeypatch)

    tenant_a = _mk_tenant(db_session, "tenant-alert-a", "Tenant Alert A")
    tenant_b = _mk_tenant(db_session, "tenant-alert-b", "Tenant Alert B")
    _mk_user(db_session, "user-alert-a", tenant_a.id, "admin-a@example.com", "pw12345!", "tenant_admin")
    _mk_user(db_session, "user-alert-b", tenant_b.id, "admin-b@example.com", "pw12345!", "tenant_admin")

    token_a = _login(client, "admin-a@example.com", "pw12345!")
    token_b = _login(client, "admin-b@example.com", "pw12345!")

    update_response = client.put(
        "/admin/alerts/current",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "email_recipients": ["security-a@example.com"],
            "severity_threshold": "med",
            "phi_threshold": 80,
            "triggers": {
                "high_confidentiality_exposure": True,
                "prompt_injection_detected": True,
                "policy_blocked": True,
                "repeated_provider_failures": True,
                "blocked_request_spike": False,
            },
            "throttle_window_minutes": 15,
            "provider_failure_threshold": 3,
            "webhook_format": "generic",
        },
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["alerts"]["email_recipients"] == ["security-a@example.com"]

    test_response = client.post("/admin/alerts/test", headers={"Authorization": f"Bearer {token_a}"})
    assert test_response.status_code == 200, test_response.text
    body = test_response.json()
    assert body["ok"] is True
    assert body["results"][0]["status"] == "sent"
    assert delivered_to == ["security-a@example.com"]

    history_a = client.get("/admin/alerts/history", headers={"Authorization": f"Bearer {token_a}"})
    assert history_a.status_code == 200, history_a.text
    assert any(item["trigger_type"] == "test_alert" for item in history_a.json())

    history_b = client.get("/admin/alerts/history", headers={"Authorization": f"Bearer {token_b}"})
    assert history_b.status_code == 200, history_b.text
    assert history_b.json() == []


def test_non_admin_users_cannot_manage_alerts(client: TestClient, db_session: Session):
    tenant = _mk_tenant(db_session, "tenant-alert-viewer", "Tenant Alert Viewer")
    _mk_user(db_session, "viewer-alert", tenant.id, "viewer-alert@example.com", "pw12345!", "viewer")
    token = _login(client, "viewer-alert@example.com", "pw12345!")

    response = client.get("/admin/alerts/current", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403, response.text

    response = client.post("/admin/alerts/test", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403, response.text
