from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models import AuditEvent, Tenant, TenantPolicy, User
from app.services.policy_templates import get_policy_template


def _mk_tenant(db: Session, tenant_id: str, name: str, slug: str) -> Tenant:
    t = Tenant(id=tenant_id, name=name, slug=slug, status="active")
    db.add(t)
    db.commit()
    return t


def _mk_user(db: Session, user_id: str, tenant_id: str | None, email: str, password: str, role: str) -> User:
    u = User(
        id=user_id,
        tenant_id=tenant_id,
        email=email.lower(),
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    db.add(u)
    db.commit()
    return u


def _login(client: TestClient, email: str, password: str) -> str:
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_super_admin_can_create_tenant_and_slug_unique(client: TestClient, db_session: Session):
    _mk_tenant(db_session, "t0", "Existing", "existing")
    _mk_user(db_session, "sa", None, "platform-admin@example.com", "pw12345!", "super_admin")
    jwt = _login(client, "platform-admin@example.com", "pw12345!")

    r = client.post(
        "/platform/tenants",
        headers={"Authorization": f"Bearer {jwt}"},
        json={"name": "Anderson & Cole LLP", "slug": "anderson-cole", "status": "active"},
    )
    assert r.status_code == 201, r.text
    tenant_id = r.json()["tenant"]["id"]

    # New tenants start with the default preset policy template.
    policy = db_session.get(TenantPolicy, tenant_id)
    assert policy is not None
    tpl = get_policy_template("general_default_policy_v1")
    assert tpl is not None
    assert policy.policy_json.get("block_prompt_patterns") == tpl["policy_json"].get("block_prompt_patterns")

    r2 = client.post(
        "/platform/tenants",
        headers={"Authorization": f"Bearer {jwt}"},
        json={"name": "Another", "slug": "anderson-cole", "status": "active"},
    )
    assert r2.status_code == 409, r2.text

    # audit event written for create
    evs = db_session.query(AuditEvent).filter(AuditEvent.tenant_id == tenant_id, AuditEvent.action_type == "TENANT_CREATE").all()
    assert len(evs) == 1
    assert evs[0].outcome == "success"


def test_tenant_admin_cannot_access_platform_endpoints(client: TestClient, db_session: Session):
    t1 = _mk_tenant(db_session, "t1", "Tenant 1", "tenant-1")
    _mk_user(db_session, "u1", t1.id, "admin@example.com", "pw12345!", "tenant_admin")
    jwt = _login(client, "admin@example.com", "pw12345!")

    r = client.get("/platform/tenants", headers={"Authorization": f"Bearer {jwt}"})
    assert r.status_code == 403, r.text


def test_switch_tenant_writes_audit_event(client: TestClient, db_session: Session):
    t1 = _mk_tenant(db_session, "t1", "Tenant 1", "tenant-1")
    _mk_user(db_session, "sa", None, "platform-admin@example.com", "pw12345!", "super_admin")
    jwt = _login(client, "platform-admin@example.com", "pw12345!")

    r = client.post(f"/platform/tenants/{t1.id}/switch", headers={"Authorization": f"Bearer {jwt}"})
    assert r.status_code == 200, r.text
    assert r.json()["current_tenant"]["id"] == t1.id

    ev = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.tenant_id == t1.id, AuditEvent.action_type == "TENANT_SWITCH")
        .order_by(AuditEvent.timestamp.desc())
        .first()
    )
    assert ev is not None
    assert ev.outcome == "success"
