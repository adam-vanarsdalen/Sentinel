from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_api_key_token, hash_password
from app.db.models import (
    ApiKey,
    AuditEvent,
    EvalResult,
    EvalRun,
    EvalTestCase,
    Tenant,
    TenantPolicy,
    TenantPolicyVersion,
    TenantProviderConfig,
    TenantSettings,
    User,
)
from app.services.alerts import default_settings_json
from app.services.policy import DEFAULT_POLICY


PASSWORD = "pw12345!"


def _mk_tenant(db: Session, tenant_id: str, name: str) -> Tenant:
    tenant = Tenant(id=tenant_id, name=name, slug=name.lower().replace(" ", "-"), status="active")
    db.add(tenant)
    db.commit()
    return tenant


def _mk_user(db: Session, user_id: str, tenant_id: str | None, email: str, role: str) -> User:
    user = User(
        id=user_id,
        tenant_id=tenant_id,
        email=email.lower(),
        password_hash=hash_password(PASSWORD),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


def _login(client: TestClient, email: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _auth(token: str, tenant_id: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if tenant_id is not None:
        headers["X-Tenant-Id"] = tenant_id
    return headers


def _policy(label: str) -> dict:
    policy = deepcopy(DEFAULT_POLICY)
    policy["allowed_models"] = ["mock"]
    policy["require_system_prompt_prefix"] = label
    return policy


def _seed_two_tenant_fixture(db: Session) -> dict:
    tenant_a = _mk_tenant(db, "tenant-a", "Tenant A")
    tenant_b = _mk_tenant(db, "tenant-b", "Tenant B")

    users = {
        "admin_a": _mk_user(db, "admin-a", tenant_a.id, "admin-a@example.com", "org_admin"),
        "admin_b": _mk_user(db, "admin-b", tenant_b.id, "admin-b@example.com", "org_admin"),
        "reviewer_a": _mk_user(db, "reviewer-a", tenant_a.id, "reviewer-a@example.com", "reviewer"),
        "auditor_a": _mk_user(db, "auditor-a", tenant_a.id, "auditor-a@example.com", "auditor"),
        "operator_a": _mk_user(db, "operator-a", tenant_a.id, "operator-a@example.com", "operator"),
        "target_a": _mk_user(db, "target-a", tenant_a.id, "target-a@example.com", "reviewer"),
        "target_b": _mk_user(db, "target-b", tenant_b.id, "target-b@example.com", "reviewer"),
        "super_admin": _mk_user(db, "super-admin", None, "platform-admin@example.com", "super_admin"),
    }

    token_a, key_a = create_api_key_token(tenant_id=tenant_a.id, name="tenant-a-key")
    token_b, key_b = create_api_key_token(tenant_id=tenant_b.id, name="tenant-b-key")
    db.add_all([key_a, key_b])

    policy_a = TenantPolicy(tenant_id=tenant_a.id, policy_json=_policy("tenant-a"), updated_by_user_id=users["admin_a"].id)
    version_a = TenantPolicyVersion(
        id="policy-version-a",
        tenant_id=tenant_a.id,
        policy_json=_policy("tenant-a-version"),
        created_by_user_id=users["admin_a"].id,
        change_note="Tenant A version",
    )
    policy_b = TenantPolicy(tenant_id=tenant_b.id, policy_json=_policy("tenant-b"), updated_by_user_id=users["admin_b"].id)
    version_b = TenantPolicyVersion(
        id="policy-version-b",
        tenant_id=tenant_b.id,
        policy_json=_policy("tenant-b-version"),
        created_by_user_id=users["admin_b"].id,
        change_note="Tenant B version",
    )
    db.add_all([policy_a, version_a, policy_b, version_b])
    db.flush()
    policy_a.active_version_id = version_a.id
    policy_b.active_version_id = version_b.id

    provider_a = TenantProviderConfig(
        id="provider-a",
        tenant_id=tenant_a.id,
        provider_type="openai",
        display_name="Tenant A OpenAI",
        is_enabled=True,
        is_default=True,
        model_allowlist=["gpt-4.1"],
        config_json={"default_model": "gpt-4.1"},
        encrypted_secret_blob="encrypted-a",
    )
    provider_b = TenantProviderConfig(
        id="provider-b",
        tenant_id=tenant_b.id,
        provider_type="openai",
        display_name="Tenant B OpenAI",
        is_enabled=True,
        is_default=True,
        model_allowlist=["gpt-4.1"],
        config_json={"default_model": "gpt-4.1"},
        encrypted_secret_blob="encrypted-b",
    )
    db.add_all([provider_a, provider_b])

    settings_a = TenantSettings(tenant_id=tenant_a.id, settings_json={**default_settings_json(), "tenant_marker": "tenant-a"})
    settings_b = TenantSettings(tenant_id=tenant_b.id, settings_json={**default_settings_json(), "tenant_marker": "tenant-b"})
    db.add_all([settings_a, settings_b])

    now = datetime.now(timezone.utc)
    audit_a = AuditEvent(
        id="audit-a",
        tenant_id=tenant_a.id,
        api_key_id=key_a.id,
        user_id=users["admin_a"].id,
        request_id="req-a",
        matter_id="MAT-A",
        practice_group="Ops",
        timestamp=now,
        action_type="LLM_REQUEST",
        outcome="success",
        provider="mock",
        model="mock",
        phi_score=5,
        risk_flags=[],
        severity="low",
        tokens_prompt=10,
        tokens_completion=5,
        cost_usd=Decimal("1.25"),
    )
    audit_b = AuditEvent(
        id="audit-b",
        tenant_id=tenant_b.id,
        api_key_id=key_b.id,
        user_id=users["admin_b"].id,
        request_id="req-b",
        matter_id="MAT-B",
        practice_group="Ops",
        timestamp=now,
        action_type="LLM_REQUEST",
        outcome="success",
        provider="mock",
        model="mock",
        phi_score=95,
        risk_flags=["PROMPT_INJECTION_SUSPECTED"],
        severity="high",
        tokens_prompt=20,
        tokens_completion=10,
        cost_usd=Decimal("9.75"),
    )
    db.add_all([audit_a, audit_b])

    case_a = EvalTestCase(
        id="case-a",
        tenant_id=tenant_a.id,
        name="Tenant A case",
        category="benign",
        input_messages=[{"role": "user", "content": "hello from A"}],
        expected_flags=[],
    )
    case_b = EvalTestCase(
        id="case-b",
        tenant_id=tenant_b.id,
        name="Tenant B case",
        category="benign",
        input_messages=[{"role": "user", "content": "hello from B"}],
        expected_flags=[],
    )
    run_a = EvalRun(id="run-a", tenant_id=tenant_a.id, provider="mock", model="mock", status="finished", summary={"tenant": "a"})
    run_b = EvalRun(id="run-b", tenant_id=tenant_b.id, provider="mock", model="mock", status="finished", summary={"tenant": "b"})
    result_a = EvalResult(
        id="result-a",
        tenant_id=tenant_a.id,
        run_id=run_a.id,
        test_case_id=case_a.id,
        passed=True,
        observed_flags=[],
    )
    result_b = EvalResult(
        id="result-b",
        tenant_id=tenant_b.id,
        run_id=run_b.id,
        test_case_id=case_b.id,
        passed=False,
        observed_flags=["TENANT_B_ONLY"],
    )
    db.add_all([case_a, case_b, run_a, run_b, result_a, result_b])
    db.commit()

    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "users": users,
        "api_key_a": key_a,
        "api_key_b": key_b,
        "api_token_a": token_a,
        "api_token_b": token_b,
        "provider_a": provider_a,
        "provider_b": provider_b,
        "policy_version_a": version_a,
        "policy_version_b": version_b,
        "audit_a": audit_a,
        "audit_b": audit_b,
        "run_a": run_a,
        "run_b": run_b,
    }


def test_user_routes_are_tenant_isolated_for_read_create_update_delete_and_super_admin_context(
    client: TestClient, db_session: Session
):
    fixture = _seed_two_tenant_fixture(db_session)
    tenant_a = fixture["tenant_a"]
    tenant_b = fixture["tenant_b"]
    admin_a_token = _login(client, "admin-a@example.com")
    reviewer_a_token = _login(client, "reviewer-a@example.com")
    super_token = _login(client, "platform-admin@example.com")

    listed = client.get("/admin/users", headers=_auth(admin_a_token))
    assert listed.status_code == 200, listed.text
    assert {row["tenant_id"] for row in listed.json()} == {tenant_a.id}
    assert "target-b@example.com" not in {row["email"] for row in listed.json()}

    create_cross_tenant = client.post(
        "/admin/users",
        headers=_auth(admin_a_token),
        json={"email": "created-by-a@example.com", "role": "reviewer", "tenant_id": tenant_b.id},
    )
    assert create_cross_tenant.status_code == 200, create_cross_tenant.text
    assert create_cross_tenant.json()["user"]["tenant_id"] == tenant_a.id
    assert db_session.get(User, create_cross_tenant.json()["user"]["id"]).tenant_id == tenant_a.id

    update_b = client.put(
        f"/admin/users/{fixture['users']['target_b'].id}/role",
        headers=_auth(admin_a_token),
        json={"role": "operator"},
    )
    assert update_b.status_code == 404, update_b.text
    assert db_session.get(User, fixture["users"]["target_b"].id).role == "reviewer"

    delete_b = client.delete(f"/admin/users/{fixture['users']['target_b'].id}", headers=_auth(admin_a_token))
    assert delete_b.status_code == 404, delete_b.text
    assert db_session.get(User, fixture["users"]["target_b"].id).is_active is True

    reviewer_list = client.get("/admin/users", headers=_auth(reviewer_a_token))
    assert reviewer_list.status_code == 200, reviewer_list.text
    assert {row["tenant_id"] for row in reviewer_list.json()} == {tenant_a.id}
    reviewer_create = client.post(
        "/admin/users",
        headers=_auth(reviewer_a_token),
        json={"email": "blocked@example.com", "role": "reviewer"},
    )
    assert reviewer_create.status_code == 403, reviewer_create.text

    super_without_context = client.get("/admin/users", headers=_auth(super_token))
    assert super_without_context.status_code == 400, super_without_context.text
    super_b_list = client.get("/admin/users", headers=_auth(super_token, tenant_b.id))
    assert super_b_list.status_code == 200, super_b_list.text
    assert {row["tenant_id"] for row in super_b_list.json()} == {tenant_b.id}
    super_a_update_b = client.put(
        f"/admin/users/{fixture['users']['target_b'].id}/role",
        headers=_auth(super_token, tenant_a.id),
        json={"role": "operator"},
    )
    assert super_a_update_b.status_code == 404, super_a_update_b.text


def test_api_key_routes_and_gateway_api_keys_are_tenant_isolated(client: TestClient, db_session: Session):
    fixture = _seed_two_tenant_fixture(db_session)
    tenant_a = fixture["tenant_a"]
    admin_a_token = _login(client, "admin-a@example.com")
    reviewer_a_token = _login(client, "reviewer-a@example.com")

    listed = client.get("/admin/api-keys", headers=_auth(admin_a_token))
    assert listed.status_code == 200, listed.text
    assert {row["name"] for row in listed.json()} == {"tenant-a-key"}

    created = client.post("/admin/api-keys", headers=_auth(admin_a_token), json={"name": "created-a"})
    assert created.status_code == 200, created.text
    assert db_session.get(ApiKey, created.json()["api_key"]["id"]).tenant_id == tenant_a.id

    revoke_b = client.post(f"/admin/api-keys/{fixture['api_key_b'].id}/revoke", headers=_auth(admin_a_token))
    assert revoke_b.status_code == 404, revoke_b.text
    assert db_session.get(ApiKey, fixture["api_key_b"].id).is_active is True

    reviewer_create = client.post("/admin/api-keys", headers=_auth(reviewer_a_token), json={"name": "blocked"})
    assert reviewer_create.status_code == 403, reviewer_create.text
    reviewer_revoke = client.post(f"/admin/api-keys/{fixture['api_key_a'].id}/revoke", headers=_auth(reviewer_a_token))
    assert reviewer_revoke.status_code == 403, reviewer_revoke.text

    gateway_with_b_key = client.post(
        "/v1/chat/completions",
        headers={"X-API-Key": fixture["api_token_b"]},
        json={"provider": "mock", "model": "mock", "messages": [{"role": "user", "content": "hello"}], "max_tokens": 8},
    )
    assert gateway_with_b_key.status_code == 200, gateway_with_b_key.text
    newest_b_event = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.api_key_id == fixture["api_key_b"].id)
        .order_by(AuditEvent.timestamp.desc())
        .first()
    )
    assert newest_b_event is not None
    assert newest_b_event.tenant_id == fixture["tenant_b"].id


def test_policy_routes_do_not_expose_or_modify_other_tenant_versions(client: TestClient, db_session: Session):
    fixture = _seed_two_tenant_fixture(db_session)
    tenant_a = fixture["tenant_a"]
    tenant_b = fixture["tenant_b"]
    admin_a_token = _login(client, "admin-a@example.com")
    reviewer_a_token = _login(client, "reviewer-a@example.com")
    super_token = _login(client, "platform-admin@example.com")

    current = client.get("/admin/policy/current", headers=_auth(admin_a_token))
    assert current.status_code == 200, current.text
    assert current.json()["tenant_id"] == tenant_a.id
    assert current.json()["policy_json"]["require_system_prompt_prefix"] == "tenant-a"

    history = client.get("/admin/policy/history", headers=_auth(admin_a_token))
    assert history.status_code == 200, history.text
    assert {row["tenant_id"] for row in history.json()} == {tenant_a.id}

    get_b_version = client.get(f"/admin/policy/history/{fixture['policy_version_b'].id}", headers=_auth(admin_a_token))
    assert get_b_version.status_code == 404, get_b_version.text

    rollback_b = client.post(f"/admin/policy/rollback/{fixture['policy_version_b'].id}", headers=_auth(admin_a_token))
    assert rollback_b.status_code == 404, rollback_b.text
    assert db_session.get(TenantPolicy, tenant_a.id).active_version_id == fixture["policy_version_a"].id
    assert db_session.get(TenantPolicy, tenant_b.id).active_version_id == fixture["policy_version_b"].id

    updated_policy = _policy("tenant-a-updated")
    update = client.put(
        "/admin/policy/current",
        headers=_auth(admin_a_token),
        json={"policy_json": updated_policy, "change_note": "tenant A only"},
    )
    assert update.status_code == 200, update.text
    assert update.json()["tenant_id"] == tenant_a.id
    assert db_session.get(TenantPolicy, tenant_b.id).policy_json["require_system_prompt_prefix"] == "tenant-b"

    reviewer_update = client.put(
        "/admin/policy/current",
        headers=_auth(reviewer_a_token),
        json={"policy_json": _policy("blocked")},
    )
    assert reviewer_update.status_code == 403, reviewer_update.text

    super_without_context = client.get("/admin/policy/current", headers=_auth(super_token))
    assert super_without_context.status_code == 400, super_without_context.text
    super_b_current = client.get("/admin/policy/current", headers=_auth(super_token, tenant_b.id))
    assert super_b_current.status_code == 200, super_b_current.text
    assert super_b_current.json()["tenant_id"] == tenant_b.id


def test_provider_config_routes_are_tenant_isolated_for_list_update_delete_and_actions(
    client: TestClient, db_session: Session
):
    fixture = _seed_two_tenant_fixture(db_session)
    admin_a_token = _login(client, "admin-a@example.com")
    reviewer_a_token = _login(client, "reviewer-a@example.com")
    super_token = _login(client, "platform-admin@example.com")

    listed = client.get("/admin/provider-configs", headers=_auth(admin_a_token))
    assert listed.status_code == 200, listed.text
    assert {row["id"] for row in listed.json()} == {fixture["provider_a"].id}

    for method, path, kwargs in [
        (
            "patch",
            f"/admin/provider-configs/{fixture['provider_b'].id}",
            {"json": {"display_name": "Tenant A should not update B"}},
        ),
        ("delete", f"/admin/provider-configs/{fixture['provider_b'].id}", {}),
        ("post", f"/admin/provider-configs/{fixture['provider_b'].id}/set-default", {}),
        ("post", f"/admin/provider-configs/{fixture['provider_b'].id}/test-connection", {}),
        ("get", f"/admin/provider-configs/{fixture['provider_b'].id}/models", {}),
    ]:
        response = getattr(client, method)(path, headers=_auth(admin_a_token), **kwargs)
        assert response.status_code == 404, f"{method} {path}: {response.text}"

    assert db_session.get(TenantProviderConfig, fixture["provider_b"].id).display_name == "Tenant B OpenAI"

    create_a = client.post(
        "/admin/provider-configs",
        headers=_auth(admin_a_token),
        json={
            "provider_type": "anthropic",
            "display_name": "Tenant A Anthropic",
            "is_enabled": True,
            "model_allowlist": ["claude-sonnet-4-6"],
            "config_json": {"default_model": "claude-sonnet-4-6"},
            "secret_json": {"api_key": "__TEST_PROVIDER_SECRET__"},
        },
    )
    assert create_a.status_code == 201, create_a.text
    assert create_a.json()["tenant_id"] == fixture["tenant_a"].id

    reviewer_list = client.get("/admin/provider-configs", headers=_auth(reviewer_a_token))
    assert reviewer_list.status_code == 403, reviewer_list.text
    super_list = client.get("/admin/provider-configs", headers=_auth(super_token, fixture["tenant_a"].id))
    assert super_list.status_code == 403, super_list.text


def test_audit_logs_exports_and_usage_metrics_are_tenant_bounded(client: TestClient, db_session: Session):
    fixture = _seed_two_tenant_fixture(db_session)
    admin_a_token = _login(client, "admin-a@example.com")
    auditor_a_token = _login(client, "auditor-a@example.com")

    listed = client.get("/admin/audit-events", headers=_auth(admin_a_token), params={"matter_id": "MAT-A"})
    assert listed.status_code == 200, listed.text
    assert {row["tenant_id"] for row in listed.json()} == {fixture["tenant_a"].id}
    assert "audit-b" not in {row["id"] for row in listed.json()}

    cross_tenant_filter = client.get(
        "/admin/audit-events/search",
        headers=_auth(admin_a_token),
        params={"api_key_id": fixture["api_key_b"].id},
    )
    assert cross_tenant_filter.status_code == 200, cross_tenant_filter.text
    assert cross_tenant_filter.json()["total"] == 0
    assert cross_tenant_filter.json()["items"] == []

    get_b = client.get(f"/admin/audit-events/{fixture['audit_b'].id}", headers=_auth(admin_a_token))
    assert get_b.status_code == 404, get_b.text

    export_json = client.get("/admin/audit-events/export.json", headers=_auth(auditor_a_token))
    assert export_json.status_code == 200, export_json.text
    assert "audit-a" in export_json.text
    assert "audit-b" not in export_json.text
    assert "tenant-b" not in export_json.text

    export_csv = client.get("/admin/audit-events/export.csv", headers=_auth(auditor_a_token))
    assert export_csv.status_code == 200, export_csv.text
    assert "audit-a" in export_csv.text
    assert "audit-b" not in export_csv.text

    cost = client.get("/admin/metrics/cost-summary", headers=_auth(admin_a_token))
    assert cost.status_code == 200, cost.text
    assert abs(cost.json()["this_month"]["total_usd"] - 1.25) < 1e-9
    assert all(row["model"] == "mock" for row in cost.json()["by_model_this_month"])

    risk = client.get("/admin/metrics/risk-summary", headers=_auth(admin_a_token))
    assert risk.status_code == 200, risk.text
    assert risk.json()["total_ai_requests"] == 1
    assert risk.json()["injection_attempts_flagged"] == 0
    assert {row["matter_id"] for row in risk.json()["top_matters"]} == {"MAT-A"}

    reviewer_export = client.get("/admin/audit-events/export.json", headers=_auth(_login(client, "reviewer-a@example.com")))
    assert reviewer_export.status_code == 403, reviewer_export.text


def test_eval_usage_records_are_tenant_isolated(client: TestClient, db_session: Session):
    fixture = _seed_two_tenant_fixture(db_session)
    admin_a_token = _login(client, "admin-a@example.com")
    reviewer_a_token = _login(client, "reviewer-a@example.com")

    runs = client.get("/admin/evals/runs", headers=_auth(admin_a_token))
    assert runs.status_code == 200, runs.text
    assert {row["id"] for row in runs.json()} == {fixture["run_a"].id}

    suites = client.get("/admin/evals/suites", headers=_auth(admin_a_token))
    assert suites.status_code == 200, suites.text
    assert {row["id"] for row in suites.json()} == {"case-a"}

    run_a = client.get(f"/admin/evals/runs/{fixture['run_a'].id}", headers=_auth(reviewer_a_token))
    assert run_a.status_code == 200, run_a.text
    assert run_a.json()["run"]["tenant_id"] == fixture["tenant_a"].id
    assert {row["id"] for row in run_a.json()["results"]} == {"result-a"}

    run_b = client.get(f"/admin/evals/runs/{fixture['run_b'].id}", headers=_auth(admin_a_token))
    assert run_b.status_code == 404, run_b.text


def test_settings_alerts_and_platform_admin_routes_do_not_cross_tenant_boundaries(
    client: TestClient, db_session: Session
):
    fixture = _seed_two_tenant_fixture(db_session)
    admin_a_token = _login(client, "admin-a@example.com")
    reviewer_a_token = _login(client, "reviewer-a@example.com")
    super_token = _login(client, "platform-admin@example.com")

    settings = client.get("/admin/settings/current", headers=_auth(admin_a_token))
    assert settings.status_code == 200, settings.text
    assert settings.json()["tenant_id"] == fixture["tenant_a"].id
    assert settings.json()["settings_json"]["tenant_marker"] == "tenant-a"

    updated = client.put(
        "/admin/settings/current",
        headers=_auth(admin_a_token),
        json={"settings_json": {"tenant_marker": "tenant-a-updated"}},
    )
    assert updated.status_code == 200, updated.text
    assert db_session.get(TenantSettings, fixture["tenant_a"].id).settings_json["tenant_marker"] == "tenant-a-updated"
    assert db_session.get(TenantSettings, fixture["tenant_b"].id).settings_json["tenant_marker"] == "tenant-b"

    reviewer_settings_update = client.put(
        "/admin/settings/current",
        headers=_auth(reviewer_a_token),
        json={"settings_json": {"tenant_marker": "blocked"}},
    )
    assert reviewer_settings_update.status_code == 403, reviewer_settings_update.text

    alerts = client.get("/admin/alerts/current", headers=_auth(admin_a_token))
    assert alerts.status_code == 200, alerts.text
    assert alerts.json()["tenant_id"] == fixture["tenant_a"].id
    alert_history = client.get("/admin/alerts/history", headers=_auth(admin_a_token))
    assert alert_history.status_code == 200, alert_history.text
    assert all(item["id"] != fixture["audit_b"].id for item in alert_history.json())

    for method, path, kwargs in [
        ("get", "/platform/tenants", {}),
        ("post", "/platform/tenants", {"json": {"name": "Blocked Tenant"}}),
        ("get", f"/platform/tenants/{fixture['tenant_b'].id}", {}),
        ("patch", f"/platform/tenants/{fixture['tenant_b'].id}", {"json": {"status": "suspended"}}),
        ("post", f"/platform/tenants/{fixture['tenant_b'].id}/switch", {}),
        ("get", f"/platform/tenants/{fixture['tenant_b'].id}/summary", {}),
    ]:
        response = getattr(client, method)(path, headers=_auth(admin_a_token), **kwargs)
        assert response.status_code == 403, f"{method} {path}: {response.text}"

    platform_list = client.get("/platform/tenants", headers=_auth(super_token))
    assert platform_list.status_code == 200, platform_list.text
    assert {row["id"] for row in platform_list.json()["items"]} >= {fixture["tenant_a"].id, fixture["tenant_b"].id}

    tenant_b_detail = client.get(f"/platform/tenants/{fixture['tenant_b'].id}", headers=_auth(super_token))
    assert tenant_b_detail.status_code == 200, tenant_b_detail.text
    assert tenant_b_detail.json()["tenant"]["id"] == fixture["tenant_b"].id
