from __future__ import annotations

import copy

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models import AuditEvent, Tenant, TenantPolicy, TenantPolicyVersion, User
from app.services.policy import DEFAULT_POLICY


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


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


def _policy_with_tokens(max_tokens: int) -> dict:
    policy = copy.deepcopy(DEFAULT_POLICY)
    policy["allowed_models"] = ["mock"]
    policy["max_tokens_per_request"] = max_tokens
    return policy


def test_policy_history_listing_includes_active_metadata(client: TestClient, db_session: Session):
    tenant = _mk_tenant(db_session, "t_policy_history", "Tenant Policy History")
    _mk_user(db_session, "u_policy_history", tenant.id, "admin@example.com", "pw12345!", "tenant_admin")
    token = _login(client, "admin@example.com", "pw12345!")

    current_response = client.get("/admin/policy/current", headers={"Authorization": f"Bearer {token}"})
    assert current_response.status_code == 200, current_response.text

    update_response = client.put(
        "/admin/policy/current",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "policy_json": _policy_with_tokens(1024),
            "change_note": "Raised request token limit for pilot users.",
        },
    )
    assert update_response.status_code == 200, update_response.text

    history_response = client.get("/admin/policy/history", headers={"Authorization": f"Bearer {token}"})
    assert history_response.status_code == 200, history_response.text
    body = history_response.json()
    assert len(body) >= 2
    assert any(row["active"] is True for row in body)
    latest = body[0]
    assert latest["change_note"] == "Raised request token limit for pilot users."
    assert latest["summary"] == "Raised request token limit for pilot users."
    assert latest["created_by_user_id"] == "u_policy_history"
    assert latest["created_by_email"] == "admin@example.com"
    assert latest["policy_json"]["max_tokens_per_request"] == 1024


def test_policy_rollback_creates_new_active_version(client: TestClient, db_session: Session):
    tenant = _mk_tenant(db_session, "t_policy_rollback", "Tenant Policy Rollback")
    _mk_user(db_session, "u_policy_rollback", tenant.id, "rollback-admin@example.com", "pw12345!", "tenant_admin")
    token = _login(client, "rollback-admin@example.com", "pw12345!")

    current_response = client.get("/admin/policy/current", headers={"Authorization": f"Bearer {token}"})
    assert current_response.status_code == 200, current_response.text
    initial_active_version_id = current_response.json()["active_version_id"]
    assert initial_active_version_id
    initial_policy_json = current_response.json()["policy_json"]

    update_response = client.put(
        "/admin/policy/current",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "policy_json": _policy_with_tokens(2048),
            "change_note": "Temporary expansion for a large matter intake.",
        },
    )
    assert update_response.status_code == 200, update_response.text
    updated_active_version_id = update_response.json()["active_version_id"]
    assert updated_active_version_id != initial_active_version_id

    rollback_response = client.post(
        f"/admin/policy/rollback/{initial_active_version_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rollback_response.status_code == 200, rollback_response.text
    rollback_body = rollback_response.json()
    assert rollback_body["active_version_id"] not in {None, initial_active_version_id, updated_active_version_id}
    assert rollback_body["policy_json"] == initial_policy_json

    active_version = db_session.get(TenantPolicyVersion, rollback_body["active_version_id"])
    assert active_version is not None
    assert active_version.source_version_id == initial_active_version_id
    assert active_version.policy_json == initial_policy_json

    actions = {
        event.action_type
        for event in db_session.query(AuditEvent).filter(AuditEvent.tenant_id == tenant.id).all()
    }
    assert "POLICY_VERSION_CREATED" in actions
    assert "POLICY_VERSION_ACTIVATED" in actions
    assert "POLICY_ROLLBACK" in actions


def test_policy_history_is_tenant_isolated(client: TestClient, db_session: Session):
    tenant_a = _mk_tenant(db_session, "t_policy_a", "Tenant Policy A")
    tenant_b = _mk_tenant(db_session, "t_policy_b", "Tenant Policy B")
    _mk_user(db_session, "u_policy_a", tenant_a.id, "a@example.com", "pw12345!", "tenant_admin")
    _mk_user(db_session, "u_policy_b", tenant_b.id, "b@example.com", "pw12345!", "tenant_admin")

    token_a = _login(client, "a@example.com", "pw12345!")
    token_b = _login(client, "b@example.com", "pw12345!")

    client.get("/admin/policy/current", headers={"Authorization": f"Bearer {token_a}"})
    client.put(
        "/admin/policy/current",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"policy_json": _policy_with_tokens(777), "change_note": "Tenant A only"},
    )
    client.get("/admin/policy/current", headers={"Authorization": f"Bearer {token_b}"})

    history_a = client.get("/admin/policy/history", headers={"Authorization": f"Bearer {token_a}"})
    history_b = client.get("/admin/policy/history", headers={"Authorization": f"Bearer {token_b}"})
    assert history_a.status_code == 200, history_a.text
    assert history_b.status_code == 200, history_b.text

    assert all(row["tenant_id"] == tenant_a.id for row in history_a.json())
    assert all(row["tenant_id"] == tenant_b.id for row in history_b.json())
    assert any(row["change_note"] == "Tenant A only" for row in history_a.json())
    assert not any(row.get("change_note") == "Tenant A only" for row in history_b.json())


def test_non_admin_users_cannot_rollback_policy(client: TestClient, db_session: Session):
    tenant = _mk_tenant(db_session, "t_policy_rbac", "Tenant Policy RBAC")
    _mk_user(db_session, "u_policy_admin", tenant.id, "policy-admin@example.com", "pw12345!", "tenant_admin")
    _mk_user(db_session, "u_policy_viewer", tenant.id, "policy-viewer@example.com", "pw12345!", "viewer")

    admin_token = _login(client, "policy-admin@example.com", "pw12345!")
    viewer_token = _login(client, "policy-viewer@example.com", "pw12345!")

    current_response = client.get("/admin/policy/current", headers={"Authorization": f"Bearer {admin_token}"})
    assert current_response.status_code == 200, current_response.text
    version_id = current_response.json()["active_version_id"]
    assert version_id

    rollback_response = client.post(
        f"/admin/policy/rollback/{version_id}",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert rollback_response.status_code == 403, rollback_response.text

    policy_row = db_session.get(TenantPolicy, tenant.id)
    assert policy_row is not None
    assert policy_row.active_version_id == version_id
