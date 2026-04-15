from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from fastapi import Depends
from pydantic import BaseModel

from app.api.deps import DbDep, require_role
from app.core.presets import get_default_policy_template_id, get_terminology
from app.db.models import TenantPolicy, TenantPolicyVersion, User
from app.services.audit_log import write_admin_audit_event
from app.services.policy import (
    DEFAULT_POLICY,
    apply_required_system_prefix,
    enforce_preflight,
    evaluate_output_rules,
    should_block_prompt_injection,
    validate_policy_json,
)
from app.services.policy_templates import get_policy_template, list_policy_templates
from app.services.policy_model_sync import reconcile_policy_allowed_models
from app.services.phi import confidentiality_exposure_level, scan_phi
from app.services.security_flags import detect_security_signals

router = APIRouter()


class PolicyResponse(BaseModel):
    tenant_id: str
    policy_json: dict
    updated_at: str
    updated_by_user_id: str | None
    active_version_id: str | None


class PolicyUpdateRequest(BaseModel):
    policy_json: dict
    change_note: str | None = None
    source_template_id: str | None = None


class PolicyVersionResponse(BaseModel):
    id: str
    tenant_id: str
    created_at: str
    created_by_user_id: str | None
    created_by_email: str | None = None
    change_note: str | None = None
    summary: str
    active: bool
    source_template_id: str | None = None
    source_version_id: str | None = None
    policy_json: dict


class PolicyDryRunRequest(BaseModel):
    policy_json: dict
    model: str
    messages: list[dict]
    response_text: str | None = None
    metadata: dict | None = None


PolicyReader = Annotated[User, Depends(require_role("super_admin", "org_admin", "compliance_admin", "operator", "reviewer", "auditor"))]
PolicyWriter = Annotated[User, Depends(require_role("super_admin", "org_admin", "compliance_admin"))]

PolicyTemplateReader = Annotated[User, Depends(require_role("super_admin", "org_admin", "compliance_admin", "operator", "reviewer", "auditor"))]


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _version_summary(version: TenantPolicyVersion) -> str:
    if version.change_note:
        return version.change_note
    if version.source_version_id:
        return "Rollback to a prior policy version"
    if version.source_template_id:
        return f"Published from template {version.source_template_id}"
    return "Policy published"


def _serialize_policy_version(
    version: TenantPolicyVersion, *, active_version_id: str | None, created_by_email: str | None = None
) -> PolicyVersionResponse:
    return PolicyVersionResponse(
        id=version.id,
        tenant_id=version.tenant_id,
        created_at=version.created_at.isoformat(),
        created_by_user_id=version.created_by_user_id,
        created_by_email=created_by_email,
        change_note=version.change_note,
        summary=_version_summary(version),
        active=version.id == active_version_id,
        source_template_id=version.source_template_id,
        source_version_id=version.source_version_id,
        policy_json=version.policy_json,
    )


def _list_policy_versions_with_users(db, *, tenant_id: str, limit: int = 20) -> tuple[str | None, list[tuple[TenantPolicyVersion, str | None]]]:
    policy = db.get(TenantPolicy, tenant_id)
    active_version_id = policy.active_version_id if policy else None
    rows = (
        db.query(TenantPolicyVersion, User.email)
        .outerjoin(User, User.id == TenantPolicyVersion.created_by_user_id)
        .filter(TenantPolicyVersion.tenant_id == tenant_id)
        .order_by(TenantPolicyVersion.created_at.desc(), TenantPolicyVersion.id.desc())
        .limit(limit)
        .all()
    )
    return active_version_id, rows


def _create_policy_version(
    db,
    *,
    tenant_id: str,
    policy_json: dict,
    user_id: str | None,
    change_note: str | None = None,
    source_template_id: str | None = None,
    source_version_id: str | None = None,
) -> tuple[TenantPolicy, TenantPolicyVersion]:
    policy_json, _ = reconcile_policy_allowed_models(policy_json)
    policy = db.get(TenantPolicy, tenant_id)
    now = _now_utc()
    if not policy:
        policy = TenantPolicy(
            tenant_id=tenant_id,
            policy_json=policy_json,
            updated_by_user_id=user_id,
            updated_at=now,
        )
        db.add(policy)
        db.flush()
    else:
        policy.policy_json = policy_json
        policy.updated_by_user_id = user_id
        policy.updated_at = now
        db.add(policy)
        db.flush()

    version = TenantPolicyVersion(
        tenant_id=tenant_id,
        policy_json=policy_json,
        created_by_user_id=user_id,
        change_note=(change_note or None),
        source_template_id=(source_template_id or None),
        source_version_id=(source_version_id or None),
    )
    db.add(version)
    db.flush()

    policy.active_version_id = version.id
    db.add(policy)
    db.commit()
    db.refresh(policy)
    db.refresh(version)
    return policy, version


def _ensure_current_policy(db, *, tenant_id: str, user: User) -> TenantPolicy:
    policy = db.get(TenantPolicy, tenant_id)
    if policy:
        if policy.active_version_id and db.get(TenantPolicyVersion, policy.active_version_id):
            return policy
        _, version = _create_policy_version(
            db,
            tenant_id=tenant_id,
            policy_json=policy.policy_json,
            user_id=policy.updated_by_user_id or user.id,
            change_note="Backfilled active policy snapshot",
        )
        policy.active_version_id = version.id
        return policy

    default_template_id = get_default_policy_template_id()
    tpl = get_policy_template(default_template_id)
    policy_json = tpl["policy_json"] if tpl else DEFAULT_POLICY
    policy, version = _create_policy_version(
        db,
        tenant_id=tenant_id,
        policy_json=policy_json,
        user_id=user.id,
        change_note="Initialized from default preset template",
        source_template_id=default_template_id,
    )
    write_admin_audit_event(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        action_type="POLICY_VERSION_CREATED",
        outcome="success",
        reason="Policy initialized",
        event_data={"actor_role": user.role, "policy_template_id": default_template_id, "version_id": version.id},
    )
    write_admin_audit_event(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        action_type="POLICY_VERSION_ACTIVATED",
        outcome="success",
        reason="Policy initialized",
        event_data={"actor_role": user.role, "policy_template_id": default_template_id, "version_id": version.id},
    )
    write_admin_audit_event(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        action_type="ADMIN_CHANGE",
        outcome="success",
        reason="Policy initialized",
        event_data={"actor_role": user.role, "policy_template_id": default_template_id, "version_id": version.id},
    )
    return policy


@router.get("/templates", response_model=list[dict])
def list_templates(user: PolicyTemplateReader) -> list[dict]:
    return [{"id": t["id"], "name": t["name"], "description": t["description"]} for t in list_policy_templates()]


@router.get("/templates/{template_id}", response_model=dict)
def get_template(template_id: str, user: PolicyTemplateReader) -> dict:
    t = get_policy_template(template_id)
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return t


@router.get("/current", response_model=PolicyResponse)
def get_current_policy(db: DbDep, user: PolicyReader) -> PolicyResponse:
    tenant_id = user.effective_tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")
    return _ensure_current_policy(db, tenant_id=tenant_id, user=user).to_response()


@router.put("/current", response_model=PolicyResponse)
def update_policy(req: PolicyUpdateRequest, db: DbDep, user: PolicyWriter) -> PolicyResponse:
    tenant_id = user.effective_tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")

    reconciled_policy_json, _ = reconcile_policy_allowed_models(req.policy_json)
    validate_policy_json(reconciled_policy_json)
    policy, version = _create_policy_version(
        db,
        tenant_id=tenant_id,
        policy_json=reconciled_policy_json,
        user_id=user.id,
        change_note=(req.change_note or None),
        source_template_id=(req.source_template_id or None),
    )

    write_admin_audit_event(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        action_type="POLICY_VERSION_CREATED",
        outcome="success",
        reason="Policy version created",
        event_data={
            "version_id": version.id,
            "change_note": req.change_note,
            "source_template_id": req.source_template_id,
        },
    )
    write_admin_audit_event(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        action_type="POLICY_VERSION_ACTIVATED",
        outcome="success",
        reason="Policy version activated",
        event_data={
            "version_id": version.id,
            "change_note": req.change_note,
            "source_template_id": req.source_template_id,
        },
    )

    write_admin_audit_event(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        action_type="ADMIN_CHANGE",
        outcome="success",
        reason="Policy updated",
        event_data={"version_id": version.id, "change_note": req.change_note, "source_template_id": req.source_template_id},
    )
    return policy.to_response()


@router.post("/test", response_model=dict)
def test_policy(req: PolicyUpdateRequest, user: Annotated[User, Depends(require_role("super_admin", "org_admin", "compliance_admin", "operator"))]) -> dict:
    reconciled_policy_json, _ = reconcile_policy_allowed_models(req.policy_json)
    validate_policy_json(reconciled_policy_json)
    return {"ok": True}


@router.post("/dry-run", response_model=dict)
def dry_run(req: PolicyDryRunRequest, user: Annotated[User, Depends(require_role("super_admin", "org_admin", "compliance_admin", "operator"))]) -> dict:
    policy_json, _ = reconcile_policy_allowed_models(req.policy_json)
    validate_policy_json(policy_json)
    messages = req.messages or []
    prompt_text = "\n".join([m.get("content", "") for m in messages])
    messages = apply_required_system_prefix(policy=policy_json, messages=messages)

    flags: list[str] = []
    outcome = "ALLOW"
    block_reason = None
    try:
        enforce_preflight(
            policy=policy_json, model=req.model, prompt_text=prompt_text, max_tokens=None, metadata=req.metadata
        )
    except Exception as e:
        outcome = "BLOCK"
        block_reason = getattr(e, "detail", str(e))[:500]

    sec = detect_security_signals(prompt_text)
    phi = scan_phi(prompt_text)
    phi_cfg = policy_json.get("phi") or {}
    if isinstance(phi_cfg, dict) and phi_cfg.get("flag_on_any_match") is True and (phi.matches or []):
        flags.append("CONFIDENTIAL_DATA_DETECTED")
    if outcome != "BLOCK" and should_block_prompt_injection(policy=policy_json, signals=sec):
        outcome = "BLOCK"
        block_reason = "Prompt injection suspicion exceeded policy threshold"
    if outcome != "BLOCK" and isinstance(phi_cfg, dict) and phi_cfg.get("enabled", True):
        threshold = int(phi_cfg.get("threshold_score", 80))
        if phi.score >= threshold and phi_cfg.get("action", "flag") == "block":
            outcome = "BLOCK"
            block_reason = "Blocked due to confidentiality exposure risk"
            flags.append("CONFIDENTIALITY_THRESHOLD_BLOCK")

    output_text = req.response_text
    out_flags: list[str] = []
    out_block = False
    if output_text is not None:
        out_flags, out_block = evaluate_output_rules(policy=policy_json, output_text=output_text)
        if out_block and outcome != "BLOCK":
            outcome = "BLOCK"
            block_reason = f'Output blocked by {get_terminology().get("rules_label") or "AI Rules"}'

    flags = sorted(set(flags + (sec.flags or []) + (out_flags or [])))
    return {
        "outcome": outcome,
        "block_reason": block_reason,
        "flags": flags,
        "phi": {"score": phi.score, "matches": phi.matches},
        "confidentiality_exposure_level": confidentiality_exposure_level(phi.score),
        "security": {
            "flags": sec.flags,
            "severity": sec.severity,
            "detector_names_triggered": sec.detector_names_triggered,
            "normalized_match_examples": sec.normalized_match_examples,
        },
        "output": {"flags": out_flags, "blocked": out_block, "skipped": output_text is None},
        "effective_messages": messages,
    }


@router.get("/history", response_model=list[PolicyVersionResponse])
@router.get("/versions", response_model=list[PolicyVersionResponse])
def list_versions(db: DbDep, user: PolicyReader, limit: int = 20) -> list[PolicyVersionResponse]:
    tenant_id = user.effective_tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")
    limit = max(1, min(100, limit))
    _ensure_current_policy(db, tenant_id=tenant_id, user=user)
    active_version_id, rows = _list_policy_versions_with_users(db, tenant_id=tenant_id, limit=limit)
    return [
        _serialize_policy_version(version, active_version_id=active_version_id, created_by_email=email)
        for version, email in rows
    ]


@router.get("/history/{version_id}", response_model=PolicyVersionResponse)
def get_history_item(version_id: str, db: DbDep, user: PolicyReader) -> PolicyVersionResponse:
    tenant_id = user.effective_tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")

    row = (
        db.query(TenantPolicyVersion, User.email)
        .outerjoin(User, User.id == TenantPolicyVersion.created_by_user_id)
        .filter(TenantPolicyVersion.tenant_id == tenant_id, TenantPolicyVersion.id == version_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy version not found")

    policy = _ensure_current_policy(db, tenant_id=tenant_id, user=user)
    version, email = row
    return _serialize_policy_version(version, active_version_id=policy.active_version_id, created_by_email=email)


@router.post("/rollback/{version_id}", response_model=PolicyResponse)
def rollback_policy(version_id: str, db: DbDep, user: PolicyWriter) -> PolicyResponse:
    tenant_id = user.effective_tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")

    target = (
        db.query(TenantPolicyVersion)
        .filter(TenantPolicyVersion.tenant_id == tenant_id, TenantPolicyVersion.id == version_id)
        .first()
    )
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy version not found")

    current = _ensure_current_policy(db, tenant_id=tenant_id, user=user)
    if current.active_version_id == version_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected version is already active")

    change_note = f"Rollback to version {version_id[:8]}"
    policy, new_version = _create_policy_version(
        db,
        tenant_id=tenant_id,
        policy_json=target.policy_json,
        user_id=user.id,
        change_note=change_note,
        source_template_id=target.source_template_id,
        source_version_id=target.id,
    )
    write_admin_audit_event(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        action_type="POLICY_VERSION_CREATED",
        outcome="success",
        reason="Policy rollback created a new version",
        event_data={"version_id": new_version.id, "source_version_id": target.id},
    )
    write_admin_audit_event(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        action_type="POLICY_VERSION_ACTIVATED",
        outcome="success",
        reason="Rollback version activated",
        event_data={"version_id": new_version.id, "source_version_id": target.id},
    )
    write_admin_audit_event(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        action_type="POLICY_ROLLBACK",
        outcome="success",
        reason="Policy rolled back",
        event_data={"version_id": new_version.id, "source_version_id": target.id},
    )
    return policy.to_response()
