from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.model_catalog import (
    PROVIDER_TYPES,
    default_model_for_provider,
    normalize_model_allowlist as catalog_normalize_model_allowlist,
    normalize_model_id,
    normalize_provider_id,
    provider_default_model_field as catalog_default_model_field,
)
from app.core.secrets import decrypt_json, encrypt_json
from app.db.models import TenantProviderConfig
from app.services.providers.base import (
    DEFAULT_CONNECT_TIMEOUT_SECONDS,
    DEFAULT_READ_TIMEOUT_SECONDS,
    DEFAULT_RETRYABLE_ERROR_CLASSES,
    DEFAULT_RETRYABLE_STATUS_CODES,
)


ProviderType = Literal["openai", "anthropic", "azure_openai", "ollama"]


class ProviderPolicyError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        detail: str,
        action_type: str,
        reason_code: str,
        provider: str | None = None,
        model: str | None = None,
        provider_config_id: str | None = None,
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.action_type = action_type
        self.reason_code = reason_code
        self.provider = provider
        self.model = model
        self.provider_config_id = provider_config_id


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_provider_type(value: str) -> str:
    return normalize_provider_id(value, allow_mock=False)


def normalize_model_allowlist(provider_type: str, value: list[str] | None) -> list[str]:
    return catalog_normalize_model_allowlist(provider_type, value)


def normalize_resilience_config(value: dict | None, *, provider_type: str) -> dict[str, Any]:
    raw = _as_dict(value)

    def _bounded_float(field_name: str, default: float, minimum: float, maximum: float) -> float:
        current = raw.get(field_name)
        if current in {None, ""}:
            return default
        try:
            parsed = float(current)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} must be a number") from exc
        if parsed < minimum or parsed > maximum:
            raise ValueError(f"{field_name} must be between {minimum} and {maximum}")
        return parsed

    def _bounded_int(field_name: str, default: int, minimum: int, maximum: int) -> int:
        current = raw.get(field_name)
        if current in {None, ""}:
            return default
        try:
            parsed = int(current)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} must be an integer") from exc
        if parsed < minimum or parsed > maximum:
            raise ValueError(f"{field_name} must be between {minimum} and {maximum}")
        return parsed

    retryable_status_codes: list[int] = []
    seen_statuses: set[int] = set()
    for item in raw.get("retryable_status_codes") or DEFAULT_RETRYABLE_STATUS_CODES:
        try:
            code = int(item)
        except (TypeError, ValueError) as exc:
            raise ValueError("retryable_status_codes must contain HTTP status codes") from exc
        if code < 100 or code > 599 or code in seen_statuses:
            continue
        retryable_status_codes.append(code)
        seen_statuses.add(code)

    retryable_error_classes: list[str] = []
    seen_classes: set[str] = set()
    for item in raw.get("retryable_error_classes") or DEFAULT_RETRYABLE_ERROR_CLASSES:
        value = str(item or "").strip().lower()
        if value not in {"timeout", "connection", "rate_limit", "server_error", "http_status"} or value in seen_classes:
            continue
        retryable_error_classes.append(value)
        seen_classes.add(value)

    fallback_enabled = bool(raw.get("fallback_enabled"))
    fallback_provider = str(raw.get("fallback_provider") or "").strip().lower() or None
    fallback_model_raw = str(raw.get("fallback_model") or "").strip()
    fallback_model = fallback_model_raw or None
    if fallback_enabled:
        if fallback_provider not in PROVIDER_TYPES:
            allowed = ", ".join(PROVIDER_TYPES)
            raise ValueError(f"fallback_provider must be one of: {allowed}")
        if not fallback_model:
            raise ValueError("fallback_model is required when fallback is enabled")
        fallback_model = normalize_model_id(fallback_provider, fallback_model, allow_empty=False)

    return {
        "connect_timeout_seconds": _bounded_float("connect_timeout_seconds", DEFAULT_CONNECT_TIMEOUT_SECONDS, 0.5, 120.0),
        "read_timeout_seconds": _bounded_float("read_timeout_seconds", DEFAULT_READ_TIMEOUT_SECONDS, 1.0, 600.0),
        "retry_count": _bounded_int("retry_count", 0, 0, 3),
        "retryable_status_codes": retryable_status_codes,
        "retryable_error_classes": retryable_error_classes,
        "fallback_enabled": fallback_enabled,
        "fallback_provider": fallback_provider,
        "fallback_model": fallback_model,
    }


def provider_default_model_field(provider_type: str) -> str:
    normalized = normalize_provider_type(provider_type)
    return catalog_default_model_field(normalized)


def get_provider_default_model(row: TenantProviderConfig | None) -> str | None:
    if row is None:
        return None
    config_json = row.config_json or {}
    field_name = provider_default_model_field(row.provider_type)
    value = str(config_json.get(field_name) or "").strip()
    return value or None


def set_provider_default_model(row: TenantProviderConfig, value: str | None) -> None:
    config_json = dict(row.config_json or {})
    field_name = provider_default_model_field(row.provider_type)
    normalized = str(value or "").strip()
    if normalized:
        config_json[field_name] = normalized
    else:
        config_json.pop(field_name, None)
    row.config_json = config_json


def _as_dict(value: dict | None) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("config_json must be an object")
    return dict(value)


def normalize_secret_json(provider_type: str, value: dict | None) -> dict[str, str]:
    raw = _as_dict(value)
    if provider_type in {"openai", "anthropic", "azure_openai", "ollama"}:
        api_key = str(raw.get("api_key") or "").strip()
        return {"api_key": api_key} if api_key else {}
    return {}


def normalize_config_json(provider_type: str, value: dict | None, *, model_allowlist: list[str]) -> dict[str, Any]:
    raw = _as_dict(value)
    resilience = normalize_resilience_config(raw.get("resilience"), provider_type=provider_type)

    if provider_type == "openai":
        out: dict[str, Any] = {}
        base_url = str(raw.get("base_url") or "").strip()
        default_model = normalize_model_id(provider_type, raw.get("default_model"), allow_empty=True)
        if base_url:
            out["base_url"] = base_url
        if default_model:
            out["default_model"] = default_model
        out["resilience"] = resilience
        return out

    if provider_type == "anthropic":
        out = {}
        base_url = str(raw.get("base_url") or "").strip()
        default_model = normalize_model_id(provider_type, raw.get("default_model"), allow_empty=True)
        if base_url:
            out["base_url"] = base_url
        if default_model:
            out["default_model"] = default_model
        out["resilience"] = resilience
        return out

    if provider_type == "ollama":
        out = {}
        base_url = str(raw.get("base_url") or "").strip()
        default_model = normalize_model_id(provider_type, raw.get("default_model"), allow_empty=True)
        api_key_env_var = str(raw.get("api_key_env_var") or "OLLAMA_API_KEY").strip() or "OLLAMA_API_KEY"
        if base_url:
            out["base_url"] = base_url
        if default_model:
            out["default_model"] = default_model
        out["api_key_env_var"] = api_key_env_var
        out["resilience"] = resilience
        return out

    endpoint = str(raw.get("endpoint") or "").strip()
    api_version = str(raw.get("api_version") or "").strip()
    auth_mode = str(raw.get("auth_mode") or "api_key").strip().lower()
    default_deployment = normalize_model_id(provider_type, raw.get("default_deployment"), allow_empty=True)
    managed_identity_client_id = str(raw.get("managed_identity_client_id") or "").strip()

    if not endpoint:
        raise ValueError("Azure OpenAI endpoint is required")
    if not api_version:
        raise ValueError("Azure OpenAI api_version is required")
    if auth_mode not in {"api_key", "managed_identity"}:
        raise ValueError("Azure OpenAI auth_mode must be 'api_key' or 'managed_identity'")
    if not default_deployment and not model_allowlist:
        raise ValueError("Azure OpenAI requires config_json.default_deployment or a non-empty model_allowlist")

    out = {"endpoint": endpoint, "api_version": api_version, "auth_mode": auth_mode}
    if default_deployment:
        out["default_deployment"] = default_deployment
    if managed_identity_client_id:
        out["managed_identity_client_id"] = managed_identity_client_id
    out["resilience"] = resilience
    return out


def validate_provider_config_payload(
    *,
    provider_type: str,
    display_name: str,
    model_allowlist: list[str] | None,
    config_json: dict | None,
    secret_json: dict | None,
    existing_secret_configured: bool,
    clear_secret: bool = False,
) -> dict[str, Any]:
    provider_type = normalize_provider_type(provider_type)
    display_name = (display_name or "").strip()
    if not display_name:
        raise ValueError("display_name is required")

    models = normalize_model_allowlist(provider_type, model_allowlist)
    normalized_secret = normalize_secret_json(provider_type, secret_json)
    normalized_config = normalize_config_json(provider_type, config_json, model_allowlist=models)
    default_model = str(normalized_config.get(provider_default_model_field(provider_type)) or "").strip()
    if default_model and models and default_model not in models:
        raise ValueError("Default model/deployment must also be included in the model allowlist")

    effective_secret_configured = bool(existing_secret_configured) and not clear_secret
    has_new_secret = bool(normalized_secret)

    if provider_type in {"openai", "anthropic"} and not (effective_secret_configured or has_new_secret):
        raise ValueError(f"{provider_type} API key is required")

    if provider_type == "azure_openai":
        auth_mode = normalized_config.get("auth_mode") or "api_key"
        if auth_mode == "api_key" and not (effective_secret_configured or has_new_secret):
            raise ValueError("Azure OpenAI API key is required when auth_mode='api_key'")

    return {
        "provider_type": provider_type,
        "display_name": display_name,
        "model_allowlist": models,
        "config_json": normalized_config,
        "secret_json": normalized_secret,
    }


def serialize_provider_config(row: TenantProviderConfig) -> dict[str, Any]:
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "provider_type": row.provider_type,
        "display_name": row.display_name,
        "is_enabled": row.is_enabled,
        "is_default": row.is_default,
        "model_allowlist": row.model_allowlist or [],
        "config_json": row.config_json or {},
        "secret_configured": bool((row.encrypted_secret_blob or "").strip()),
        "secret_status": "configured" if (row.encrypted_secret_blob or "").strip() else "not_configured",
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def get_provider_config_or_404(db: Session, *, tenant_id: str, provider_config_id: str) -> TenantProviderConfig:
    row = (
        db.query(TenantProviderConfig)
        .filter(TenantProviderConfig.id == provider_config_id, TenantProviderConfig.tenant_id == tenant_id)
        .one_or_none()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider config not found")
    return row


def set_default_provider_config(db: Session, *, tenant_id: str, provider_config_id: str) -> TenantProviderConfig:
    rows = db.query(TenantProviderConfig).filter(TenantProviderConfig.tenant_id == tenant_id).all()
    target: TenantProviderConfig | None = None
    for row in rows:
        should_default = row.id == provider_config_id
        if row.is_default != should_default:
            row.is_default = should_default
            row.updated_at = utcnow()
            db.add(row)
        if should_default:
            target = row
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider config not found")
    return target


def secret_payload(row: TenantProviderConfig) -> dict[str, Any]:
    return decrypt_json(row.encrypted_secret_blob)


def _is_placeholder_api_key(value: str | None) -> bool:
    raw = str(value or "").strip().lower()
    if not raw:
        return True
    return raw.startswith("demo-") or raw.startswith("change_me") or raw.startswith("placeholder")


def update_secret_blob(*, row: TenantProviderConfig, secret_json: dict | None, clear_secret: bool) -> None:
    if clear_secret:
        row.encrypted_secret_blob = None
        return
    if secret_json:
        row.encrypted_secret_blob = encrypt_json(secret_json)


def config_runtime_settings(row: TenantProviderConfig) -> dict[str, Any]:
    runtime_settings: dict[str, Any] = {"provider_type": row.provider_type}
    runtime_settings.update(row.config_json or {})
    runtime_settings.update(secret_payload(row))
    # Allow local/container env credentials to override seeded demo placeholder secrets.
    if row.provider_type == "openai":
        candidate = runtime_settings.get("api_key")
        if _is_placeholder_api_key(candidate) and (settings.openai_api_key or "").strip():
            runtime_settings["api_key"] = settings.openai_api_key
    elif row.provider_type == "anthropic":
        candidate = runtime_settings.get("api_key")
        if _is_placeholder_api_key(candidate) and (settings.anthropic_api_key or "").strip():
            runtime_settings["api_key"] = settings.anthropic_api_key
    elif row.provider_type == "azure_openai":
        candidate = runtime_settings.get("api_key")
        if _is_placeholder_api_key(candidate) and (settings.azure_openai_api_key or "").strip():
            runtime_settings["api_key"] = settings.azure_openai_api_key
    elif row.provider_type == "ollama":
        candidate = runtime_settings.get("api_key")
        if _is_placeholder_api_key(candidate):
            if (settings.ollama_api_key or "").strip():
                runtime_settings["api_key"] = settings.ollama_api_key
            else:
                runtime_settings["api_key"] = "ollama-placeholder"
        if not str(runtime_settings.get("base_url") or "").strip():
            runtime_settings["base_url"] = settings.ollama_base_url
    runtime_settings["model_allowlist"] = row.model_allowlist or []
    return runtime_settings


def serialize_provider_policy(row: TenantProviderConfig | None, *, provider_type: str) -> dict[str, Any]:
    return {
        "provider_type": provider_type,
        "provider_config_id": row.id if row else None,
        "display_name": row.display_name if row else None,
        "is_configured": row is not None,
        "secret_configured": bool((row.encrypted_secret_blob or "").strip()) if row else False,
        "is_enabled": bool(row.is_enabled) if row else False,
        "is_default": bool(row.is_default) if row else False,
        "allowed_models": row.model_allowlist or [] if row else [],
        "default_model": get_provider_default_model(row),
    }


def build_provider_policy_snapshot(db: Session, *, tenant_id: str) -> dict[str, Any]:
    rows = db.query(TenantProviderConfig).filter(TenantProviderConfig.tenant_id == tenant_id).all()
    rows_by_provider = {row.provider_type: row for row in rows}
    providers = [serialize_provider_policy(rows_by_provider.get(provider_type), provider_type=provider_type) for provider_type in PROVIDER_TYPES]
    enabled = [row for row in rows if row.is_enabled]
    default_row = next((row for row in enabled if row.is_default), None)
    warnings: list[str] = []
    if enabled and default_row is None and len(enabled) > 1:
        warnings.append("Multiple approved providers are enabled but no default provider is configured.")
    if default_row is not None and not get_provider_default_model(default_row):
        warnings.append(f"Default provider '{default_row.provider_type}' has no default model/deployment configured.")
    for row in enabled:
        if not get_provider_default_model(row):
            warnings.append(f"Approved provider '{row.provider_type}' has no default model/deployment configured.")
    return {
        "tenant_id": tenant_id,
        "default_provider": default_row.provider_type if default_row else None,
        "providers": providers,
        "warnings": warnings,
    }


def resolve_gateway_provider(
    db: Session,
    *,
    tenant_id: str,
    requested_provider: str | None,
    model: str | None,
) -> tuple[str, str, dict[str, Any], TenantProviderConfig | None]:
    requested_raw = (requested_provider or "").strip().lower() or None
    requested: str | None = None
    if requested_raw:
        try:
            requested = normalize_provider_id(requested_raw, allow_mock=False)
        except ValueError as exc:
            raise ProviderPolicyError(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid provider",
                action_type="PROVIDER_DENY",
                reason_code="invalid_provider",
                provider=requested_raw,
                model=(model or "").strip() or None,
            ) from exc
    rows = db.query(TenantProviderConfig).filter(TenantProviderConfig.tenant_id == tenant_id).all()
    enabled_rows = [row for row in rows if row.is_enabled]
    rows_by_provider = {row.provider_type: row for row in enabled_rows}

    if rows:
        if not enabled_rows:
            raise ProviderPolicyError(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No approved provider configured for tenant",
                action_type="PROVIDER_DENY",
                reason_code="no_approved_provider",
                provider=requested,
                model=(model or "").strip() or None,
            )
        if requested:
            row = rows_by_provider.get(requested)
            if not row:
                raise ProviderPolicyError(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Provider not approved for tenant",
                    action_type="PROVIDER_DENY",
                    reason_code="provider_not_approved",
                    provider=requested,
                    model=(model or "").strip() or None,
                )
        else:
            default_row = next((row for row in enabled_rows if row.is_default), None)
            if default_row is None:
                if len(enabled_rows) == 1:
                    default_row = enabled_rows[0]
                else:
                    raise ProviderPolicyError(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="No default provider configured for tenant",
                        action_type="PROVIDER_DENY",
                        reason_code="default_provider_required",
                        model=(model or "").strip() or None,
                    )
            row = default_row

        resolved_model = str(model or "").strip() or get_provider_default_model(row)
        if not resolved_model:
            raise ProviderPolicyError(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No default model/deployment configured for the approved provider",
                action_type="MODEL_DENY",
                reason_code="default_model_required",
                provider=row.provider_type,
                provider_config_id=row.id,
            )
        try:
            resolved_model = normalize_model_id(row.provider_type, resolved_model, allow_empty=False)
        except ValueError as exc:
            raise ProviderPolicyError(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
                action_type="MODEL_DENY",
                reason_code="invalid_model",
                provider=row.provider_type,
                model=resolved_model,
                provider_config_id=row.id,
            ) from exc
        allowlist = catalog_normalize_model_allowlist(row.provider_type, row.model_allowlist or [])
        if allowlist and resolved_model not in allowlist:
            raise ProviderPolicyError(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Model not approved for tenant provider",
                action_type="MODEL_DENY",
                reason_code="model_not_approved",
                provider=row.provider_type,
                model=resolved_model,
                provider_config_id=row.id,
            )
        return row.provider_type, resolved_model, config_runtime_settings(row), row

    env = (settings.environment or "").strip().lower()
    if env == "production":
        raise ProviderPolicyError(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Provider not configured for tenant",
            action_type="PROVIDER_DENY",
            reason_code="provider_not_configured",
            provider=requested,
            model=(model or "").strip() or None,
        )

    provider_name_raw = requested or settings.provider_default or "mock"
    try:
        provider_name = normalize_provider_id(provider_name_raw, allow_mock=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid provider")
    if provider_name == "mock":
        resolved_model = "mock"
    else:
        fallback_model = str(model or "").strip()
        if fallback_model:
            try:
                resolved_model = normalize_model_id(provider_name, fallback_model, allow_empty=False)
            except ValueError as exc:
                raise ProviderPolicyError(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(exc),
                    action_type="MODEL_DENY",
                    reason_code="invalid_model",
                    provider=provider_name,
                    model=fallback_model,
                ) from exc
        else:
            resolved_model = default_model_for_provider(provider_name) or "mock"
    return provider_name, resolved_model, {}, None
