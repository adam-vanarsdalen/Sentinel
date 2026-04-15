from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.cost import estimate_cost_usd
from app.core.errors import ApiError, ProviderServiceError
from app.core.request_context import get_request_id
from app.core.security import sha256_text
from app.db.models import ApiKey, AuditEvent, TenantPolicy
from app.services.alerts import maybe_send_alerts_for_event
from app.services.audit_log import write_system_audit_event
from app.services.phi import scan_phi
from app.services.policy import (
    DEFAULT_POLICY,
    apply_required_system_prefix,
    enforce_preflight,
    evaluate_output_rules,
    should_block_prompt_injection,
)
from app.services.provider_configs import ProviderPolicyError, resolve_gateway_provider
from app.services.providers.anthropic_provider import AnthropicProvider
from app.services.providers.azure_openai_provider import AzureOpenAiProvider
from app.services.providers.base import (
    DEFAULT_CONNECT_TIMEOUT_SECONDS,
    DEFAULT_READ_TIMEOUT_SECONDS,
    DEFAULT_RETRYABLE_ERROR_CLASSES,
    DEFAULT_RETRYABLE_STATUS_CODES,
)
from app.services.providers.mock import MockProvider
from app.services.providers.openai_provider import OpenAiProvider
from app.services.security_flags import SecuritySignals, detect_security_signals

logger = logging.getLogger(__name__)


class RequestBlocked(Exception):
    def __init__(
        self,
        *,
        status_code: int = status.HTTP_403_FORBIDDEN,
        block_reason: str,
        flags: list[str] | None = None,
        policy_updated_at: str | None = None,
        policy_version_id: str | None = None,
        rule: str | None = None,
        reason_code: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        error_code: str = "POLICY_BLOCKED",
        retryable: bool = False,
        security: dict[str, Any] | None = None,
    ):
        self.status_code = status_code
        self.block_reason = block_reason
        self.flags = flags or []
        self.policy_updated_at = policy_updated_at
        self.policy_version_id = policy_version_id
        self.rule = rule
        self.reason_code = reason_code
        self.provider = provider
        self.model = model
        self.error_code = error_code
        self.retryable = retryable
        self.security = security


def _get_policy(db: Session, tenant_id: str) -> dict:
    policy_row = db.get(TenantPolicy, tenant_id)
    return policy_row.policy_json if policy_row else DEFAULT_POLICY


def _get_policy_info(db: Session, tenant_id: str) -> dict:
    policy_row = db.get(TenantPolicy, tenant_id)
    updated_at = policy_row.updated_at.isoformat() if policy_row else None
    version_id = None
    try:
        from app.db.models import TenantPolicyVersion

        latest = (
            db.query(TenantPolicyVersion.id)
            .filter(TenantPolicyVersion.tenant_id == tenant_id)
            .order_by(TenantPolicyVersion.created_at.desc())
            .first()
        )
        version_id = latest[0] if latest else None
    except Exception:
        version_id = None
    return {"updated_at": updated_at, "version_id": version_id}


def _estimate_tokens(text: str) -> int:
    # Pilot estimate: ~4 chars/token.
    return max(1, len(text) // 4)


def _provider(name: str):
    if name == "openai":
        return OpenAiProvider()
    if name == "azure_openai":
        return AzureOpenAiProvider()
    if name == "anthropic":
        return AnthropicProvider()
    return MockProvider()


def _security_details(signals: SecuritySignals) -> dict[str, Any]:
    return {
        "flags": signals.flags,
        "severity": signals.severity,
        "detector_names_triggered": signals.detector_names_triggered,
        "normalized_match_examples": signals.normalized_match_examples,
    }


def _resilience_config(runtime_config: dict[str, Any] | None) -> dict[str, Any]:
    runtime_config = runtime_config or {}
    raw = runtime_config.get("resilience") if isinstance(runtime_config.get("resilience"), dict) else {}
    retryable_status_codes = [int(code) for code in (raw.get("retryable_status_codes") or DEFAULT_RETRYABLE_STATUS_CODES)]
    retryable_error_classes = [str(code) for code in (raw.get("retryable_error_classes") or DEFAULT_RETRYABLE_ERROR_CLASSES)]
    return {
        "connect_timeout_seconds": float(raw.get("connect_timeout_seconds") or DEFAULT_CONNECT_TIMEOUT_SECONDS),
        "read_timeout_seconds": float(raw.get("read_timeout_seconds") or DEFAULT_READ_TIMEOUT_SECONDS),
        "retry_count": max(0, int(raw.get("retry_count") or 0)),
        "retryable_status_codes": retryable_status_codes,
        "retryable_error_classes": retryable_error_classes,
        "fallback_enabled": bool(raw.get("fallback_enabled")),
        "fallback_provider": str(raw.get("fallback_provider") or "").strip().lower() or None,
        "fallback_model": str(raw.get("fallback_model") or "").strip() or None,
    }


def _write_provider_runtime_event(
    db: Session,
    *,
    tenant_id: str,
    api_key_id: str,
    action_type: str,
    outcome: str,
    reason: str,
    provider: str | None,
    model: str | None,
    event_data: dict[str, Any],
) -> None:
    write_system_audit_event(
        db,
        tenant_id=tenant_id,
        api_key_id=api_key_id,
        action_type=action_type,
        outcome=outcome,
        reason=reason[:500],
        provider=provider,
        model=model,
        event_data=event_data,
    )


def _should_retry_provider_error(exc: ProviderServiceError, *, resilience: dict[str, Any]) -> bool:
    if exc.provider_status_code is not None and int(exc.provider_status_code) in set(resilience["retryable_status_codes"]):
        return True
    if exc.error_class and str(exc.error_class) in set(resilience["retryable_error_classes"]):
        return True
    return exc.retryable


def _invoke_provider_with_resilience(
    db: Session,
    *,
    tenant_id: str,
    api_key_id: str,
    provider_name: str,
    model: str,
    runtime_config: dict[str, Any],
    provider_config_row,
    messages: list[dict],
    max_tokens: int | None,
    temperature: float | None,
) -> tuple[Any, str, str, dict[str, Any], Any, list[dict[str, Any]]]:
    current_provider_name = provider_name
    current_model = model
    current_runtime_config = runtime_config
    current_provider_row = provider_config_row
    current_provider = _provider(current_provider_name)
    fallback_consumed = False
    attempt_trace: list[dict[str, Any]] = []
    attempt_number = 0

    while True:
        resilience = _resilience_config(current_runtime_config)
        try:
            resp = current_provider.chat_completions(
                model=current_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                runtime_config=current_runtime_config,
            )
            attempt_trace.append(
                {
                    "provider": current_provider_name,
                    "model": current_model,
                    "attempt_number": attempt_number + 1,
                    "outcome": "success",
                }
            )
            return resp, current_provider_name, current_model, current_runtime_config, current_provider_row, attempt_trace
        except ProviderServiceError as exc:
            attempt_number += 1
            attempt_event = {
                "provider": current_provider_name,
                "model": current_model,
                "attempt_number": attempt_number,
                "outcome": "fail",
                "error_code": exc.code,
                "error_class": exc.error_class,
                "provider_status_code": exc.provider_status_code,
            }
            attempt_trace.append(attempt_event)
            if exc.code == "PROVIDER_TIMEOUT":
                _write_provider_runtime_event(
                    db,
                    tenant_id=tenant_id,
                    api_key_id=api_key_id,
                    action_type="PROVIDER_TIMEOUT",
                    outcome="fail",
                    reason=exc.detail,
                    provider=current_provider_name,
                    model=current_model,
                    event_data=attempt_event,
                )

            if attempt_number <= int(resilience["retry_count"]) and _should_retry_provider_error(exc, resilience=resilience):
                _write_provider_runtime_event(
                    db,
                    tenant_id=tenant_id,
                    api_key_id=api_key_id,
                    action_type="PROVIDER_RETRY",
                    outcome="success",
                    reason=f"Retrying provider after transient failure: {exc.detail}",
                    provider=current_provider_name,
                    model=current_model,
                    event_data={**attempt_event, "remaining_retries": int(resilience["retry_count"]) - attempt_number + 1},
                )
                continue

            if (
                not fallback_consumed
                and bool(resilience["fallback_enabled"])
                and resilience["fallback_provider"]
                and resilience["fallback_model"]
            ):
                fallback_provider = str(resilience["fallback_provider"])
                fallback_model = str(resilience["fallback_model"])
                try:
                    fallback_provider_name, fallback_resolved_model, fallback_runtime_config, fallback_provider_row = resolve_gateway_provider(
                        db,
                        tenant_id=tenant_id,
                        requested_provider=fallback_provider,
                        model=fallback_model,
                    )
                except ProviderPolicyError as fallback_exc:
                    _write_provider_runtime_event(
                        db,
                        tenant_id=tenant_id,
                        api_key_id=api_key_id,
                        action_type="PROVIDER_FALLBACK_DENIED",
                        outcome="fail",
                        reason=fallback_exc.detail,
                        provider=fallback_provider,
                        model=fallback_model,
                        event_data={
                            "reason_code": fallback_exc.reason_code,
                            "from_provider": current_provider_name,
                            "from_model": current_model,
                            "requested_fallback_provider": fallback_provider,
                            "requested_fallback_model": fallback_model,
                        },
                    )
                    raise ProviderServiceError(
                        status_code=exc.status_code,
                        code=exc.code,
                        detail=f"{exc.detail}. Fallback denied for this organization.",
                        retryable=exc.retryable,
                        provider_status_code=exc.provider_status_code,
                        error_class=exc.error_class,
                        attempt_trace=list(attempt_trace),
                    ) from exc

                if fallback_provider_name == current_provider_name and fallback_resolved_model == current_model:
                    _write_provider_runtime_event(
                        db,
                        tenant_id=tenant_id,
                        api_key_id=api_key_id,
                        action_type="PROVIDER_FALLBACK_DENIED",
                        outcome="fail",
                        reason="Fallback target duplicates the primary provider/model.",
                        provider=fallback_provider_name,
                        model=fallback_resolved_model,
                        event_data={
                            "from_provider": current_provider_name,
                            "from_model": current_model,
                        },
                    )
                    raise ProviderServiceError(
                        status_code=exc.status_code,
                        code=exc.code,
                        detail=exc.detail,
                        retryable=exc.retryable,
                        provider_status_code=exc.provider_status_code,
                        error_class=exc.error_class,
                        attempt_trace=list(attempt_trace),
                    ) from exc

                _write_provider_runtime_event(
                    db,
                    tenant_id=tenant_id,
                    api_key_id=api_key_id,
                    action_type="PROVIDER_FALLBACK_USED",
                    outcome="success",
                    reason=f"Switching to fallback provider after primary failure: {exc.detail}",
                    provider=fallback_provider_name,
                    model=fallback_resolved_model,
                    event_data={
                        "from_provider": current_provider_name,
                        "from_model": current_model,
                        "to_provider": fallback_provider_name,
                        "to_model": fallback_resolved_model,
                    },
                )
                current_provider_name = fallback_provider_name
                current_model = fallback_resolved_model
                current_runtime_config = fallback_runtime_config
                current_provider_row = fallback_provider_row
                current_provider = _provider(current_provider_name)
                fallback_consumed = True
                attempt_number = 0
                continue

            raise ProviderServiceError(
                status_code=exc.status_code,
                code=exc.code,
                detail=exc.detail,
                retryable=exc.retryable,
                provider_status_code=exc.provider_status_code,
                error_class=exc.error_class,
                attempt_trace=list(attempt_trace),
            ) from exc


def handle_chat_completion(db: Session, api_key: ApiKey, req: dict) -> dict:
    tenant_id = api_key.tenant_id
    requested_model = (req.get("model") or "").strip() or None
    requested_provider = req.get("provider")
    messages = req.get("messages") or []
    max_tokens = req.get("max_tokens")
    temperature = req.get("temperature")
    metadata = req.get("metadata") or {}
    matter_id = metadata.get("matter_id")
    practice_group = metadata.get("practice_group")
    client_name = metadata.get("client_name")
    data_classification = metadata.get("data_classification")
    purpose = metadata.get("purpose")

    prompt_text = "\n".join([m.get("content", "") for m in messages])
    policy = _get_policy(db, tenant_id)
    policy_info = _get_policy_info(db, tenant_id)
    event_metadata: dict[str, Any] = {}
    if data_classification:
        event_metadata["data_classification"] = str(data_classification)[:64]
    if purpose:
        event_metadata["purpose"] = str(purpose)[:80]

    try:
        provider_name, model, runtime_config, provider_config_row = resolve_gateway_provider(
            db,
            tenant_id=tenant_id,
            requested_provider=requested_provider,
            model=requested_model,
        )
    except ProviderPolicyError as e:
        sec = detect_security_signals(prompt_text)
        phi = scan_phi(prompt_text)
        denial_provider = e.provider or ((requested_provider or "").strip().lower() or None)
        denial_model = e.model or requested_model
        denial_event_data = {
            "metadata": {
                **event_metadata,
                "reason_code": e.reason_code,
                "requested_provider": (requested_provider or "").strip().lower() or None,
                "requested_model": requested_model,
            }
        }
        if e.provider_config_id:
            denial_event_data["metadata"]["provider_config_id"] = e.provider_config_id
        _write_audit(
            db,
            tenant_id=tenant_id,
            api_key_id=api_key.id,
            action_type=e.action_type,
            outcome="fail",
            reason=e.detail[:500],
            model=denial_model,
            provider=denial_provider,
            prompt_text=prompt_text,
            response_text="",
            phi_score=phi.score,
            risk_flags=sec.flags,
            severity=sec.severity,
            matter_id=matter_id,
            practice_group=practice_group,
            client_name=client_name,
            store_redacted=bool((policy.get("logging") or {}).get("store_redacted_snippets", False)),
            event_data=denial_event_data,
        )
        raise RequestBlocked(
            status_code=e.status_code,
            block_reason=e.detail[:500],
            flags=sec.flags,
            policy_updated_at=policy_info.get("updated_at"),
            policy_version_id=policy_info.get("version_id"),
            rule="provider_policy",
            reason_code=e.reason_code,
            provider=denial_provider,
            model=denial_model,
            error_code="POLICY_BLOCKED",
        )
    except HTTPException as e:
        sec = detect_security_signals(prompt_text)
        phi = scan_phi(prompt_text)
        _write_audit(
            db,
            tenant_id=tenant_id,
            api_key_id=api_key.id,
            action_type="POLICY_BLOCK",
            outcome="fail",
            reason=str(e.detail)[:500],
            model=requested_model,
            provider=requested_provider,
            prompt_text=prompt_text,
            response_text="",
            phi_score=phi.score,
            risk_flags=sec.flags,
            severity=sec.severity,
            matter_id=matter_id,
            practice_group=practice_group,
            client_name=client_name,
            store_redacted=bool((policy.get("logging") or {}).get("store_redacted_snippets", False)),
            event_data={"metadata": event_metadata} if event_metadata else {},
        )
        raise RequestBlocked(
            status_code=e.status_code,
            block_reason=str(e.detail)[:500],
            flags=sec.flags,
            policy_updated_at=policy_info.get("updated_at"),
            policy_version_id=policy_info.get("version_id"),
            rule="provider_routing",
            provider=(requested_provider or "").strip().lower() or None,
            model=requested_model,
            error_code="VALIDATION_ERROR" if e.status_code < 500 else "PROVIDER_UNAVAILABLE",
            retryable=e.status_code >= 500,
        )
    if provider_config_row is not None:
        event_metadata["provider_config_id"] = provider_config_row.id

    # Preflight policy enforcement
    try:
        enforce_preflight(policy=policy, model=model, prompt_text=prompt_text, max_tokens=max_tokens, metadata=metadata)
    except HTTPException as e:
        sec = detect_security_signals(prompt_text)
        phi = scan_phi(prompt_text)
        phi_cfg = policy.get("phi") or {}
        phi_flags: list[str] = []
        if isinstance(phi_cfg, dict) and phi_cfg.get("flag_on_any_match") is True and (phi.matches or []):
            phi_flags.append("CONFIDENTIAL_DATA_DETECTED")
        combined_flags = sorted(set((sec.flags or []) + phi_flags))
        _write_audit(
            db,
            tenant_id=tenant_id,
            api_key_id=api_key.id,
            action_type="POLICY_BLOCK",
            outcome="fail",
            reason=str(e.detail)[:500],
            model=model,
            provider=None,
            prompt_text=prompt_text,
            response_text="",
            phi_score=phi.score,
            risk_flags=combined_flags,
            severity=sec.severity,
            matter_id=matter_id,
            practice_group=practice_group,
            client_name=client_name,
            store_redacted=bool((policy.get("logging") or {}).get("store_redacted_snippets", False)),
            event_data={"metadata": event_metadata} if event_metadata else {},
        )
        raise RequestBlocked(
            status_code=e.status_code,
            block_reason=str(e.detail)[:500],
            flags=combined_flags,
            policy_updated_at=policy_info.get("updated_at"),
            policy_version_id=policy_info.get("version_id"),
        )
    messages = apply_required_system_prefix(policy=policy, messages=messages)

    # Signals (heuristics)
    sec = detect_security_signals(prompt_text)
    phi = scan_phi(prompt_text)
    phi_cfg = policy.get("phi") or {}
    phi_flags = []
    if isinstance(phi_cfg, dict) and phi_cfg.get("flag_on_any_match") is True and (phi.matches or []):
        phi_flags.append("CONFIDENTIAL_DATA_DETECTED")

    if should_block_prompt_injection(policy=policy, signals=sec):
        combined_flags = sorted(set((sec.flags or []) + (phi_flags or [])))
        _write_audit(
            db,
            tenant_id=tenant_id,
            api_key_id=api_key.id,
            action_type="POLICY_BLOCK",
            outcome="fail",
            reason="Prompt injection suspicion exceeded policy threshold",
            model=model,
            provider=req.get("provider"),
            prompt_text=prompt_text,
            response_text="",
            phi_score=phi.score,
            risk_flags=combined_flags,
            severity=sec.severity,
            matter_id=matter_id,
            practice_group=practice_group,
            client_name=client_name,
            store_redacted=bool((policy.get("logging") or {}).get("store_redacted_snippets", False)),
            event_data={"metadata": event_metadata} if event_metadata else {},
        )
        raise RequestBlocked(
            block_reason="Prompt injection suspicion exceeded policy threshold",
            flags=combined_flags,
            policy_updated_at=policy_info.get("updated_at"),
            policy_version_id=policy_info.get("version_id"),
            rule="security_prompt_injection",
            reason_code="PROMPT_INJECTION_THRESHOLD",
            model=model,
            provider=req.get("provider"),
            security=_security_details(sec),
        )

    if phi_cfg.get("enabled", True):
        threshold = int(phi_cfg.get("threshold_score", 80))
        if phi.score >= threshold and phi_cfg.get("action", "flag") == "block":
            combined_flags = sorted(set((sec.flags or []) + (phi_flags or [])))
            _write_audit(
                db,
                tenant_id=tenant_id,
                api_key_id=api_key.id,
                action_type="PHI_FLAG",
                outcome="fail",
                reason="Confidential-data threshold block",
                model=model,
                provider=req.get("provider"),
                prompt_text=prompt_text,
                response_text="",
                phi_score=phi.score,
                risk_flags=combined_flags,
                severity=sec.severity,
                matter_id=matter_id,
                practice_group=practice_group,
                client_name=client_name,
                store_redacted=bool((policy.get("logging") or {}).get("store_redacted_snippets", False)),
                event_data={"metadata": event_metadata} if event_metadata else {},
            )
            raise RequestBlocked(
                block_reason="Blocked due to confidentiality exposure risk",
                flags=combined_flags,
                policy_updated_at=policy_info.get("updated_at"),
                policy_version_id=policy_info.get("version_id"),
                rule="confidentiality_threshold",
            )

    attempt_trace: list[dict[str, Any]] = []

    try:
        resp, provider_name, model, runtime_config, provider_config_row, attempt_trace = _invoke_provider_with_resilience(
            db,
            tenant_id=tenant_id,
            api_key_id=api_key.id,
            provider_name=provider_name,
            model=model,
            runtime_config=runtime_config,
            provider_config_row=provider_config_row,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if provider_config_row is not None:
            event_metadata["provider_config_id"] = provider_config_row.id
    except HTTPException:
        raise
    except ProviderServiceError as e:
        attempt_trace = list(e.attempt_trace or attempt_trace)
        logger.warning(
            "Provider chat_completions failed",
            extra={"tenant_id": tenant_id, "provider": provider_name, "model": model},
        )
        _write_audit(
            db,
            tenant_id=tenant_id,
            api_key_id=api_key.id,
            action_type="LLM_REQUEST",
            outcome="fail",
            reason=e.detail[:500],
            model=model,
            provider=provider_name,
            prompt_text=prompt_text,
            response_text="",
            phi_score=phi.score,
            risk_flags=sec.flags,
            severity=sec.severity,
            matter_id=matter_id,
            practice_group=practice_group,
            client_name=client_name,
            store_redacted=bool((policy.get("logging") or {}).get("store_redacted_snippets", False)),
            event_data={"metadata": event_metadata, "routing": {"attempts": attempt_trace}},
        )
        raise ApiError(
            status_code=e.status_code,
            code=e.code,
            message="The AI provider did not respond in time." if e.code == "PROVIDER_TIMEOUT" else "The AI provider is currently unavailable.",
            detail=e.detail[:500],
            retryable=e.retryable,
        ) from e
    except Exception as e:
        logger.exception(
            "Provider chat_completions failed",
            extra={"tenant_id": tenant_id, "provider": provider_name, "model": model},
        )
        _write_audit(
            db,
            tenant_id=tenant_id,
            api_key_id=api_key.id,
            action_type="LLM_REQUEST",
            outcome="fail",
            reason=str(e)[:500],
            model=model,
            provider=provider_name,
            prompt_text=prompt_text,
            response_text="",
            phi_score=phi.score,
            risk_flags=sec.flags,
            severity=sec.severity,
            matter_id=matter_id,
            practice_group=practice_group,
            client_name=client_name,
            store_redacted=bool((policy.get("logging") or {}).get("store_redacted_snippets", False)),
            event_data={"metadata": event_metadata, "routing": {"attempts": attempt_trace}},
        )
        raise ApiError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="PROVIDER_UNAVAILABLE",
            detail="Provider request failed",
            retryable=True,
        ) from e

    output_text = resp.content or ""
    out_flags, out_block = evaluate_output_rules(policy=policy, output_text=output_text)
    combined_flags = sorted(set((sec.flags or []) + (phi_flags or []) + (out_flags or [])))

    if out_block:
        _write_audit(
            db,
            tenant_id=tenant_id,
            api_key_id=api_key.id,
            action_type="POLICY_BLOCK",
            outcome="fail",
            reason="Output blocked by policy",
            model=model,
            provider=provider_name,
            prompt_text=prompt_text,
            response_text=output_text,
            phi_score=phi.score,
            risk_flags=combined_flags,
            severity=sec.severity,
            matter_id=matter_id,
            practice_group=practice_group,
            client_name=client_name,
            store_redacted=bool((policy.get("logging") or {}).get("store_redacted_snippets", False)),
            event_data={
                "metadata": event_metadata,
                "routing": {"attempts": attempt_trace},
            },
        )
        raise RequestBlocked(
            block_reason="Output blocked by AI Rules",
            flags=combined_flags,
            policy_updated_at=policy_info.get("updated_at"),
            policy_version_id=policy_info.get("version_id"),
        )

    prompt_tokens = resp.prompt_tokens if resp.prompt_tokens is not None else _estimate_tokens(prompt_text)
    completion_tokens = resp.completion_tokens if resp.completion_tokens is not None else _estimate_tokens(output_text)
    cost = estimate_cost_usd(model=model, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)

    _write_audit(
        db,
        tenant_id=tenant_id,
        api_key_id=api_key.id,
        action_type="LLM_REQUEST",
        outcome="success",
        reason=None,
        model=model,
        provider=provider_name,
        prompt_text=prompt_text,
        response_text=output_text,
        phi_score=phi.score,
        risk_flags=combined_flags,
        severity=sec.severity,
        tokens_prompt=prompt_tokens,
        tokens_completion=completion_tokens,
        cost_usd=cost,
        matter_id=matter_id,
        practice_group=practice_group,
        client_name=client_name,
        store_redacted=bool((policy.get("logging") or {}).get("store_redacted_snippets", False)),
        event_data={
            "metadata": event_metadata,
            "routing": {"attempts": attempt_trace},
        },
    )

    return {
        "id": "chatcmpl_mock",
        "object": "chat.completion",
        "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": output_text}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "total_tokens": prompt_tokens + completion_tokens},
    }


def _write_audit(
    db: Session,
    *,
    tenant_id: str,
    api_key_id: str | None,
    action_type: str,
    outcome: str,
    reason: str | None,
    model: str | None,
    provider: str | None,
    prompt_text: str,
    response_text: str,
    phi_score: int | None,
    risk_flags: list[str] | None,
    severity: str | None,
    matter_id: str | None = None,
    practice_group: str | None = None,
    client_name: str | None = None,
    tokens_prompt: int | None = None,
    tokens_completion: int | None = None,
    cost_usd: Decimal | None = None,
    store_redacted: bool = False,
    event_data: dict | None = None,
) -> None:
    prompt_hash = sha256_text(prompt_text) if prompt_text else None
    response_hash = sha256_text(response_text) if response_text else None
    redacted_prompt = None
    redacted_response = None
    if store_redacted:
        redacted_prompt = (scan_phi(prompt_text).redacted_snippet if prompt_text else None)
        redacted_response = (scan_phi(response_text).redacted_snippet if response_text else None)

    ev = AuditEvent(
        tenant_id=tenant_id,
        api_key_id=api_key_id,
        user_id=None,
        matter_id=str(matter_id)[:120] if matter_id else None,
        practice_group=str(practice_group)[:120] if practice_group else None,
        client_name=str(client_name)[:200] if client_name else None,
        request_id=get_request_id(),
        action_type=action_type,
        outcome=outcome,
        reason=reason,
        model=model,
        provider=provider,
        prompt_hash=prompt_hash,
        response_hash=response_hash,
        redacted_prompt=redacted_prompt,
        redacted_response=redacted_response,
        phi_score=phi_score,
        risk_flags=risk_flags or [],
        severity=severity,
        tokens_prompt=tokens_prompt,
        tokens_completion=tokens_completion,
        cost_usd=cost_usd,
        event_data=event_data or {},
    )
    db.add(ev)
    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Audit write failed", extra={"tenant_id": tenant_id, "model": model, "provider": provider})
        raise

def _maybe_notify_high_severity(db: Session, ev: AuditEvent) -> None:
    try:
        maybe_send_alerts_for_event(db, ev)
    except Exception:
        # Never block the request path on notification issues.
        return
