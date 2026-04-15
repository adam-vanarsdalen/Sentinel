from __future__ import annotations

from app.db.models import Tenant, TenantPolicy, TenantPolicyVersion
from app.services.policy_model_sync import (
    reconcile_policy_allowed_models,
    reconcile_tenant_policy_rows,
    should_reconcile_allowed_models,
)


def test_reconcile_policy_allowed_models_replaces_mock_only():
    policy = {
        "allowed_models": ["mock"],
        "max_tokens_per_request": 512,
    }
    updated, changed = reconcile_policy_allowed_models(policy)
    assert changed is True
    assert "gpt-4.1" in (updated.get("allowed_models") or [])
    assert "mock" in (updated.get("allowed_models") or [])


def test_reconcile_policy_allowed_models_preserves_non_mock_allowlist():
    policy = {
        "allowed_models": ["gpt-4.1"],
        "max_tokens_per_request": 512,
    }
    updated, changed = reconcile_policy_allowed_models(policy)
    assert changed is False
    assert updated["allowed_models"] == ["gpt-4.1"]
    assert should_reconcile_allowed_models(updated) is False


def test_reconcile_tenant_policy_rows_updates_active_policy_version(db_session):
    tenant = Tenant(id="t_sync", name="Sync Tenant", slug="sync-tenant", status="active")
    db_session.add(tenant)
    version = TenantPolicyVersion(
        id="v_sync",
        tenant_id=tenant.id,
        policy_json={"allowed_models": ["mock"], "max_tokens_per_request": 512},
        source_template_id="general_default_policy_v1",
    )
    db_session.add(version)
    db_session.add(
        TenantPolicy(
            tenant_id=tenant.id,
            policy_json={"allowed_models": ["mock"], "max_tokens_per_request": 512},
            active_version_id=version.id,
        )
    )
    db_session.commit()

    changed = reconcile_tenant_policy_rows(db_session, tenant_id=tenant.id)
    assert changed is True
    db_session.commit()

    refreshed_policy = db_session.get(TenantPolicy, tenant.id)
    refreshed_version = db_session.get(TenantPolicyVersion, version.id)
    assert refreshed_policy is not None
    assert refreshed_version is not None
    assert "gpt-4.1" in (refreshed_policy.policy_json.get("allowed_models") or [])
    assert "gpt-4.1" in (refreshed_version.policy_json.get("allowed_models") or [])
