from __future__ import annotations

import copy
import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.model_catalog import normalize_model_allowlist as catalog_normalize_model_allowlist
from app.core.model_catalog import normalize_model_id, normalize_provider_id, provider_default_model_field
from app.core.presets import DEFAULT_PRESET_ID, get_demo_defaults, get_demo_seed, list_presets
from app.core.roles import canonical_role
from app.core.secrets import encrypt_json
from app.core.security import create_api_key_from_token, create_api_key_token, hash_password
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
from app.db.session import SessionLocal
from app.services.alerts import default_settings_json
from app.services.policy_model_sync import reconcile_policy_allowed_models
from app.services.policy import DEFAULT_POLICY, validate_policy_json
from app.services.policy_templates import get_policy_template


SEED_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "sentinel.demo.seed.v1")
LEGAL_COMPAT_ADMIN_EMAIL = "admin@demolaw.com"
LEGAL_COMPAT_API_KEY_NAME = "demo-contract-review"
GENERAL_COMPAT_API_KEY_NAME = "demo-operations-app"


def _getenv_bool(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).lower() in ("1", "true", "yes", "on")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _seed_uuid(*parts: str) -> str:
    return str(uuid.uuid5(SEED_NAMESPACE, "::".join(parts)))


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(dict(merged[key]), value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _hours_ago(value: Any) -> datetime:
    try:
        hours = float(value or 0)
    except (TypeError, ValueError):
        hours = 0.0
    return _utcnow() - timedelta(hours=hours)


def _ordered_preset_ids() -> list[str]:
    available = {str(preset.get("id") or "").strip().lower() for preset in list_presets()}
    preferred = [DEFAULT_PRESET_ID, "legal", "finance", "healthcare"]
    ordered = [preset_id for preset_id in preferred if preset_id in available]
    ordered.extend(sorted(preset_id for preset_id in available if preset_id and preset_id not in ordered))
    return ordered


def _find_tenant(db: Session, *, tenant_id: str, slug: str, name: str) -> Tenant | None:
    tenant = db.get(Tenant, tenant_id)
    if tenant:
        return tenant
    tenant = db.query(Tenant).filter(Tenant.slug == slug).one_or_none()
    if tenant:
        return tenant
    return db.query(Tenant).filter(Tenant.name == name).one_or_none()


def _ensure_super_admin(db: Session, *, sync_passwords: bool) -> bool:
    changed = False
    super_email = os.getenv("DEMO_SUPER_ADMIN_EMAIL", settings.demo_super_admin_email).lower()
    super_pwd = os.getenv("DEMO_SUPER_ADMIN_PASSWORD", settings.demo_super_admin_password)
    user = db.query(User).filter(User.email == super_email).one_or_none()
    if not user:
        user = User(
            id=_seed_uuid("user", "super-admin"),
            tenant_id=None,
            email=super_email,
            password_hash=hash_password(super_pwd),
            role="super_admin",
            is_active=True,
        )
        db.add(user)
        return True

    if user.tenant_id is not None:
        user.tenant_id = None
        changed = True
    if user.role != "super_admin":
        user.role = "super_admin"
        changed = True
    if not user.is_active:
        user.is_active = True
        changed = True
    if sync_passwords:
        user.password_hash = hash_password(super_pwd)
        changed = True
    db.add(user)
    return changed


def _user_specs_for_preset(preset_id: str, demo_seed: dict[str, Any]) -> list[dict[str, str]]:
    users = [dict(item) for item in (demo_seed.get("users") or []) if isinstance(item, dict)]
    existing_emails = {str(item.get("email") or "").strip().lower() for item in users}

    if preset_id == DEFAULT_PRESET_ID:
        default_admin_email = os.getenv("DEMO_TENANT_ADMIN_EMAIL", settings.demo_tenant_admin_email).lower()
        if default_admin_email and default_admin_email not in existing_emails:
            users.insert(0, {"email": default_admin_email, "role": "org_admin"})
            existing_emails.add(default_admin_email)

    demo_defaults = get_demo_defaults(preset_id)
    manifest_admin_email = str(demo_defaults.get("admin_email") or "").strip().lower()
    if manifest_admin_email and manifest_admin_email not in existing_emails:
        users.insert(0, {"email": manifest_admin_email, "role": "org_admin"})
        existing_emails.add(manifest_admin_email)

    if preset_id == "legal" and LEGAL_COMPAT_ADMIN_EMAIL not in existing_emails:
        users.append({"email": LEGAL_COMPAT_ADMIN_EMAIL, "role": "org_admin"})

    return users


def _api_key_specs_for_preset(preset_id: str, demo_seed: dict[str, Any]) -> list[dict[str, str]]:
    keys = [dict(item) for item in (demo_seed.get("api_keys") or []) if isinstance(item, dict)]
    key_names = {str(item.get("name") or "").strip() for item in keys}

    if preset_id == DEFAULT_PRESET_ID and GENERAL_COMPAT_API_KEY_NAME not in key_names:
        keys.append(
            {
                "name": GENERAL_COMPAT_API_KEY_NAME,
                "token": "sk_genops99_demo_seed_general_compat_operations_app",
            }
        )

    if preset_id == "legal" and LEGAL_COMPAT_API_KEY_NAME not in key_names:
        keys.append(
            {
                "name": LEGAL_COMPAT_API_KEY_NAME,
                "token": "sk_lglcompat_demo_seed_legal_compat_contract_review",
            }
        )

    return keys


def _build_policy_json(spec: dict[str, Any]) -> dict[str, Any]:
    template_id = str(spec.get("template_id") or "").strip()
    template = get_policy_template(template_id) if template_id else None
    policy_json = copy.deepcopy(template["policy_json"]) if template else copy.deepcopy(DEFAULT_POLICY)
    overrides = spec.get("overrides") if isinstance(spec.get("overrides"), dict) else {}
    if overrides:
        policy_json = _deep_merge(policy_json, overrides)
    policy_json, _ = reconcile_policy_allowed_models(policy_json)
    validate_policy_json(policy_json)
    return policy_json


def _upsert_tenant(
    db: Session,
    *,
    preset_id: str,
    demo_seed: dict[str, Any],
    created_at: datetime,
) -> tuple[Tenant, bool]:
    tenant_meta = demo_seed.get("tenant") if isinstance(demo_seed.get("tenant"), dict) else {}
    name = str((tenant_meta or {}).get("name") or f"{preset_id.title()} Demo").strip()
    slug = str((tenant_meta or {}).get("slug") or name.lower().replace(" ", "-")).strip()
    status = str((tenant_meta or {}).get("status") or "active").strip() or "active"
    profile = str((tenant_meta or {}).get("profile") or preset_id.title()).strip()
    summary = str((tenant_meta or {}).get("summary") or "").strip()
    tenant_id = _seed_uuid("tenant", preset_id)
    tenant = _find_tenant(db, tenant_id=tenant_id, slug=slug, name=name)
    changed = False

    metadata = {
        "preset_id": preset_id,
        "is_demo": True,
        "demo_profile": profile,
        "demo_summary": summary,
        "default_demo": preset_id == DEFAULT_PRESET_ID,
    }

    if not tenant:
        tenant = Tenant(
            id=tenant_id,
            name=name,
            slug=slug,
            status=status,
            created_at=created_at,
            updated_at=created_at,
            settings_json=metadata,
        )
        db.add(tenant)
        return tenant, True

    if tenant.name != name:
        tenant.name = name
        changed = True
    if tenant.slug != slug:
        tenant.slug = slug
        changed = True
    if tenant.status != status:
        tenant.status = status
        changed = True
    if tenant.created_at != created_at:
        tenant.created_at = created_at
        changed = True
    if tenant.updated_at != created_at:
        tenant.updated_at = created_at
        changed = True
    if (tenant.settings_json or {}) != metadata:
        tenant.settings_json = metadata
        changed = True
    db.add(tenant)
    return tenant, changed


def _upsert_users(
    db: Session,
    *,
    tenant: Tenant,
    preset_id: str,
    demo_seed: dict[str, Any],
    sync_passwords: bool,
) -> tuple[dict[str, User], bool]:
    changed = False
    tenant_pwd = os.getenv("DEMO_TENANT_ADMIN_PASSWORD", settings.demo_tenant_admin_password)
    users_by_email: dict[str, User] = {}

    for index, spec in enumerate(_user_specs_for_preset(preset_id, demo_seed)):
        email = str(spec.get("email") or "").strip().lower()
        if not email:
            continue
        role = canonical_role(spec.get("role") or "org_admin")
        user = db.query(User).filter(User.email == email).one_or_none()
        if not user:
            user = User(
                id=_seed_uuid("user", preset_id, str(index), email),
                tenant_id=tenant.id,
                email=email,
                password_hash=hash_password(tenant_pwd),
                role=role,
                is_active=True,
            )
            db.add(user)
            changed = True
        else:
            if user.tenant_id != tenant.id:
                user.tenant_id = tenant.id
                changed = True
            if canonical_role(user.role) != role:
                user.role = role
                changed = True
            if not user.is_active:
                user.is_active = True
                changed = True
            if sync_passwords:
                user.password_hash = hash_password(tenant_pwd)
                changed = True
            db.add(user)
        users_by_email[email] = user

    return users_by_email, changed


def _upsert_api_keys(
    db: Session,
    *,
    tenant: Tenant,
    preset_id: str,
    demo_seed: dict[str, Any],
) -> tuple[dict[str, ApiKey], bool]:
    changed = False
    api_keys_by_name: dict[str, ApiKey] = {}
    env_demo_token = os.getenv("DEMO_APP_API_KEY", "").strip()

    for spec in _api_key_specs_for_preset(preset_id, demo_seed):
        name = str(spec.get("name") or "").strip()
        if not name:
            continue
        key_id = _seed_uuid("api-key", preset_id, name)
        row = db.get(ApiKey, key_id)
        if row is None:
            row = db.query(ApiKey).filter(ApiKey.tenant_id == tenant.id, ApiKey.name == name).one_or_none()

        if row is None:
            token = str(spec.get("token") or "").strip()
            if preset_id == DEFAULT_PRESET_ID and name == str((demo_seed.get("api_keys") or [{}])[0].get("name") or "") and env_demo_token:
                token = env_demo_token
            if token:
                row = create_api_key_from_token(tenant_id=tenant.id, name=name, token=token)
            else:
                _, row = create_api_key_token(tenant_id=tenant.id, name=name)
            row.id = key_id
            row.is_active = True
            db.add(row)
            changed = True
        else:
            if row.tenant_id != tenant.id:
                row.tenant_id = tenant.id
                changed = True
            if row.name != name:
                row.name = name
                changed = True
            if not row.is_active:
                row.is_active = True
                row.revoked_at = None
                changed = True
            db.add(row)

        api_keys_by_name[name] = row

    return api_keys_by_name, changed


def _upsert_provider_configs(
    db: Session,
    *,
    tenant: Tenant,
    preset_id: str,
    demo_seed: dict[str, Any],
) -> bool:
    changed = False
    providers = [dict(item) for item in (demo_seed.get("providers") or []) if isinstance(item, dict)]
    for spec in providers:
        try:
            provider_type = normalize_provider_id(spec.get("provider_type"), allow_mock=False)
        except ValueError:
            continue
        normalized_allowlist = catalog_normalize_model_allowlist(provider_type, list(spec.get("model_allowlist") or []))
        normalized_config_json = dict(spec.get("config_json") or {})
        default_field = provider_default_model_field(provider_type)
        if default_field in normalized_config_json:
            normalized_config_json[default_field] = normalize_model_id(
                provider_type,
                normalized_config_json.get(default_field),
                allow_empty=True,
            )

        provider_id = _seed_uuid("provider", preset_id, provider_type)
        row = db.get(TenantProviderConfig, provider_id)
        if row is None:
            row = (
                db.query(TenantProviderConfig)
                .filter(TenantProviderConfig.tenant_id == tenant.id, TenantProviderConfig.provider_type == provider_type)
                .one_or_none()
            )
        now = _utcnow()
        if row is None:
            row = TenantProviderConfig(
                id=provider_id,
                tenant_id=tenant.id,
                provider_type=provider_type,
                display_name=str(spec.get("display_name") or provider_type),
                is_enabled=bool(spec.get("is_enabled", True)),
                is_default=bool(spec.get("is_default", False)),
                model_allowlist=normalized_allowlist,
                config_json=normalized_config_json,
                encrypted_secret_blob=encrypt_json(spec.get("secret_json") if isinstance(spec.get("secret_json"), dict) else {}),
                created_at=now,
                updated_at=now,
            )
            db.add(row)
            changed = True
            continue

        row_changed = False
        updates = {
            "tenant_id": tenant.id,
            "provider_type": provider_type,
            "display_name": str(spec.get("display_name") or provider_type),
            "is_enabled": bool(spec.get("is_enabled", True)),
            "is_default": bool(spec.get("is_default", False)),
            "model_allowlist": normalized_allowlist,
            "config_json": normalized_config_json,
            "encrypted_secret_blob": encrypt_json(spec.get("secret_json") if isinstance(spec.get("secret_json"), dict) else {}),
        }
        for field, value in updates.items():
            if getattr(row, field) != value:
                setattr(row, field, value)
                row_changed = True
                changed = True
        if row_changed:
            row.updated_at = now
        db.add(row)
    return changed


def _upsert_policy_state(
    db: Session,
    *,
    tenant: Tenant,
    preset_id: str,
    demo_seed: dict[str, Any],
    users_by_email: dict[str, User],
) -> bool:
    changed = False
    policy_specs = [dict(item) for item in (demo_seed.get("policy_versions") or []) if isinstance(item, dict)]
    active_version_id: str | None = None
    active_policy_json: dict[str, Any] | None = None
    org_admin_user_id = next((user.id for user in users_by_email.values() if canonical_role(user.role) == "org_admin"), None)

    for index, spec in enumerate(policy_specs):
        version_id = _seed_uuid("policy-version", preset_id, str(index))
        policy_json = _build_policy_json(spec)
        row = db.get(TenantPolicyVersion, version_id)
        created_at = _utcnow() - timedelta(days=max(len(policy_specs) - index, 1))
        if row is None:
            row = TenantPolicyVersion(
                id=version_id,
                tenant_id=tenant.id,
                policy_json=policy_json,
                created_by_user_id=org_admin_user_id,
                change_note=str(spec.get("change_note") or "").strip() or None,
                source_template_id=str(spec.get("template_id") or "").strip() or None,
                source_version_id=None,
                created_at=created_at,
            )
            db.add(row)
            changed = True
        else:
            if row.tenant_id != tenant.id:
                row.tenant_id = tenant.id
                changed = True
            if row.policy_json != policy_json:
                row.policy_json = policy_json
                changed = True
            if row.created_by_user_id != org_admin_user_id:
                row.created_by_user_id = org_admin_user_id
                changed = True
            change_note = str(spec.get("change_note") or "").strip() or None
            if row.change_note != change_note:
                row.change_note = change_note
                changed = True
            source_template_id = str(spec.get("template_id") or "").strip() or None
            if row.source_template_id != source_template_id:
                row.source_template_id = source_template_id
                changed = True
            if row.created_at != created_at:
                row.created_at = created_at
                changed = True
            db.add(row)

        if bool(spec.get("active")):
            active_version_id = row.id
            active_policy_json = policy_json

    if active_policy_json is None:
        active_policy_json = _build_policy_json({})

    # Persist policy versions before setting tenant_policies.active_version_id.
    db.flush()
    policy_row = db.get(TenantPolicy, tenant.id)
    if policy_row is None:
        policy_row = TenantPolicy(
            tenant_id=tenant.id,
            policy_json=active_policy_json,
            updated_by_user_id=org_admin_user_id,
            active_version_id=active_version_id,
            updated_at=_utcnow(),
        )
        db.add(policy_row)
        return True

    if policy_row.policy_json != active_policy_json:
        policy_row.policy_json = active_policy_json
        changed = True
    if policy_row.updated_by_user_id != org_admin_user_id:
        policy_row.updated_by_user_id = org_admin_user_id
        changed = True
    if policy_row.active_version_id != active_version_id:
        policy_row.active_version_id = active_version_id
        changed = True
    if changed:
        policy_row.updated_at = _utcnow()
    db.add(policy_row)
    return changed


def _upsert_settings(
    db: Session,
    *,
    tenant: Tenant,
    preset_id: str,
    demo_seed: dict[str, Any],
    users_by_email: dict[str, User],
) -> bool:
    base = default_settings_json()
    incoming = demo_seed.get("settings") if isinstance(demo_seed.get("settings"), dict) else {}
    settings_json = _deep_merge(base, incoming or {})
    row = db.get(TenantSettings, tenant.id)
    updated_by_user_id = next((user.id for user in users_by_email.values() if canonical_role(user.role) in {"org_admin", "compliance_admin"}), None)
    now = _utcnow()
    if row is None:
        row = TenantSettings(
            tenant_id=tenant.id,
            settings_json=settings_json,
            updated_by_user_id=updated_by_user_id,
            updated_at=now,
        )
        db.add(row)
        return True

    changed = False
    if row.settings_json != settings_json:
        row.settings_json = settings_json
        changed = True
    if row.updated_by_user_id != updated_by_user_id:
        row.updated_by_user_id = updated_by_user_id
        changed = True
    if changed:
        row.updated_at = now
    db.add(row)
    return changed


def _upsert_audit_events(
    db: Session,
    *,
    tenant: Tenant,
    preset_id: str,
    demo_seed: dict[str, Any],
    users_by_email: dict[str, User],
    api_keys_by_name: dict[str, ApiKey],
) -> bool:
    changed = False
    for spec in [dict(item) for item in (demo_seed.get("audit_events") or []) if isinstance(item, dict)]:
        slug = str(spec.get("id") or spec.get("request_id") or uuid.uuid4()).strip()
        event_id = _seed_uuid("audit-event", preset_id, slug)
        row = db.get(AuditEvent, event_id)
        provider_raw = str(spec.get("provider") or "").strip() or None
        model_raw = str(spec.get("model") or "").strip() or None
        provider = None
        model = None
        if provider_raw:
            provider = normalize_provider_id(provider_raw, allow_mock=True)
            if model_raw:
                model = normalize_model_id(provider, model_raw, allow_empty=False)
        payload = {
            "tenant_id": tenant.id,
            "api_key_id": api_keys_by_name.get(str(spec.get("api_key_name") or "").strip(), None).id
            if api_keys_by_name.get(str(spec.get("api_key_name") or "").strip(), None)
            else None,
            "user_id": users_by_email.get(str(spec.get("user_email") or "").strip().lower(), None).id
            if users_by_email.get(str(spec.get("user_email") or "").strip().lower(), None)
            else None,
            "matter_id": str(spec.get("matter_id") or "").strip() or None,
            "practice_group": str(spec.get("practice_group") or "").strip() or None,
            "client_name": str(spec.get("client_name") or "").strip() or None,
            "request_id": str(spec.get("request_id") or slug).strip(),
            "timestamp": _hours_ago(spec.get("hours_ago")),
            "action_type": str(spec.get("action_type") or "LLM_REQUEST").strip(),
            "outcome": str(spec.get("outcome") or "success").strip(),
            "reason": str(spec.get("reason") or "").strip() or None,
            "model": model,
            "provider": provider,
            "redacted_prompt": str(spec.get("redacted_prompt") or "").strip() or None,
            "redacted_response": str(spec.get("redacted_response") or "").strip() or None,
            "phi_score": int(spec["phi_score"]) if spec.get("phi_score") is not None else None,
            "risk_flags": list(spec.get("risk_flags") or []),
            "severity": str(spec.get("severity") or "").strip() or None,
            "tokens_prompt": int(spec["tokens_prompt"]) if spec.get("tokens_prompt") is not None else None,
            "tokens_completion": int(spec["tokens_completion"]) if spec.get("tokens_completion") is not None else None,
            "cost_usd": Decimal(str(spec["cost_usd"])) if spec.get("cost_usd") is not None else None,
            "event_data": dict(spec.get("event_data") or {}),
        }
        if row is None:
            row = AuditEvent(id=event_id, **payload)
            db.add(row)
            changed = True
            continue

        for field, value in payload.items():
            if getattr(row, field) != value:
                setattr(row, field, value)
                changed = True
        db.add(row)
    return changed


def _upsert_eval_suite(
    db: Session,
    *,
    tenant: Tenant,
    preset_id: str,
    demo_seed: dict[str, Any],
) -> bool:
    changed = False
    case_rows: dict[str, EvalTestCase] = {}
    for index, spec in enumerate([dict(item) for item in (demo_seed.get("eval_cases") or []) if isinstance(item, dict)]):
        case_name = str(spec.get("name") or f"Case {index + 1}").strip()
        case_id = _seed_uuid("eval-case", preset_id, case_name)
        row = db.get(EvalTestCase, case_id)
        payload = {
            "tenant_id": tenant.id,
            "name": case_name,
            "category": str(spec.get("category") or "benign").strip(),
            "input_messages": list(spec.get("input_messages") or []),
            "expected_flags": list(spec.get("expected_flags") or []),
        }
        if row is None:
            row = EvalTestCase(id=case_id, **payload)
            db.add(row)
            changed = True
        else:
            for field, value in payload.items():
                if getattr(row, field) != value:
                    setattr(row, field, value)
                    changed = True
            db.add(row)
        case_rows[case_name] = row

    run_spec = demo_seed.get("eval_run") if isinstance(demo_seed.get("eval_run"), dict) else {}
    run_id = _seed_uuid("eval-run", preset_id, "baseline")
    run = db.get(EvalRun, run_id)
    started_at = _hours_ago(run_spec.get("hours_ago"))
    finished_at = started_at + timedelta(minutes=6) if str(run_spec.get("status") or "finished").strip() == "finished" else None
    result_specs = [dict(item) for item in (run_spec.get("results") or []) if isinstance(item, dict)]
    summary = run_spec.get("summary") if isinstance(run_spec.get("summary"), dict) else {}
    if not summary:
        total = len(result_specs)
        passed = sum(1 for item in result_specs if bool(item.get("passed")))
        summary = {"total": total, "passed": passed, "failed": total - passed}

    run_provider = normalize_provider_id(run_spec.get("provider") or "mock", allow_mock=True)
    run_model = normalize_model_id(run_provider, run_spec.get("model") or "mock", allow_empty=False)
    run_payload = {
        "tenant_id": tenant.id,
        "provider": run_provider,
        "model": run_model,
        "status": str(run_spec.get("status") or "finished").strip(),
        "started_at": started_at,
        "finished_at": finished_at,
        "summary": dict(summary),
    }
    if run is None:
        run = EvalRun(id=run_id, **run_payload)
        db.add(run)
        changed = True
    else:
        for field, value in run_payload.items():
            if getattr(run, field) != value:
                setattr(run, field, value)
                changed = True
        db.add(run)

    for spec in result_specs:
        case_name = str(spec.get("case_name") or "").strip()
        case = case_rows.get(case_name)
        if case is None:
            continue
        result_id = _seed_uuid("eval-result", preset_id, case_name)
        row = db.get(EvalResult, result_id)
        payload = {
            "tenant_id": tenant.id,
            "run_id": run.id,
            "test_case_id": case.id,
            "passed": bool(spec.get("passed")),
            "observed_flags": list(spec.get("observed_flags") or []),
            "phi_score": int(spec["phi_score"]) if spec.get("phi_score") is not None else None,
            "risk_severity": str(spec.get("risk_severity") or "").strip() or None,
            "details": dict(spec.get("details") or {}),
        }
        if row is None:
            row = EvalResult(id=result_id, **payload)
            db.add(row)
            changed = True
            continue
        for field, value in payload.items():
            if getattr(row, field) != value:
                setattr(row, field, value)
                changed = True
        db.add(row)

    return changed


def _seed_preset_demo(db: Session, *, preset_id: str, order_index: int, sync_passwords: bool) -> bool:
    demo_seed = get_demo_seed(preset_id)
    if not demo_seed:
        return False

    created_at = _utcnow() - timedelta(minutes=order_index)
    tenant, changed = _upsert_tenant(db, preset_id=preset_id, demo_seed=demo_seed, created_at=created_at)
    # Ensure tenant rows exist before child rows that reference tenant_id directly.
    db.flush()
    users_by_email, users_changed = _upsert_users(
        db,
        tenant=tenant,
        preset_id=preset_id,
        demo_seed=demo_seed,
        sync_passwords=sync_passwords,
    )
    api_keys_by_name, keys_changed = _upsert_api_keys(db, tenant=tenant, preset_id=preset_id, demo_seed=demo_seed)
    # Flush parent entities before children that reference them by foreign keys.
    db.flush()
    providers_changed = _upsert_provider_configs(db, tenant=tenant, preset_id=preset_id, demo_seed=demo_seed)
    policies_changed = _upsert_policy_state(
        db,
        tenant=tenant,
        preset_id=preset_id,
        demo_seed=demo_seed,
        users_by_email=users_by_email,
    )
    settings_changed = _upsert_settings(
        db,
        tenant=tenant,
        preset_id=preset_id,
        demo_seed=demo_seed,
        users_by_email=users_by_email,
    )
    db.flush()
    events_changed = _upsert_audit_events(
        db,
        tenant=tenant,
        preset_id=preset_id,
        demo_seed=demo_seed,
        users_by_email=users_by_email,
        api_keys_by_name=api_keys_by_name,
    )
    db.flush()
    evals_changed = _upsert_eval_suite(db, tenant=tenant, preset_id=preset_id, demo_seed=demo_seed)
    return any([changed, users_changed, keys_changed, providers_changed, policies_changed, settings_changed, events_changed, evals_changed])


def main() -> None:
    if not (_getenv_bool("SEED_DEMO", "0") or settings.seed_demo):
        return

    db: Session = SessionLocal()
    try:
        changed = False
        sync_passwords = _getenv_bool("DEMO_PASSWORD_SYNC", "0")
        changed = _ensure_super_admin(db, sync_passwords=sync_passwords) or changed

        for index, preset_id in enumerate(_ordered_preset_ids(), start=1):
            changed = _seed_preset_demo(db, preset_id=preset_id, order_index=index, sync_passwords=sync_passwords) or changed

        if changed:
            db.commit()
        else:
            print("Demo data already seeded")
    finally:
        db.close()


if __name__ == "__main__":
    main()
