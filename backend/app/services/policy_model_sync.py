from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy.orm import Session

from app.core.model_catalog import policy_model_options
from app.db.models import TenantPolicy, TenantPolicyVersion


def _canonical_allowed_models() -> list[str]:
    return policy_model_options(include_mock=True)


def should_reconcile_allowed_models(policy_json: dict[str, Any] | None) -> bool:
    if not isinstance(policy_json, dict):
        return False
    raw = policy_json.get("allowed_models")
    if not isinstance(raw, list) or not raw:
        return True
    normalized = [str(item or "").strip().lower() for item in raw if str(item or "").strip()]
    if not normalized:
        return True
    return all(item == "mock" for item in normalized)


def reconcile_policy_allowed_models(policy_json: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    if not isinstance(policy_json, dict):
        return policy_json, False
    if not should_reconcile_allowed_models(policy_json):
        return policy_json, False
    updated = deepcopy(policy_json)
    updated["allowed_models"] = _canonical_allowed_models()
    return updated, True


def reconcile_tenant_policy_rows(db: Session, *, tenant_id: str) -> bool:
    changed = False
    policy_row = db.get(TenantPolicy, tenant_id)
    if policy_row is None:
        return False

    updated_policy_json, policy_changed = reconcile_policy_allowed_models(policy_row.policy_json or {})
    if policy_changed:
        policy_row.policy_json = updated_policy_json
        db.add(policy_row)
        changed = True

    active_version_id = policy_row.active_version_id
    if active_version_id:
        version_row = db.get(TenantPolicyVersion, active_version_id)
        if version_row is not None:
            updated_version_json, version_changed = reconcile_policy_allowed_models(version_row.policy_json or {})
            if version_changed:
                version_row.policy_json = updated_version_json
                db.add(version_row)
                changed = True

    return changed


def backfill_all_tenant_policy_allowed_models(db: Session) -> dict[str, int]:
    updated_policy_rows = 0
    updated_policy_versions = 0

    for policy_row in db.query(TenantPolicy).all():
        updated_policy_json, policy_changed = reconcile_policy_allowed_models(policy_row.policy_json or {})
        if policy_changed:
            policy_row.policy_json = updated_policy_json
            db.add(policy_row)
            updated_policy_rows += 1

        active_version_id = policy_row.active_version_id
        if active_version_id:
            version_row = db.get(TenantPolicyVersion, active_version_id)
            if version_row is not None:
                updated_version_json, version_changed = reconcile_policy_allowed_models(version_row.policy_json or {})
                if version_changed:
                    version_row.policy_json = updated_version_json
                    db.add(version_row)
                    updated_policy_versions += 1

    db.commit()
    return {
        "updated_policy_rows": updated_policy_rows,
        "updated_active_policy_versions": updated_policy_versions,
    }
