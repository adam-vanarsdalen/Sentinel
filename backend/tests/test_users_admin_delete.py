from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models import Tenant, User


def _mk_tenant(db: Session, tenant_id: str, name: str) -> Tenant:
    t = Tenant(id=tenant_id, name=name, slug=name.lower().replace(" ", "-"), status="active")
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


def test_tenant_admin_can_delete_user_and_audited(client: TestClient, db_session: Session):
    t1 = _mk_tenant(db_session, "t1", "Demo Firm")
    _mk_user(db_session, "admin", t1.id, "admin@example.com", "pw12345!", "tenant_admin")
    victim = _mk_user(db_session, "u2", t1.id, "user2@example.com", "pw12345!", "viewer")
    jwt_admin = _login(client, "admin@example.com", "pw12345!")

    r = client.delete(f"/admin/users/{victim.id}", headers={"Authorization": f"Bearer {jwt_admin}"})
    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is False

    r2 = client.get(
        "/admin/audit-events/search?action_type=USER_DEACTIVATE",
        headers={"Authorization": f"Bearer {jwt_admin}"},
    )
    assert r2.status_code == 200, r2.text
    items = r2.json()["items"]
    match = next((i for i in items if i.get("event_data", {}).get("target_user_id") == victim.id), None)
    assert match is not None
    assert match.get("user_email") == "admin@example.com"


def test_cannot_delete_last_active_tenant_admin(client: TestClient, db_session: Session):
    t1 = _mk_tenant(db_session, "t1", "Demo Firm")
    admin = _mk_user(db_session, "admin", t1.id, "admin@example.com", "pw12345!", "tenant_admin")
    _mk_user(db_session, "sa", None, "platform-admin@example.com", "pw12345!", "super_admin")
    jwt_sa = _login(client, "platform-admin@example.com", "pw12345!")

    r = client.delete(
        f"/admin/users/{admin.id}",
        headers={"Authorization": f"Bearer {jwt_sa}", "X-Tenant-Id": t1.id},
    )
    assert r.status_code == 409, r.text


def test_super_admin_users_requires_tenant_context(client: TestClient, db_session: Session):
    t1 = _mk_tenant(db_session, "t1", "Firm 1")
    _mk_user(db_session, "sa", None, "platform-admin@example.com", "pw12345!", "super_admin")
    _mk_user(db_session, "u1", t1.id, "user1@example.com", "pw12345!", "viewer")
    jwt_sa = _login(client, "platform-admin@example.com", "pw12345!")

    r = client.get("/admin/users", headers={"Authorization": f"Bearer {jwt_sa}"})
    assert r.status_code == 400, r.text

    r2 = client.get("/admin/users", headers={"Authorization": f"Bearer {jwt_sa}", "X-Tenant-Id": t1.id})
    assert r2.status_code == 200, r2.text
