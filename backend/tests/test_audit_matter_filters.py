from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_api_key_token, hash_password
from app.db.models import Tenant, TenantPolicy, User
from app.services.policy import DEFAULT_POLICY


def _mk_tenant(db: Session, tenant_id: str, name: str) -> Tenant:
    t = Tenant(id=tenant_id, name=name, slug=name.lower().replace(" ", "-"), status="active")
    db.add(t)
    db.commit()
    return t


def _mk_user(db: Session, user_id: str, tenant_id: str, email: str, password: str, role: str) -> User:
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


def test_audit_search_filters_by_matter_id_and_practice_group(client: TestClient, db_session: Session):
    t1 = _mk_tenant(db_session, "t1", "Firm 1")
    _mk_user(db_session, "u1", t1.id, "admin@firm1.com", "pw12345!", "tenant_admin")
    db_session.add(TenantPolicy(tenant_id=t1.id, policy_json=DEFAULT_POLICY))
    db_session.commit()

    token, api_key = create_api_key_token(tenant_id=t1.id, name="app")
    db_session.add(api_key)
    db_session.commit()

    for mid, pg in [("MAT-2026-0001", "Corporate"), ("MAT-2026-0142", "Litigation"), ("OTHER-99", "Corporate")]:
        r = client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {token}"},
            json={"model": "mock", "messages": [{"role": "user", "content": "hello"}], "max_tokens": 5, "metadata": {"matter_id": mid, "practice_group": pg}},
        )
        assert r.status_code == 200, r.text

    jwt = _login(client, "admin@firm1.com", "pw12345!")
    r2 = client.get(
        "/admin/audit-events/search",
        headers={"Authorization": f"Bearer {jwt}"},
        params={"matter_id": "MAT-2026-0142", "limit": 50, "offset": 0},
    )
    assert r2.status_code == 200, r2.text
    items = r2.json()["items"]
    assert len(items) == 1
    assert items[0]["matter_id"] == "MAT-2026-0142"

    r3 = client.get(
        "/admin/audit-events/search",
        headers={"Authorization": f"Bearer {jwt}"},
        params={"matter_query": "MAT-2026", "practice_group": "Corporate", "limit": 50, "offset": 0},
    )
    assert r3.status_code == 200, r3.text
    mids = {i.get("matter_id") for i in r3.json()["items"]}
    assert mids == {"MAT-2026-0001"}


def test_tenant_isolation_for_matter_filters(client: TestClient, db_session: Session):
    t1 = _mk_tenant(db_session, "ta", "Firm A")
    t2 = _mk_tenant(db_session, "tb", "Firm B")
    _mk_user(db_session, "ua", t1.id, "a@firm.com", "pwA12345!", "tenant_admin")
    _mk_user(db_session, "ub", t2.id, "b@firm.com", "pwB12345!", "tenant_admin")
    db_session.add_all([TenantPolicy(tenant_id=t1.id, policy_json=DEFAULT_POLICY), TenantPolicy(tenant_id=t2.id, policy_json=DEFAULT_POLICY)])
    db_session.commit()

    tok1, api_key1 = create_api_key_token(tenant_id=t1.id, name="app-a")
    db_session.add(api_key1)
    db_session.commit()
    r = client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {tok1}"},
        json={"model": "mock", "messages": [{"role": "user", "content": "hello"}], "max_tokens": 5, "metadata": {"matter_id": "MAT-SECRET-1", "practice_group": "Corporate"}},
    )
    assert r.status_code == 200, r.text

    jwt_b = _login(client, "b@firm.com", "pwB12345!")
    r2 = client.get(
        "/admin/audit-events/search",
        headers={"Authorization": f"Bearer {jwt_b}"},
        params={"matter_id": "MAT-SECRET-1", "limit": 10, "offset": 0},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["items"] == []
