from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_api_key_token, hash_password
from app.db.models import AuditEvent, Tenant, TenantPolicy, TenantProviderConfig, User
from app.services.policy import DEFAULT_POLICY
from app.services.providers.base import ProviderResponse


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


def test_provider_configs_are_tenant_isolated_and_mask_secrets(client: TestClient, db_session: Session):
    t1 = _mk_tenant(db_session, "t1", "Tenant 1")
    t2 = _mk_tenant(db_session, "t2", "Tenant 2")
    _mk_user(db_session, "u1", t1.id, "admin1@example.com", "pw12345!", "tenant_admin")
    _mk_user(db_session, "u2", t2.id, "admin2@example.com", "pw12345!", "tenant_admin")

    jwt1 = _login(client, "admin1@example.com", "pw12345!")
    jwt2 = _login(client, "admin2@example.com", "pw12345!")

    secret = "sk-test-secret-123"
    r = client.post(
        "/admin/provider-configs",
        headers={"Authorization": f"Bearer {jwt1}"},
        json={
            "provider_type": "openai",
            "display_name": "Firm OpenAI",
            "is_enabled": True,
            "is_default": True,
            "model_allowlist": ["gpt-4.1"],
            "config_json": {"default_model": "gpt-4.1"},
            "secret_json": {"api_key": secret},
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["tenant_id"] == t1.id
    assert body["secret_configured"] is True
    assert body["secret_status"] == "configured"
    assert "api_key" not in str(body)
    assert secret not in r.text

    stored = db_session.query(TenantProviderConfig).filter(TenantProviderConfig.tenant_id == t1.id).one()
    assert stored.encrypted_secret_blob
    assert secret not in stored.encrypted_secret_blob

    list_1 = client.get("/admin/provider-configs", headers={"Authorization": f"Bearer {jwt1}"})
    assert list_1.status_code == 200, list_1.text
    assert len(list_1.json()) == 1
    assert list_1.json()[0]["display_name"] == "Firm OpenAI"

    list_2 = client.get("/admin/provider-configs", headers={"Authorization": f"Bearer {jwt2}"})
    assert list_2.status_code == 200, list_2.text
    assert list_2.json() == []


def test_non_tenant_admin_cannot_manage_provider_configs(client: TestClient, db_session: Session):
    tenant = _mk_tenant(db_session, "t1", "Tenant 1")
    _mk_user(db_session, "viewer", tenant.id, "viewer@example.com", "pw12345!", "viewer")
    jwt = _login(client, "viewer@example.com", "pw12345!")

    r = client.get("/admin/provider-configs", headers={"Authorization": f"Bearer {jwt}"})
    assert r.status_code == 403, r.text

    r2 = client.post(
        "/admin/provider-configs",
        headers={"Authorization": f"Bearer {jwt}"},
        json={"provider_type": "openai", "display_name": "Blocked", "secret_json": {"api_key": "x"}},
    )
    assert r2.status_code == 403, r2.text


def test_super_admin_cannot_manage_provider_configs(client: TestClient, db_session: Session):
    _mk_user(db_session, "super", None, "platform-admin@example.com", "pw12345!", "super_admin")
    jwt = _login(client, "platform-admin@example.com", "pw12345!")

    r = client.get("/admin/provider-configs", headers={"Authorization": f"Bearer {jwt}"})
    assert r.status_code == 403, r.text


def test_gateway_uses_tenant_default_provider_config(client: TestClient, db_session: Session, monkeypatch):
    from app.services.providers.openai_provider import OpenAiProvider

    tenant = _mk_tenant(db_session, "t1", "Tenant 1")
    token, api_key = create_api_key_token(tenant_id=tenant.id, name="firm-app")
    db_session.add(api_key)
    policy = dict(DEFAULT_POLICY)
    policy["allowed_models"] = ["gpt-4.1"]
    db_session.add(TenantPolicy(tenant_id=tenant.id, policy_json=policy))
    db_session.add(
        TenantProviderConfig(
            id="pc1",
            tenant_id=tenant.id,
            provider_type="openai",
            display_name="Firm OpenAI",
            is_enabled=True,
            is_default=True,
            model_allowlist=["gpt-4.1"],
            config_json={"default_model": "gpt-4.1"},
            encrypted_secret_blob="gAAAAABfake",
        )
    )
    db_session.commit()

    def _fake_chat_completions(
        self,
        *,
        model: str,
        messages: list[dict],
        max_tokens: int | None,
        temperature: float | None,
        runtime_config: dict | None = None,
    ) -> ProviderResponse:
        assert runtime_config is not None
        return ProviderResponse(content="Firm provider response", raw={"ok": True}, prompt_tokens=4, completion_tokens=3)

    monkeypatch.setattr(OpenAiProvider, "chat_completions", _fake_chat_completions)
    monkeypatch.setattr("app.services.provider_configs.secret_payload", lambda row: {"api_key": "tenant-openai-key"})

    r = client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {token}"},
        json={"model": "gpt-4.1", "messages": [{"role": "user", "content": "hello"}], "max_tokens": 32},
    )
    assert r.status_code == 200, r.text
    assert r.json()["choices"][0]["message"]["content"] == "Firm provider response"

    ev = db_session.query(AuditEvent).filter(AuditEvent.tenant_id == tenant.id).order_by(AuditEvent.timestamp.desc()).first()
    assert ev is not None
    assert ev.provider == "openai"
    assert ev.model == "gpt-4.1"
    assert (ev.event_data or {}).get("metadata", {}).get("provider_config_id") == "pc1"


def test_gateway_uses_default_model_when_request_omits_model(client: TestClient, db_session: Session, monkeypatch):
    from app.services.providers.openai_provider import OpenAiProvider

    tenant = _mk_tenant(db_session, "t_default_model", "Tenant Default Model")
    token, api_key = create_api_key_token(tenant_id=tenant.id, name="firm-app")
    db_session.add(api_key)
    policy = dict(DEFAULT_POLICY)
    policy["allowed_models"] = ["gpt-4.1"]
    db_session.add(TenantPolicy(tenant_id=tenant.id, policy_json=policy))
    db_session.add(
        TenantProviderConfig(
            id="pc_default_model",
            tenant_id=tenant.id,
            provider_type="openai",
            display_name="Firm OpenAI",
            is_enabled=True,
            is_default=True,
            model_allowlist=["gpt-4.1"],
            config_json={"default_model": "gpt-4.1"},
            encrypted_secret_blob="gAAAAABfake",
        )
    )
    db_session.commit()

    def _fake_chat_completions(
        self,
        *,
        model: str,
        messages: list[dict],
        max_tokens: int | None,
        temperature: float | None,
        runtime_config: dict | None = None,
    ) -> ProviderResponse:
        assert model == "gpt-4.1"
        return ProviderResponse(content="Default model response", raw={"ok": True}, prompt_tokens=4, completion_tokens=3)

    monkeypatch.setattr(OpenAiProvider, "chat_completions", _fake_chat_completions)
    monkeypatch.setattr("app.services.provider_configs.secret_payload", lambda row: {"api_key": "tenant-openai-key"})

    r = client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {token}"},
        json={"messages": [{"role": "user", "content": "hello"}], "max_tokens": 32},
    )
    assert r.status_code == 200, r.text
    assert r.json()["model"] == "gpt-4.1"


def test_gateway_blocks_model_outside_provider_allowlist(client: TestClient, db_session: Session):
    tenant = _mk_tenant(db_session, "t1", "Tenant 1")
    token, api_key = create_api_key_token(tenant_id=tenant.id, name="firm-app")
    db_session.add(api_key)
    policy = dict(DEFAULT_POLICY)
    policy["allowed_models"] = ["gpt-4.1", "gpt-4.1"]
    db_session.add(TenantPolicy(tenant_id=tenant.id, policy_json=policy))
    db_session.add(
        TenantProviderConfig(
            id="pc1",
            tenant_id=tenant.id,
            provider_type="openai",
            display_name="Firm OpenAI",
            is_enabled=True,
            is_default=True,
            model_allowlist=["gpt-4.1-mini"],
            config_json={"default_model": "gpt-4.1"},
            encrypted_secret_blob="gAAAAABfake",
        )
    )
    db_session.commit()

    r = client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {token}"},
        json={"model": "gpt-4.1", "messages": [{"role": "user", "content": "hello"}], "max_tokens": 32},
    )
    assert r.status_code == 403, r.text
    body = r.json()
    assert body["outcome"] == "BLOCKED"
    assert body["reason_code"] == "model_not_approved"
    assert body["policy"]["rule"] == "provider_policy"
    assert body["provider"] == "openai"
    assert body["model"] == "gpt-4.1"
    assert "Model not approved for tenant provider" in body["block_reason"]

    ev = db_session.query(AuditEvent).filter(AuditEvent.tenant_id == tenant.id).order_by(AuditEvent.timestamp.desc()).first()
    assert ev is not None
    assert ev.action_type == "MODEL_DENY"
    assert (ev.event_data or {}).get("metadata", {}).get("reason_code") == "model_not_approved"


def test_gateway_blocks_provider_outside_tenant_approvals(client: TestClient, db_session: Session):
    tenant = _mk_tenant(db_session, "t_provider_block", "Tenant Provider Block")
    token, api_key = create_api_key_token(tenant_id=tenant.id, name="firm-app")
    db_session.add(api_key)
    policy = dict(DEFAULT_POLICY)
    policy["allowed_models"] = ["gpt-4.1", "claude-sonnet-4-6"]
    db_session.add(TenantPolicy(tenant_id=tenant.id, policy_json=policy))
    db_session.add(
        TenantProviderConfig(
            id="pc_openai_only",
            tenant_id=tenant.id,
            provider_type="openai",
            display_name="Firm OpenAI",
            is_enabled=True,
            is_default=True,
            model_allowlist=["gpt-4.1"],
            config_json={"default_model": "gpt-4.1"},
            encrypted_secret_blob="gAAAAABfake",
        )
    )
    db_session.commit()

    r = client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "messages": [{"role": "user", "content": "hello"}],
            "max_tokens": 32,
        },
    )
    assert r.status_code == 403, r.text
    body = r.json()
    assert body["outcome"] == "BLOCKED"
    assert body["reason_code"] == "provider_not_approved"
    assert body["provider"] == "anthropic"
    assert body["model"] == "claude-sonnet-4-6"

    ev = db_session.query(AuditEvent).filter(AuditEvent.tenant_id == tenant.id).order_by(AuditEvent.timestamp.desc()).first()
    assert ev is not None
    assert ev.action_type == "PROVIDER_DENY"
    assert (ev.event_data or {}).get("metadata", {}).get("reason_code") == "provider_not_approved"


def test_gateway_allows_explicit_mock_provider_in_non_production(client: TestClient, db_session: Session):
    tenant = _mk_tenant(db_session, "t_mock_override", "Tenant Mock Override")
    token, api_key = create_api_key_token(tenant_id=tenant.id, name="firm-app")
    db_session.add(api_key)
    policy = dict(DEFAULT_POLICY)
    policy["allowed_models"] = ["mock", "gpt-4.1"]
    db_session.add(TenantPolicy(tenant_id=tenant.id, policy_json=policy))
    db_session.add(
        TenantProviderConfig(
            id="pc_openai_for_mock_override",
            tenant_id=tenant.id,
            provider_type="openai",
            display_name="Firm OpenAI",
            is_enabled=True,
            is_default=True,
            model_allowlist=["gpt-4.1"],
            config_json={"default_model": "gpt-4.1"},
            encrypted_secret_blob="gAAAAABfake",
        )
    )
    db_session.commit()

    r = client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "provider": "mock",
            "model": "mock",
            "messages": [{"role": "user", "content": "hello"}],
            "max_tokens": 32,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["model"] == "mock"
    assert "[mock:mock]" in body["choices"][0]["message"]["content"]

    ev = db_session.query(AuditEvent).filter(AuditEvent.tenant_id == tenant.id).order_by(AuditEvent.timestamp.desc()).first()
    assert ev is not None
    assert ev.provider == "mock"
    assert ev.model == "mock"


def test_tenant_b_policy_changes_do_not_affect_tenant_a(client: TestClient, db_session: Session, monkeypatch):
    from app.services.providers.openai_provider import OpenAiProvider

    tenant_a = _mk_tenant(db_session, "t_approve_a", "Tenant Approve A")
    tenant_b = _mk_tenant(db_session, "t_approve_b", "Tenant Approve B")
    token_a, api_key_a = create_api_key_token(tenant_id=tenant_a.id, name="firm-a")
    token_b, api_key_b = create_api_key_token(tenant_id=tenant_b.id, name="firm-b")
    db_session.add_all([api_key_a, api_key_b])

    policy_a = dict(DEFAULT_POLICY)
    policy_a["allowed_models"] = ["gpt-4.1"]
    policy_b = dict(DEFAULT_POLICY)
    policy_b["allowed_models"] = ["gpt-4.1-mini"]
    db_session.add_all(
        [
            TenantPolicy(tenant_id=tenant_a.id, policy_json=policy_a),
            TenantPolicy(tenant_id=tenant_b.id, policy_json=policy_b),
            TenantProviderConfig(
                id="pc_a",
                tenant_id=tenant_a.id,
                provider_type="openai",
                display_name="A OpenAI",
                is_enabled=True,
                is_default=True,
                model_allowlist=["gpt-4.1"],
                config_json={"default_model": "gpt-4.1"},
                encrypted_secret_blob="blob-a",
            ),
            TenantProviderConfig(
                id="pc_b",
                tenant_id=tenant_b.id,
                provider_type="openai",
                display_name="B OpenAI",
                is_enabled=True,
                is_default=True,
                model_allowlist=["gpt-4.1-mini"],
                config_json={"default_model": "gpt-4.1-mini"},
                encrypted_secret_blob="blob-b",
            ),
        ]
    )
    db_session.commit()

    def _fake_chat_completions(
        self,
        *,
        model: str,
        messages: list[dict],
        max_tokens: int | None,
        temperature: float | None,
        runtime_config: dict | None = None,
    ) -> ProviderResponse:
        return ProviderResponse(content=f"ok:{model}", raw={"ok": True}, prompt_tokens=3, completion_tokens=2)

    monkeypatch.setattr(OpenAiProvider, "chat_completions", _fake_chat_completions)
    monkeypatch.setattr("app.services.provider_configs.secret_payload", lambda row: {"api_key": "tenant-openai-key"})

    blocked = client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"model": "gpt-4.1-mini", "messages": [{"role": "user", "content": "hello"}]},
    )
    assert blocked.status_code == 403, blocked.text
    assert blocked.json()["reason_code"] == "model_not_approved"

    allowed = client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"model": "gpt-4.1-mini", "messages": [{"role": "user", "content": "hello"}]},
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["model"] == "gpt-4.1-mini"


def test_provider_policy_endpoint_updates_only_current_tenant(client: TestClient, db_session: Session):
    tenant_a = _mk_tenant(db_session, "t_policy_a", "Tenant Policy A")
    tenant_b = _mk_tenant(db_session, "t_policy_b", "Tenant Policy B")
    _mk_user(db_session, "admin_a", tenant_a.id, "admin-a@example.com", "pw12345!", "tenant_admin")
    _mk_user(db_session, "admin_b", tenant_b.id, "admin-b@example.com", "pw12345!", "tenant_admin")
    db_session.add_all(
        [
            TenantProviderConfig(
                id="pc_policy_a",
                tenant_id=tenant_a.id,
                provider_type="openai",
                display_name="A OpenAI",
                is_enabled=True,
                is_default=True,
                model_allowlist=["gpt-4.1"],
                config_json={"default_model": "gpt-4.1"},
                encrypted_secret_blob="blob-a",
            ),
            TenantProviderConfig(
                id="pc_policy_b",
                tenant_id=tenant_b.id,
                provider_type="openai",
                display_name="B OpenAI",
                is_enabled=True,
                is_default=True,
                model_allowlist=["gpt-4.1-mini"],
                config_json={"default_model": "gpt-4.1-mini"},
                encrypted_secret_blob="blob-b",
            ),
        ]
    )
    db_session.commit()

    jwt_a = _login(client, "admin-a@example.com", "pw12345!")
    jwt_b = _login(client, "admin-b@example.com", "pw12345!")

    update = client.put(
        "/admin/provider-configs/policy",
        headers={"Authorization": f"Bearer {jwt_a}"},
        json={
            "default_provider": "openai",
            "providers": [{"provider_type": "openai", "is_enabled": True, "allowed_models": ["gpt-4.1"], "default_model": "gpt-4.1"}],
        },
    )
    assert update.status_code == 200, update.text
    assert update.json()["default_provider"] == "openai"
    providers_a = {item["provider_type"]: item for item in update.json()["providers"]}
    assert providers_a["openai"]["allowed_models"] == ["gpt-4.1"]

    policy_b = client.get("/admin/provider-configs/policy", headers={"Authorization": f"Bearer {jwt_b}"})
    assert policy_b.status_code == 200, policy_b.text
    providers_b = {item["provider_type"]: item for item in policy_b.json()["providers"]}
    assert providers_b["openai"]["allowed_models"] == ["gpt-4.1-mini"]

    ev = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.tenant_id == tenant_a.id, AuditEvent.action_type == "PROVIDER_POLICY_UPDATE")
        .order_by(AuditEvent.timestamp.desc())
        .first()
    )
    assert ev is not None
    assert ev.outcome == "success"


def test_set_default_provider_config_writes_audit_event(client: TestClient, db_session: Session):
    tenant = _mk_tenant(db_session, "t1", "Tenant 1")
    _mk_user(db_session, "admin", tenant.id, "admin@example.com", "pw12345!", "tenant_admin")
    jwt = _login(client, "admin@example.com", "pw12345!")

    openai_cfg = TenantProviderConfig(
        id="pc1",
        tenant_id=tenant.id,
        provider_type="openai",
        display_name="OpenAI",
        is_enabled=True,
        is_default=True,
        model_allowlist=["gpt-4.1"],
        config_json={"default_model": "gpt-4.1"},
        encrypted_secret_blob="blob1",
    )
    anthropic_cfg = TenantProviderConfig(
        id="pc2",
        tenant_id=tenant.id,
        provider_type="anthropic",
        display_name="Anthropic",
        is_enabled=True,
        is_default=False,
        model_allowlist=["claude-sonnet-4-6"],
        config_json={"default_model": "claude-sonnet-4-6"},
        encrypted_secret_blob="blob2",
    )
    db_session.add_all([openai_cfg, anthropic_cfg])
    db_session.commit()

    r = client.post("/admin/provider-configs/pc2/set-default", headers={"Authorization": f"Bearer {jwt}"})
    assert r.status_code == 200, r.text
    assert r.json()["id"] == "pc2"
    assert r.json()["is_default"] is True

    db_session.refresh(openai_cfg)
    db_session.refresh(anthropic_cfg)
    assert openai_cfg.is_default is False
    assert anthropic_cfg.is_default is True

    ev = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.tenant_id == tenant.id, AuditEvent.action_type == "PROVIDER_CONFIG_SET_DEFAULT")
        .order_by(AuditEvent.timestamp.desc())
        .first()
    )
    assert ev is not None
    assert ev.outcome == "success"


def test_ollama_provider_config_accepts_empty_secret_and_discovers_models(client: TestClient, db_session: Session, monkeypatch):
    from app.services.providers.ollama_provider import OllamaProvider

    tenant = _mk_tenant(db_session, "t_ollama_cfg", "Tenant Ollama")
    _mk_user(db_session, "admin_ollama", tenant.id, "admin-ollama@example.com", "pw12345!", "org_admin")
    jwt = _login(client, "admin-ollama@example.com", "pw12345!")

    created = client.post(
        "/admin/provider-configs",
        headers={"Authorization": f"Bearer {jwt}"},
        json={
            "provider_type": "ollama",
            "display_name": "Ollama Local",
            "is_enabled": True,
            "is_default": True,
            "model_allowlist": ["gpt-oss:120b-cloud"],
            "config_json": {"base_url": "http://localhost:11434/v1/", "default_model": "gpt-oss:120b-cloud"},
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["provider_type"] == "ollama"
    assert body["secret_configured"] is False
    assert '"api_key":"' not in created.text

    monkeypatch.setattr(
        OllamaProvider,
        "list_models",
        lambda self, runtime_config=None: [{"id": "gpt-oss:120b-cloud", "family": "gpt-oss", "families": ["gpt-oss"]}],
    )
    discovered = client.get(f"/admin/provider-configs/{body['id']}/models", headers={"Authorization": f"Bearer {jwt}"})
    assert discovered.status_code == 200, discovered.text
    assert discovered.json()["provider_type"] == "ollama"
    assert discovered.json()["models"][0]["id"] == "gpt-oss:120b-cloud"


def test_ollama_connection_test_uses_catalog_default_model_when_not_configured(
    client: TestClient, db_session: Session, monkeypatch
):
    from app.services.providers.ollama_provider import OllamaProvider

    tenant = _mk_tenant(db_session, "t_ollama_default_test", "Tenant Ollama Default Test")
    _mk_user(db_session, "admin_ollama_default", tenant.id, "admin-ollama-default@example.com", "pw12345!", "org_admin")
    jwt = _login(client, "admin-ollama-default@example.com", "pw12345!")

    created = client.post(
        "/admin/provider-configs",
        headers={"Authorization": f"Bearer {jwt}"},
        json={
            "provider_type": "ollama",
            "display_name": "Ollama Local",
            "is_enabled": True,
            "is_default": True,
            "model_allowlist": [],
            "config_json": {"base_url": "http://localhost:11434/v1/"},
        },
    )
    assert created.status_code == 201, created.text
    provider_config_id = created.json()["id"]

    def _fake_chat(
        self,
        *,
        model: str,
        messages: list[dict],
        max_tokens: int | None,
        temperature: float | None,
        runtime_config: dict | None = None,
    ) -> ProviderResponse:
        assert model == "gpt-oss:120b-cloud"
        return ProviderResponse(content="OK", raw={"ok": True}, prompt_tokens=1, completion_tokens=1)

    monkeypatch.setattr(OllamaProvider, "chat_completions", _fake_chat)

    tested = client.post(f"/admin/provider-configs/{provider_config_id}/test-connection", headers={"Authorization": f"Bearer {jwt}"})
    assert tested.status_code == 200, tested.text
    assert tested.json()["model"] == "gpt-oss:120b-cloud"


def test_gateway_allows_ollama_allowed_model_and_blocks_disallowed(client: TestClient, db_session: Session, monkeypatch):
    from app.services.providers.ollama_provider import OllamaProvider

    tenant = _mk_tenant(db_session, "t_ollama_gateway", "Tenant Ollama Gateway")
    token, api_key = create_api_key_token(tenant_id=tenant.id, name="ops-app")
    db_session.add(api_key)
    policy = dict(DEFAULT_POLICY)
    policy["allowed_models"] = ["gpt-oss:120b-cloud"]
    db_session.add(TenantPolicy(tenant_id=tenant.id, policy_json=policy))
    db_session.add(
        TenantProviderConfig(
            id="pc_ollama",
            tenant_id=tenant.id,
            provider_type="ollama",
            display_name="Ollama",
            is_enabled=True,
            is_default=True,
            model_allowlist=["gpt-oss:120b-cloud"],
            config_json={"default_model": "gpt-oss:120b-cloud", "base_url": "http://localhost:11434/v1/"},
            encrypted_secret_blob="blob-ollama",
        )
    )
    db_session.commit()

    monkeypatch.setattr("app.services.provider_configs.secret_payload", lambda row: {})

    def _fake_chat_completions(
        self,
        *,
        model: str,
        messages: list[dict],
        max_tokens: int | None,
        temperature: float | None,
        runtime_config: dict | None = None,
    ) -> ProviderResponse:
        assert model == "gpt-oss:120b-cloud"
        assert runtime_config is not None
        return ProviderResponse(content="Ollama OK", raw={"ok": True}, prompt_tokens=3, completion_tokens=2)

    monkeypatch.setattr(OllamaProvider, "chat_completions", _fake_chat_completions)

    allowed = client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "ollama", "model": "gpt-oss:120b-cloud", "messages": [{"role": "user", "content": "hello"}]},
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["model"] == "gpt-oss:120b-cloud"

    blocked_policy = client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "ollama", "model": "gpt-4.1", "messages": [{"role": "user", "content": "hello"}]},
    )
    assert blocked_policy.status_code == 400, blocked_policy.text
    assert blocked_policy.json()["error"]["code"] == "POLICY_BLOCKED"
    assert blocked_policy.json().get("reason_code") == "invalid_model"

    blocked_provider = client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "ollama", "model": "gpt-oss:120b-cloud:alt", "messages": [{"role": "user", "content": "hello"}]},
    )
    assert blocked_provider.status_code in {400, 403}, blocked_provider.text

    latest = db_session.query(AuditEvent).filter(AuditEvent.tenant_id == tenant.id).order_by(AuditEvent.timestamp.desc()).first()
    assert latest is not None
    assert latest.provider == "ollama"


def test_ollama_runtime_settings_use_env_fallback_without_exposing_secret(monkeypatch):
    from app.core.config import settings
    from app.services.provider_configs import config_runtime_settings

    row = TenantProviderConfig(
        id="pc_ollama_env",
        tenant_id="tenant",
        provider_type="ollama",
        display_name="Ollama",
        is_enabled=True,
        is_default=False,
        model_allowlist=["gpt-oss:120b-cloud"],
        config_json={"default_model": "gpt-oss:120b-cloud"},
        encrypted_secret_blob=None,
    )
    monkeypatch.setattr(settings, "ollama_api_key", "env-ollama-key")
    monkeypatch.setattr(settings, "ollama_base_url", "http://localhost:11434/v1/")

    runtime = config_runtime_settings(row)
    assert runtime["api_key"] == "env-ollama-key"
    assert runtime["base_url"] == "http://localhost:11434/v1/"
    assert "secret" not in runtime
