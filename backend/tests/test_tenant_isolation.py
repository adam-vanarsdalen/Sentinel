from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_api_key_token, hash_password
from app.db.models import ApiKey, Tenant, User


def _mk_tenant(db: Session, tenant_id: str, name: str) -> Tenant:
    t = Tenant(id=tenant_id, name=name, slug=name.lower().replace(" ", "-"), status="active")
    db.add(t)
    db.commit()
    return t


def _mk_user(db: Session, user_id: str, tenant_id: str, email: str, password: str, role: str) -> User:
    u = User(id=user_id, tenant_id=tenant_id, email=email.lower(), password_hash=hash_password(password), role=role, is_active=True)
    db.add(u)
    db.commit()
    return u


def _login(client: TestClient, email: str, password: str) -> str:
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_tenant_isolation_api_keys_list(client: TestClient, db_session: Session):
    t1 = _mk_tenant(db_session, "ta", "Tenant A")
    t2 = _mk_tenant(db_session, "tb", "Tenant B")

    _mk_user(db_session, "ua", t1.id, "a@example.com", "pwA12345!", "tenant_admin")
    _mk_user(db_session, "ub", t2.id, "b@example.com", "pwB12345!", "tenant_admin")

    tok1, k1 = create_api_key_token(tenant_id=t1.id, name="app-a")
    tok2, k2 = create_api_key_token(tenant_id=t2.id, name="app-b")
    db_session.add_all([k1, k2])
    db_session.commit()

    jwt_a = _login(client, "a@example.com", "pwA12345!")
    r = client.get("/admin/api-keys", headers={"Authorization": f"Bearer {jwt_a}"})
    assert r.status_code == 200, r.text
    items = r.json()
    assert len(items) == 1
    assert items[0]["name"] == "app-a"
