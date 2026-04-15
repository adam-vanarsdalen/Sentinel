from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import DbDep, require_role
from app.core.model_catalog import catalog_payload, default_model_for_provider, normalize_model_id
from app.core.errors import ApiError, ProviderServiceError
from app.db.models import TenantProviderConfig, User
from app.services.audit_log import write_admin_audit_event
from app.services.provider_configs import (
    PROVIDER_TYPES,
    build_provider_policy_snapshot,
    config_runtime_settings,
    get_provider_config_or_404,
    normalize_model_allowlist,
    normalize_provider_type,
    serialize_provider_config,
    set_default_provider_config,
    set_provider_default_model,
    update_secret_blob,
    utcnow,
    validate_provider_config_payload,
)
from app.services.policy_model_sync import reconcile_tenant_policy_rows
from app.services.providers.anthropic_provider import AnthropicProvider
from app.services.providers.azure_openai_provider import AzureOpenAiProvider
from app.services.providers.ollama_provider import OllamaProvider
from app.services.providers.openai_provider import OpenAiProvider


router = APIRouter()

ProviderConfigAdmin = Annotated[User, Depends(require_role("org_admin"))]
ProviderCatalogReader = Annotated[User, Depends(require_role("super_admin", "org_admin", "compliance_admin", "operator", "reviewer", "auditor"))]


class ProviderConfigResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    id: str
    tenant_id: str
    provider_type: str
    display_name: str
    is_enabled: bool
    is_default: bool
    model_allowlist: list[str]
    config_json: dict
    secret_configured: bool
    secret_status: str
    created_at: str
    updated_at: str


class ProviderConfigCreateRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    provider_type: str
    display_name: str = Field(min_length=1, max_length=200)
    is_enabled: bool = True
    is_default: bool = False
    model_allowlist: list[str] | None = None
    config_json: dict | None = None
    secret_json: dict | None = None


class ProviderConfigUpdateRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    is_enabled: bool | None = None
    is_default: bool | None = None
    model_allowlist: list[str] | None = None
    config_json: dict | None = None
    secret_json: dict | None = None
    clear_secret: bool = False


class ProviderPolicyProviderResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    provider_type: str
    provider_config_id: str | None = None
    display_name: str | None = None
    is_configured: bool
    secret_configured: bool
    is_enabled: bool
    is_default: bool
    allowed_models: list[str]
    default_model: str | None = None


class ProviderPolicyResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    tenant_id: str
    default_provider: str | None = None
    providers: list[ProviderPolicyProviderResponse]
    warnings: list[str]


class ProviderPolicyProviderRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    provider_type: str
    is_enabled: bool
    allowed_models: list[str] | None = None
    default_model: str | None = None


class ProviderPolicyUpdateRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    default_provider: str | None = None
    providers: list[ProviderPolicyProviderRequest]


class ProviderCatalogModelResponse(BaseModel):
    id: str
    display_name: str
    status: str
    aliases: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)


class ProviderCatalogItemResponse(BaseModel):
    id: str
    display_name: str
    default_model_field: str | None = None
    supports_custom_models: bool
    enabled_by_default: bool
    notes: str | None = None
    models: list[ProviderCatalogModelResponse]


class ProviderCatalogResponse(BaseModel):
    providers: list[ProviderCatalogItemResponse]


class ProviderDiscoveredModelsResponse(BaseModel):
    provider_type: str
    models: list[dict[str, Any]] = Field(default_factory=list)
    source: str = "provider_native"


def _tenant_id_for(user: User) -> str:
    tenant_id = user.effective_tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")
    return tenant_id


def _provider_client(provider_type: str):
    if provider_type == "openai":
        return OpenAiProvider()
    if provider_type == "anthropic":
        return AnthropicProvider()
    if provider_type == "azure_openai":
        return AzureOpenAiProvider()
    if provider_type == "ollama":
        return OllamaProvider()
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid provider_type")


def _connection_test_model(row: TenantProviderConfig) -> str:
    config_json = row.config_json or {}
    model_allowlist = row.model_allowlist or []
    if row.provider_type == "azure_openai":
        return str(
            config_json.get("default_deployment")
            or (model_allowlist[0] if model_allowlist else "")
            or default_model_for_provider(row.provider_type)
            or ""
        ).strip()
    return str(
        config_json.get("default_model")
        or (model_allowlist[0] if model_allowlist else "")
        or default_model_for_provider(row.provider_type)
        or ""
    ).strip()


def _audit_event_payload(row: TenantProviderConfig) -> dict[str, Any]:
    return {
        "provider_config_id": row.id,
        "provider_type": row.provider_type,
        "display_name": row.display_name,
        "is_enabled": row.is_enabled,
        "is_default": row.is_default,
        "model_allowlist": row.model_allowlist or [],
        "config_json": row.config_json or {},
        "secret_configured": bool(row.encrypted_secret_blob),
    }


def _write_provider_policy_update_audit(db: DbDep, *, tenant_id: str, user_id: str) -> None:
    snapshot = build_provider_policy_snapshot(db, tenant_id=tenant_id)
    write_admin_audit_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action_type="PROVIDER_POLICY_UPDATE",
        outcome="success",
        reason="Provider approval policy updated",
        event_data=snapshot,
    )


def _sync_policy_model_allowlist_if_stale(db: DbDep, *, tenant_id: str) -> None:
    if reconcile_tenant_policy_rows(db, tenant_id=tenant_id):
        db.commit()


@router.get("/policy", response_model=ProviderPolicyResponse)
def get_provider_policy(db: DbDep, user: ProviderConfigAdmin) -> ProviderPolicyResponse:
    tenant_id = _tenant_id_for(user)
    return build_provider_policy_snapshot(db, tenant_id=tenant_id)


@router.get("/catalog", response_model=ProviderCatalogResponse)
def get_provider_catalog(user: ProviderCatalogReader) -> ProviderCatalogResponse:
    _ = user
    return ProviderCatalogResponse.model_validate(catalog_payload(include_mock=False))


@router.put("/policy", response_model=ProviderPolicyResponse)
def update_provider_policy(req: ProviderPolicyUpdateRequest, db: DbDep, user: ProviderConfigAdmin) -> ProviderPolicyResponse:
    tenant_id = _tenant_id_for(user)
    rows = db.query(TenantProviderConfig).filter(TenantProviderConfig.tenant_id == tenant_id).all()
    rows_by_provider = {row.provider_type: row for row in rows}
    seen: set[str] = set()

    for item in req.providers:
        provider_type = normalize_provider_type(item.provider_type)
        if provider_type in seen:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Duplicate provider_type in policy update")
        seen.add(provider_type)

        row = rows_by_provider.get(provider_type)
        if row is None:
            if item.is_enabled or normalize_model_allowlist(provider_type, item.allowed_models) or str(item.default_model or "").strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{provider_type} must be configured before it can be approved",
                )
            continue

        allowed_models = normalize_model_allowlist(provider_type, item.allowed_models)
        default_model = normalize_model_id(provider_type, item.default_model, allow_empty=True)
        if default_model and allowed_models and default_model not in allowed_models:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Default model/deployment must also be included in the allowed models list",
            )

        row.is_enabled = item.is_enabled
        row.model_allowlist = allowed_models
        set_provider_default_model(row, default_model or None)
        if not row.is_enabled:
            row.is_default = False
        row.updated_at = utcnow()
        db.add(row)

    default_provider = str(req.default_provider or "").strip().lower() or None
    if default_provider is None:
        for row in rows:
            if row.is_default:
                row.is_default = False
                row.updated_at = utcnow()
                db.add(row)
    else:
        if default_provider not in PROVIDER_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid default_provider")
        target = rows_by_provider.get(default_provider)
        if target is None or not target.is_enabled:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Default provider must be configured and enabled")
        set_default_provider_config(db, tenant_id=tenant_id, provider_config_id=target.id)

    db.commit()
    _sync_policy_model_allowlist_if_stale(db, tenant_id=tenant_id)
    _write_provider_policy_update_audit(db, tenant_id=tenant_id, user_id=user.id)
    return build_provider_policy_snapshot(db, tenant_id=tenant_id)


@router.get("", response_model=list[ProviderConfigResponse])
def list_provider_configs(db: DbDep, user: ProviderConfigAdmin) -> list[ProviderConfigResponse]:
    tenant_id = _tenant_id_for(user)
    rows = (
        db.query(TenantProviderConfig)
        .filter(TenantProviderConfig.tenant_id == tenant_id)
        .order_by(TenantProviderConfig.provider_type.asc(), TenantProviderConfig.created_at.asc())
        .all()
    )
    return [serialize_provider_config(row) for row in rows]


@router.post("", response_model=ProviderConfigResponse, status_code=201)
def create_provider_config(req: ProviderConfigCreateRequest, db: DbDep, user: ProviderConfigAdmin) -> ProviderConfigResponse:
    tenant_id = _tenant_id_for(user)
    if (
        db.query(TenantProviderConfig)
        .filter(TenantProviderConfig.tenant_id == tenant_id, TenantProviderConfig.provider_type == req.provider_type.strip().lower())
        .count()
        > 0
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Provider config already exists for this provider")

    try:
        normalized = validate_provider_config_payload(
            provider_type=req.provider_type,
            display_name=req.display_name,
            model_allowlist=req.model_allowlist,
            config_json=req.config_json,
            secret_json=req.secret_json,
            existing_secret_configured=False,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    existing_count = db.query(TenantProviderConfig).filter(TenantProviderConfig.tenant_id == tenant_id).count()
    initial_is_default = bool(req.is_default or (existing_count == 0 and req.is_enabled))
    if initial_is_default and not req.is_enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Default provider config must be enabled")
    row = TenantProviderConfig(
        tenant_id=tenant_id,
        provider_type=normalized["provider_type"],
        display_name=normalized["display_name"],
        is_enabled=req.is_enabled,
        is_default=initial_is_default,
        model_allowlist=normalized["model_allowlist"],
        config_json=normalized["config_json"],
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    update_secret_blob(row=row, secret_json=normalized["secret_json"], clear_secret=False)
    db.add(row)
    db.commit()
    db.refresh(row)

    if row.is_default:
        set_default_provider_config(db, tenant_id=tenant_id, provider_config_id=row.id)
        db.commit()
        db.refresh(row)
    _sync_policy_model_allowlist_if_stale(db, tenant_id=tenant_id)

    write_admin_audit_event(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        action_type="PROVIDER_CONFIG_CREATE",
        outcome="success",
        reason="Provider config created",
        event_data=_audit_event_payload(row),
    )
    _write_provider_policy_update_audit(db, tenant_id=tenant_id, user_id=user.id)
    return serialize_provider_config(row)


@router.patch("/{provider_config_id}", response_model=ProviderConfigResponse)
def update_provider_config(
    provider_config_id: str,
    req: ProviderConfigUpdateRequest,
    db: DbDep,
    user: ProviderConfigAdmin,
) -> ProviderConfigResponse:
    tenant_id = _tenant_id_for(user)
    row = get_provider_config_or_404(db, tenant_id=tenant_id, provider_config_id=provider_config_id)

    display_name = req.display_name if req.display_name is not None else row.display_name
    model_allowlist = req.model_allowlist if req.model_allowlist is not None else (row.model_allowlist or [])
    config_json = req.config_json if req.config_json is not None else (row.config_json or {})

    try:
        normalized = validate_provider_config_payload(
            provider_type=row.provider_type,
            display_name=display_name,
            model_allowlist=model_allowlist,
            config_json=config_json,
            secret_json=req.secret_json,
            existing_secret_configured=bool(row.encrypted_secret_blob),
            clear_secret=req.clear_secret,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    next_is_enabled = req.is_enabled if req.is_enabled is not None else row.is_enabled
    next_is_default = req.is_default if req.is_default is not None else row.is_default
    if next_is_default and not next_is_enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Default provider config must be enabled")

    row.display_name = normalized["display_name"]
    row.model_allowlist = normalized["model_allowlist"]
    row.config_json = normalized["config_json"]
    row.is_enabled = next_is_enabled
    row.is_default = bool(next_is_default)
    row.updated_at = utcnow()
    update_secret_blob(row=row, secret_json=normalized["secret_json"], clear_secret=req.clear_secret)
    db.add(row)
    db.commit()
    db.refresh(row)

    if row.is_default:
        set_default_provider_config(db, tenant_id=tenant_id, provider_config_id=row.id)
    elif not row.is_enabled:
        row.is_default = False
        db.add(row)
    db.commit()
    db.refresh(row)
    _sync_policy_model_allowlist_if_stale(db, tenant_id=tenant_id)

    write_admin_audit_event(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        action_type="PROVIDER_CONFIG_UPDATE",
        outcome="success",
        reason="Provider config updated",
        event_data=_audit_event_payload(row),
    )
    _write_provider_policy_update_audit(db, tenant_id=tenant_id, user_id=user.id)
    return serialize_provider_config(row)


@router.delete("/{provider_config_id}", response_model=dict)
def delete_provider_config(provider_config_id: str, db: DbDep, user: ProviderConfigAdmin) -> dict:
    tenant_id = _tenant_id_for(user)
    row = get_provider_config_or_404(db, tenant_id=tenant_id, provider_config_id=provider_config_id)
    event_data = _audit_event_payload(row)
    db.delete(row)
    db.commit()
    _sync_policy_model_allowlist_if_stale(db, tenant_id=tenant_id)
    write_admin_audit_event(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        action_type="PROVIDER_CONFIG_DELETE",
        outcome="success",
        reason="Provider config deleted",
        event_data=event_data,
    )
    _write_provider_policy_update_audit(db, tenant_id=tenant_id, user_id=user.id)
    return {"ok": True}


@router.post("/{provider_config_id}/set-default", response_model=ProviderConfigResponse)
def set_provider_config_default(provider_config_id: str, db: DbDep, user: ProviderConfigAdmin) -> ProviderConfigResponse:
    tenant_id = _tenant_id_for(user)
    row = get_provider_config_or_404(db, tenant_id=tenant_id, provider_config_id=provider_config_id)
    if not row.is_enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Default provider config must be enabled")
    target = set_default_provider_config(db, tenant_id=tenant_id, provider_config_id=provider_config_id)
    db.commit()
    db.refresh(target)
    _sync_policy_model_allowlist_if_stale(db, tenant_id=tenant_id)
    write_admin_audit_event(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        action_type="PROVIDER_CONFIG_SET_DEFAULT",
        outcome="success",
        reason="Provider config set as default",
        event_data=_audit_event_payload(target),
    )
    _write_provider_policy_update_audit(db, tenant_id=tenant_id, user_id=user.id)
    return serialize_provider_config(target)


@router.post("/{provider_config_id}/test-connection", response_model=dict)
def test_provider_config_connection(provider_config_id: str, db: DbDep, user: ProviderConfigAdmin) -> dict:
    tenant_id = _tenant_id_for(user)
    row = get_provider_config_or_404(db, tenant_id=tenant_id, provider_config_id=provider_config_id)
    model = _connection_test_model(row)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A test model/deployment is required. Add config_json.default_model/default_deployment or model_allowlist.",
        )

    provider = _provider_client(row.provider_type)
    try:
        provider.chat_completions(
            model=model,
            messages=[{"role": "user", "content": "Reply with OK."}],
            max_tokens=8,
            temperature=0,
            runtime_config=config_runtime_settings(row),
        )
    except ProviderServiceError as exc:
        write_admin_audit_event(
            db,
            tenant_id=tenant_id,
            user_id=user.id,
            action_type="PROVIDER_CONFIG_TEST",
            outcome="fail",
            reason=exc.detail[:500],
            event_data={**_audit_event_payload(row), "model": model},
        )
        raise ApiError(
            status_code=exc.status_code,
            code=exc.code,
            message="Provider connection test failed.",
            detail=exc.detail[:500],
            retryable=exc.retryable,
        ) from exc
    except Exception as exc:
        write_admin_audit_event(
            db,
            tenant_id=tenant_id,
            user_id=user.id,
            action_type="PROVIDER_CONFIG_TEST",
            outcome="fail",
            reason=str(exc)[:500],
            event_data={**_audit_event_payload(row), "model": model},
        )
        raise ApiError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="PROVIDER_UNAVAILABLE",
            message="Provider connection test failed.",
            detail="Provider connection test failed",
            retryable=True,
        ) from exc

    write_admin_audit_event(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        action_type="PROVIDER_CONFIG_TEST",
        outcome="success",
        reason="Provider connection test succeeded",
        event_data={**_audit_event_payload(row), "model": model},
    )
    return {"ok": True, "provider_type": row.provider_type, "model": model}


@router.get("/{provider_config_id}/models", response_model=ProviderDiscoveredModelsResponse)
def list_provider_discovered_models(provider_config_id: str, db: DbDep, user: ProviderConfigAdmin) -> ProviderDiscoveredModelsResponse:
    tenant_id = _tenant_id_for(user)
    row = get_provider_config_or_404(db, tenant_id=tenant_id, provider_config_id=provider_config_id)
    provider = _provider_client(row.provider_type)
    if not hasattr(provider, "list_models"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provider does not support model discovery")

    try:
        models = provider.list_models(runtime_config=config_runtime_settings(row))  # type: ignore[attr-defined]
    except ProviderServiceError as exc:
        raise ApiError(
            status_code=exc.status_code,
            code=exc.code,
            message="Provider model discovery failed.",
            detail=exc.detail[:500],
            retryable=exc.retryable,
        ) from exc

    return ProviderDiscoveredModelsResponse(provider_type=row.provider_type, models=models)
