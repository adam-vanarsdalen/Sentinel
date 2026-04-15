from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.model_catalog import PROVIDER_TYPES, normalize_model_allowlist, normalize_model_id
from app.core.security import hash_password
from app.db.models import Tenant, User


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


def test_catalog_provider_types_are_curated():
    assert PROVIDER_TYPES == ("openai", "anthropic", "azure_openai")


def test_model_allowlist_normalization_is_provider_aware():
    models = normalize_model_allowlist("openai", ["gpt-4.1", " gpt-4.1 ", "Gpt-4.1-mini", "", "gpt-4.1-mini"])
    assert models == ["gpt-4.1", "gpt-4.1-mini"]

    azure_models = normalize_model_allowlist("azure_openai", ["care-gpt-4o-mini", "custom-deployment", " custom-deployment "])
    assert azure_models == ["care-gpt-4o-mini", "custom-deployment"]


def test_unknown_model_rejected_for_fixed_catalog_providers():
    try:
        normalize_model_id("openai", "made-up-model", allow_empty=False)
    except ValueError as exc:
        assert "Unknown model" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unsupported model")


def test_provider_catalog_endpoint_returns_catalog_for_org_admin(client: TestClient, db_session: Session):
    tenant = _mk_tenant(db_session, "t-model-catalog", "Model Catalog Tenant")
    _mk_user(db_session, "u-model-catalog", tenant.id, "admin@catalog.example.com", "pw12345!", "org_admin")
    jwt = _login(client, "admin@catalog.example.com", "pw12345!")

    response = client.get("/admin/provider-configs/catalog", headers={"Authorization": f"Bearer {jwt}"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert "providers" in body
    provider_ids = {item["id"] for item in body["providers"]}
    assert provider_ids == {"openai", "anthropic", "azure_openai"}
    openai_models = [item["id"] for item in next(item for item in body["providers"] if item["id"] == "openai")["models"]]
    assert "gpt-4.1-mini" in openai_models
    assert "gpt-4.1" in openai_models


def test_eval_run_rejects_unknown_model(client: TestClient, db_session: Session):
    tenant = _mk_tenant(db_session, "t-eval-catalog", "Eval Catalog Tenant")
    _mk_user(db_session, "u-eval-catalog", tenant.id, "operator@catalog.example.com", "pw12345!", "operator")
    jwt = _login(client, "operator@catalog.example.com", "pw12345!")

    response = client.post(
        "/admin/evals/run",
        headers={"Authorization": f"Bearer {jwt}"},
        json={"provider": "openai", "model": "made-up-model"},
    )
    assert response.status_code == 400
    assert "Unknown model" in response.text
