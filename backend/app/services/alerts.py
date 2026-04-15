from __future__ import annotations

import asyncio
import copy
import logging
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.presets import get_product_name, get_terminology
from app.core.request_context import get_request_id
from app.core.secrets import decrypt_json, encrypt_json
from app.db.models import AuditEvent, Tenant, TenantSettings

logger = logging.getLogger(__name__)

ALERT_EVENT_TYPES = {
    "high_confidentiality_exposure",
    "prompt_injection_detected",
    "policy_blocked",
    "repeated_provider_failures",
    "blocked_request_spike",
}
ALERT_WEBHOOK_FORMATS = {"generic", "slack", "teams"}
SEVERITY_ORDER = {"low": 0, "med": 1, "high": 2}
PROMPT_INJECTION_FLAGS = {"PROMPT_INJECTION_SUSPECTED", "EMBEDDED_INJECTION_SUSPECTED"}

DEFAULT_ALERT_SETTINGS: dict[str, Any] = {
    "phi_threshold": 80,
    "severity_threshold": "med",
    "email_recipients": [],
    "webhook_format": "generic",
    "webhook_secret_blob": None,
    "triggers": {
        "high_confidentiality_exposure": True,
        "prompt_injection_detected": True,
        "policy_blocked": True,
        "repeated_provider_failures": True,
        "blocked_request_spike": False,
    },
    "throttle_window_minutes": 30,
    "provider_failure_threshold": 3,
}


def default_settings_json() -> dict[str, Any]:
    return {
        "storage_mode": "off",
        "retention_days": None,
        "alerts": copy.deepcopy(DEFAULT_ALERT_SETTINGS),
    }


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _sanitize_email_recipients(value: Any) -> list[str]:
    raw_items: list[str]
    if value is None:
        raw_items = []
    elif isinstance(value, str):
        raw_items = [part.strip() for part in value.replace(";", ",").split(",")]
    elif isinstance(value, list):
        raw_items = [str(item or "").strip() for item in value]
    else:
        raise ValueError("email_recipients must be a list of email addresses")

    recipients: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        normalized = item.lower()
        if not normalized:
            continue
        if "@" not in normalized:
            raise ValueError(f"Invalid email recipient: {item}")
        if normalized in seen:
            continue
        recipients.append(normalized)
        seen.add(normalized)
    return recipients


def _normalize_severity(value: Any) -> str:
    severity = str(value or "med").strip().lower()
    if severity not in SEVERITY_ORDER:
        raise ValueError("severity_threshold must be one of: low, med, high")
    return severity


def _normalize_int(value: Any, *, field_name: str, minimum: int, maximum: int, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer") from exc
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"{field_name} must be between {minimum} and {maximum}")
    return parsed


def _normalize_triggers(value: Any) -> dict[str, bool]:
    normalized = copy.deepcopy(DEFAULT_ALERT_SETTINGS["triggers"])
    if value is None:
        return normalized
    if not isinstance(value, dict):
        raise ValueError("triggers must be an object")
    for key, enabled in value.items():
        if key not in ALERT_EVENT_TYPES:
            continue
        normalized[key] = bool(enabled)
    return normalized


def normalize_alert_settings(settings_json: dict[str, Any] | None) -> dict[str, Any]:
    merged = copy.deepcopy(DEFAULT_ALERT_SETTINGS)
    source = settings_json or {}
    stored = source.get("alerts") if isinstance(source, dict) else {}
    if not isinstance(stored, dict):
        stored = {}

    merged["phi_threshold"] = _normalize_int(
        stored.get("phi_threshold"),
        field_name="phi_threshold",
        minimum=0,
        maximum=100,
        default=int(DEFAULT_ALERT_SETTINGS["phi_threshold"]),
    )
    merged["severity_threshold"] = _normalize_severity(stored.get("severity_threshold"))
    merged["throttle_window_minutes"] = _normalize_int(
        stored.get("throttle_window_minutes"),
        field_name="throttle_window_minutes",
        minimum=1,
        maximum=1440,
        default=int(DEFAULT_ALERT_SETTINGS["throttle_window_minutes"]),
    )
    merged["provider_failure_threshold"] = _normalize_int(
        stored.get("provider_failure_threshold"),
        field_name="provider_failure_threshold",
        minimum=2,
        maximum=20,
        default=int(DEFAULT_ALERT_SETTINGS["provider_failure_threshold"]),
    )
    merged["triggers"] = _normalize_triggers(stored.get("triggers"))
    merged["webhook_format"] = (
        str(stored.get("webhook_format") or DEFAULT_ALERT_SETTINGS["webhook_format"]).strip().lower()
    )
    if merged["webhook_format"] not in ALERT_WEBHOOK_FORMATS:
        merged["webhook_format"] = str(DEFAULT_ALERT_SETTINGS["webhook_format"])

    recipients = _sanitize_email_recipients(stored.get("email_recipients"))
    if not recipients:
        recipients = _sanitize_email_recipients(source.get("notification_email"))
    merged["email_recipients"] = recipients

    webhook_secret_blob = stored.get("webhook_secret_blob")
    merged["webhook_secret_blob"] = webhook_secret_blob if isinstance(webhook_secret_blob, str) and webhook_secret_blob.strip() else None
    return merged


def _masked_webhook_hint(blob: str | None) -> str | None:
    if not blob:
        return None
    try:
        url = str(decrypt_json(blob).get("url") or "").strip()
    except Exception:
        return "Configured"
    if not url:
        return "Configured"
    parsed = urlparse(url)
    host = parsed.netloc or parsed.path or "Configured"
    return host


def serialize_alert_settings(tenant_id: str, settings_json: dict[str, Any] | None) -> dict[str, Any]:
    alerts = normalize_alert_settings(settings_json)
    return {
        "tenant_id": tenant_id,
        "alerts": {
            "phi_threshold": alerts["phi_threshold"],
            "severity_threshold": alerts["severity_threshold"],
            "email_recipients": alerts["email_recipients"],
            "webhook_format": alerts["webhook_format"],
            "webhook_configured": bool(alerts["webhook_secret_blob"]),
            "webhook_status": "configured" if alerts["webhook_secret_blob"] else "not_configured",
            "webhook_destination_hint": _masked_webhook_hint(alerts["webhook_secret_blob"]),
            "triggers": alerts["triggers"],
            "throttle_window_minutes": alerts["throttle_window_minutes"],
            "provider_failure_threshold": alerts["provider_failure_threshold"],
        },
    }


def ensure_tenant_settings_row(db: Session, tenant_id: str) -> TenantSettings:
    row = db.get(TenantSettings, tenant_id)
    if row:
        return row
    row = TenantSettings(tenant_id=tenant_id, settings_json=default_settings_json())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_alert_settings(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    payload: dict[str, Any],
) -> TenantSettings:
    row = ensure_tenant_settings_row(db, tenant_id)
    current_settings = dict(row.settings_json or default_settings_json())
    current_alerts = normalize_alert_settings(current_settings)

    email_recipients = _sanitize_email_recipients(payload.get("email_recipients"))
    severity_threshold = _normalize_severity(payload.get("severity_threshold"))
    phi_threshold = _normalize_int(
        payload.get("phi_threshold"),
        field_name="phi_threshold",
        minimum=0,
        maximum=100,
        default=int(current_alerts["phi_threshold"]),
    )
    throttle_window_minutes = _normalize_int(
        payload.get("throttle_window_minutes"),
        field_name="throttle_window_minutes",
        minimum=1,
        maximum=1440,
        default=int(current_alerts["throttle_window_minutes"]),
    )
    provider_failure_threshold = _normalize_int(
        payload.get("provider_failure_threshold"),
        field_name="provider_failure_threshold",
        minimum=2,
        maximum=20,
        default=int(current_alerts["provider_failure_threshold"]),
    )
    triggers = _normalize_triggers(payload.get("triggers"))

    webhook_format = str(payload.get("webhook_format") or current_alerts["webhook_format"]).strip().lower()
    if webhook_format not in ALERT_WEBHOOK_FORMATS:
        raise ValueError("webhook_format must be one of: generic, slack, teams")

    webhook_url = str(payload.get("webhook_url") or "").strip()
    clear_webhook = bool(payload.get("clear_webhook"))
    webhook_secret_blob = current_alerts["webhook_secret_blob"]
    if clear_webhook:
        webhook_secret_blob = None
    elif webhook_url:
        parsed = urlparse(webhook_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("webhook_url must be a valid http or https URL")
        webhook_secret_blob = encrypt_json({"url": webhook_url})

    current_settings.pop("notification_email", None)
    current_settings["alerts"] = {
        "phi_threshold": phi_threshold,
        "severity_threshold": severity_threshold,
        "email_recipients": email_recipients,
        "webhook_format": webhook_format,
        "webhook_secret_blob": webhook_secret_blob,
        "triggers": triggers,
        "throttle_window_minutes": throttle_window_minutes,
        "provider_failure_threshold": provider_failure_threshold,
    }
    row.settings_json = current_settings
    row.updated_by_user_id = user_id
    row.updated_at = _utcnow()
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def alert_history(db: Session, *, tenant_id: str, limit: int = 20) -> list[dict[str, Any]]:
    rows = (
        db.query(AuditEvent)
        .filter(AuditEvent.tenant_id == tenant_id, AuditEvent.action_type.in_(("ALERT_SENT", "ALERT_FAILED")))
        .order_by(AuditEvent.timestamp.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )
    history: list[dict[str, Any]] = []
    for row in rows:
        event_data = row.event_data or {}
        history.append(
            {
                "id": row.id,
                "timestamp": row.timestamp.isoformat(),
                "status": "sent" if row.action_type == "ALERT_SENT" else "failed",
                "trigger_type": event_data.get("trigger_type"),
                "severity": event_data.get("severity"),
                "channel": event_data.get("channel"),
                "destination": event_data.get("destination"),
                "request_id": event_data.get("source_request_id") or row.request_id,
                "reason": row.reason,
            }
        )
    return history


def _write_alert_audit_event(
    db: Session,
    *,
    tenant_id: str,
    action_type: str,
    reason: str | None,
    event_data: dict[str, Any],
) -> None:
    ev = AuditEvent(
        tenant_id=tenant_id,
        user_id=None,
        api_key_id=None,
        request_id=get_request_id(),
        action_type=action_type,
        outcome="success" if action_type == "ALERT_SENT" else "fail",
        reason=(reason or "")[:500] or None,
        event_data=event_data,
    )
    db.add(ev)
    db.commit()


def _severity_meets_threshold(candidate: str, threshold: str) -> bool:
    return SEVERITY_ORDER.get(candidate, 0) >= SEVERITY_ORDER.get(threshold, 0)


def _is_policy_blocked(ev: AuditEvent) -> bool:
    return ev.outcome == "fail" and ev.action_type in {"POLICY_BLOCK", "PHI_FLAG", "MODEL_DENY", "PROVIDER_DENY"}


def _count_recent_provider_failures(
    db: Session,
    *,
    tenant_id: str,
    provider: str,
    since: datetime,
) -> int:
    return (
        db.query(AuditEvent)
        .filter(
            AuditEvent.tenant_id == tenant_id,
            AuditEvent.action_type == "LLM_REQUEST",
            AuditEvent.outcome == "fail",
            AuditEvent.provider == provider,
            AuditEvent.timestamp >= since,
        )
        .count()
    )


def _is_throttled(db: Session, *, tenant_id: str, alert_key: str, throttle_window_minutes: int) -> bool:
    since = _utcnow() - timedelta(minutes=throttle_window_minutes)
    rows = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.tenant_id == tenant_id,
            AuditEvent.action_type == "ALERT_SENT",
            AuditEvent.timestamp >= since,
        )
        .all()
    )
    for row in rows:
        if (row.event_data or {}).get("alert_key") == alert_key:
            return True
    return False


def _event_severity(ev: AuditEvent, *, default: str = "med") -> str:
    severity = str(ev.severity or default).strip().lower()
    return severity if severity in SEVERITY_ORDER else default


def _build_alert_candidates(db: Session, ev: AuditEvent, alerts: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    triggers = alerts["triggers"]
    terminology = get_terminology()
    organization_label = str(terminology.get("organization_singular") or "Organization")
    rules_label = str(terminology.get("rules_label") or "AI Rules")
    product_name = get_product_name()

    if triggers.get("high_confidentiality_exposure") and (ev.phi_score or 0) >= int(alerts["phi_threshold"]):
        candidates.append(
            {
                "trigger_type": "high_confidentiality_exposure",
                "severity": "high",
                "alert_key": "high_confidentiality_exposure",
                "title": "High confidentiality exposure detected",
                "detail": f"A request exceeded the {organization_label.lower()}'s confidentiality exposure alert threshold.",
            }
        )

    if triggers.get("prompt_injection_detected") and any(flag in PROMPT_INJECTION_FLAGS for flag in (ev.risk_flags or [])):
        candidates.append(
            {
                "trigger_type": "prompt_injection_detected",
                "severity": _event_severity(ev, default="med"),
                "alert_key": "prompt_injection_detected",
                "title": "Prompt injection detected",
                "detail": f"{product_name} detected prompt-injection indicators in submitted content.",
            }
        )

    if triggers.get("policy_blocked") and _is_policy_blocked(ev):
        candidates.append(
            {
                "trigger_type": "policy_blocked",
                "severity": _event_severity(ev, default="med"),
                "alert_key": "policy_blocked",
                "title": f"Request blocked by {rules_label}",
                "detail": "A request was blocked by tenant policy, model approval rules, or confidentiality controls.",
            }
        )

    if triggers.get("repeated_provider_failures") and ev.action_type == "LLM_REQUEST" and ev.outcome == "fail" and ev.provider:
        since = _utcnow() - timedelta(minutes=int(alerts["throttle_window_minutes"]))
        failure_count = _count_recent_provider_failures(db, tenant_id=ev.tenant_id, provider=ev.provider, since=since)
        threshold = int(alerts["provider_failure_threshold"])
        if failure_count >= threshold:
            candidates.append(
                {
                    "trigger_type": "repeated_provider_failures",
                    "severity": "high" if failure_count >= threshold * 2 else "med",
                    "alert_key": f"repeated_provider_failures:{ev.provider}",
                    "title": "Repeated provider failures detected",
                    "detail": f"{failure_count} provider failures were recorded for {ev.provider} in the last {alerts['throttle_window_minutes']} minutes.",
                    "provider_failure_count": failure_count,
                }
            )

    return [candidate for candidate in candidates if _severity_meets_threshold(candidate["severity"], alerts["severity_threshold"])]


def _tenant_name(db: Session, tenant_id: str) -> str:
    tenant = db.get(Tenant, tenant_id)
    if tenant and tenant.name:
        return tenant.name
    return tenant_id


def _destination_label(channel: str, alerts: dict[str, Any], recipient: str | None = None) -> str:
    if channel == "email":
        return recipient or "email"
    return _masked_webhook_hint(alerts["webhook_secret_blob"]) or "webhook"


def _build_generic_webhook_payload(*, tenant_name: str, candidate: dict[str, Any], ev: AuditEvent | None) -> dict[str, Any]:
    return {
        "source": get_product_name().lower().replace(" ", "_"),
        "title": candidate["title"],
        "message": candidate["detail"],
        "severity": candidate["severity"],
        "trigger_type": candidate["trigger_type"],
        "tenant_name": tenant_name,
        "request_id": ev.request_id if ev else get_request_id(),
        "provider": ev.provider if ev else None,
        "model": ev.model if ev else None,
        "timestamp": (ev.timestamp if ev else _utcnow()).isoformat(),
    }


def _build_slack_webhook_payload(*, tenant_name: str, candidate: dict[str, Any], ev: AuditEvent | None) -> dict[str, Any]:
    request_id = ev.request_id if ev else get_request_id()
    product_name = get_product_name()
    organization_label = str((get_terminology().get("organization_singular") or "Organization"))
    text = (
        f"*{product_name} alert*: {candidate['title']}\n"
        f"{organization_label}: {tenant_name}\n"
        f"Severity: {candidate['severity']}\n"
        f"Request ID: {request_id or 'n/a'}\n"
        f"{candidate['detail']}"
    )
    return {"text": text}


def _build_teams_webhook_payload(*, tenant_name: str, candidate: dict[str, Any], ev: AuditEvent | None) -> dict[str, Any]:
    request_id = ev.request_id if ev else get_request_id()
    organization_label = str((get_terminology().get("organization_singular") or "Organization"))
    return {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "summary": candidate["title"],
        "themeColor": "C0392B" if candidate["severity"] == "high" else "D35400",
        "title": candidate["title"],
        "sections": [
            {
                "facts": [
                    {"name": organization_label, "value": tenant_name},
                    {"name": "Severity", "value": candidate["severity"]},
                    {"name": "Request ID", "value": request_id or "n/a"},
                ],
                "text": candidate["detail"],
            }
        ],
    }


def _build_webhook_payload(*, webhook_format: str, tenant_name: str, candidate: dict[str, Any], ev: AuditEvent | None) -> dict[str, Any]:
    if webhook_format == "slack":
        return _build_slack_webhook_payload(tenant_name=tenant_name, candidate=candidate, ev=ev)
    if webhook_format == "teams":
        return _build_teams_webhook_payload(tenant_name=tenant_name, candidate=candidate, ev=ev)
    return _build_generic_webhook_payload(tenant_name=tenant_name, candidate=candidate, ev=ev)


async def _send_email_async(
    *,
    msg: EmailMessage,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str | None,
    smtp_password: str | None,
) -> None:
    import aiosmtplib

    use_tls = smtp_port == 465
    start_tls = False if use_tls else None
    await aiosmtplib.send(
        msg,
        hostname=smtp_host,
        port=smtp_port,
        username=smtp_user,
        password=smtp_password,
        use_tls=use_tls,
        start_tls=start_tls,
        timeout=3,
    )


def _deliver_email(*, recipient: str, tenant_name: str, candidate: dict[str, Any], ev: AuditEvent | None) -> None:
    smtp_host = settings.smtp_host
    if not smtp_host:
        raise RuntimeError("SMTP is not configured.")
    smtp_port = int(settings.smtp_port or 587)
    smtp_user = settings.smtp_user
    smtp_password = settings.smtp_password
    if smtp_user and not smtp_password:
        raise RuntimeError("SMTP password is not configured.")

    msg = EmailMessage()
    msg["To"] = recipient
    product_name = get_product_name()
    organization_label = str((get_terminology().get("organization_singular") or "Organization"))
    msg["From"] = smtp_user or "sentinel@localhost"
    msg["Subject"] = f"{product_name} alert: {candidate['title']}"
    msg.set_content(
        "\n".join(
            [
                f"{organization_label}: {tenant_name}",
                f"Severity: {candidate['severity']}",
                f"Trigger: {candidate['trigger_type']}",
                f"Request ID: {(ev.request_id if ev else get_request_id()) or 'n/a'}",
                f"Provider: {(ev.provider if ev else None) or 'n/a'}",
                f"Model: {(ev.model if ev else None) or 'n/a'}",
                f"Timestamp: {(ev.timestamp if ev else _utcnow()).isoformat()}",
                "",
                candidate["detail"],
            ]
        )
    )
    asyncio.run(
        _send_email_async(
            msg=msg,
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            smtp_user=smtp_user,
            smtp_password=smtp_password,
        )
    )


def _deliver_webhook(*, alerts: dict[str, Any], tenant_name: str, candidate: dict[str, Any], ev: AuditEvent | None) -> None:
    blob = alerts["webhook_secret_blob"]
    if not blob:
        raise RuntimeError("Webhook is not configured.")
    webhook_url = str(decrypt_json(blob).get("url") or "").strip()
    if not webhook_url:
        raise RuntimeError("Webhook is not configured.")
    payload = _build_webhook_payload(
        webhook_format=alerts["webhook_format"],
        tenant_name=tenant_name,
        candidate=candidate,
        ev=ev,
    )
    with httpx.Client(timeout=3.0) as client:
        response = client.post(webhook_url, json=payload)
        response.raise_for_status()


def _delivery_targets(alerts: dict[str, Any]) -> list[dict[str, str]]:
    targets: list[dict[str, str]] = []
    for recipient in alerts["email_recipients"]:
        targets.append({"channel": "email", "destination": recipient})
    if alerts["webhook_secret_blob"]:
        targets.append({"channel": "webhook", "destination": _masked_webhook_hint(alerts["webhook_secret_blob"]) or "webhook"})
    return targets


def _deliver_alert_candidate(
    db: Session,
    *,
    tenant_id: str,
    tenant_name: str,
    alerts: dict[str, Any],
    candidate: dict[str, Any],
    ev: AuditEvent | None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for target in _delivery_targets(alerts):
        channel = target["channel"]
        destination = target["destination"]
        try:
            if channel == "email":
                _deliver_email(
                    recipient=destination,
                    tenant_name=tenant_name,
                    candidate=candidate,
                    ev=ev,
                )
            else:
                _deliver_webhook(alerts=alerts, tenant_name=tenant_name, candidate=candidate, ev=ev)
            _write_alert_audit_event(
                db,
                tenant_id=tenant_id,
                action_type="ALERT_SENT",
                reason=candidate["detail"],
                event_data={
                    "trigger_type": candidate["trigger_type"],
                    "severity": candidate["severity"],
                    "channel": channel,
                    "destination": destination,
                    "alert_key": candidate["alert_key"],
                    "source_audit_event_id": ev.id if ev else None,
                    "source_request_id": ev.request_id if ev else get_request_id(),
                },
            )
            results.append({"channel": channel, "destination": destination, "status": "sent"})
        except Exception as exc:
            logger.warning(
                "Alert delivery failed",
                extra={"tenant_id": tenant_id, "request_id": ev.request_id if ev else get_request_id()},
                exc_info=True,
            )
            _write_alert_audit_event(
                db,
                tenant_id=tenant_id,
                action_type="ALERT_FAILED",
                reason=str(exc)[:500],
                event_data={
                    "trigger_type": candidate["trigger_type"],
                    "severity": candidate["severity"],
                    "channel": channel,
                    "destination": destination,
                    "alert_key": candidate["alert_key"],
                    "source_audit_event_id": ev.id if ev else None,
                    "source_request_id": ev.request_id if ev else get_request_id(),
                },
            )
            results.append({"channel": channel, "destination": destination, "status": "failed", "error": str(exc)})
    return results


def maybe_send_alerts_for_event(db: Session, ev: AuditEvent) -> list[dict[str, Any]]:
    row = db.get(TenantSettings, ev.tenant_id)
    alerts = normalize_alert_settings(row.settings_json if row else None)
    if not alerts["email_recipients"] and not alerts["webhook_secret_blob"]:
        return []

    candidates = _build_alert_candidates(db, ev, alerts)
    if not candidates:
        return []

    tenant_name = _tenant_name(db, ev.tenant_id)
    results: list[dict[str, Any]] = []
    for candidate in candidates:
        if _is_throttled(
            db,
            tenant_id=ev.tenant_id,
            alert_key=candidate["alert_key"],
            throttle_window_minutes=int(alerts["throttle_window_minutes"]),
        ):
            continue
        results.extend(
            _deliver_alert_candidate(
                db,
                tenant_id=ev.tenant_id,
                tenant_name=tenant_name,
                alerts=alerts,
                candidate=candidate,
                ev=ev,
            )
        )
    return results


def send_test_alert(db: Session, *, tenant_id: str) -> dict[str, Any]:
    row = db.get(TenantSettings, tenant_id)
    alerts = normalize_alert_settings(row.settings_json if row else None)
    if not alerts["email_recipients"] and not alerts["webhook_secret_blob"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Configure at least one email recipient or webhook before sending a test alert.",
        )

    tenant_name = _tenant_name(db, tenant_id)
    candidate = {
        "trigger_type": "test_alert",
        "severity": alerts["severity_threshold"],
        "alert_key": f"test_alert:{_utcnow().isoformat()}",
        "title": "Test governance alert",
        "detail": f"This is an organization-admin initiated {get_product_name()} test alert.",
    }
    results = _deliver_alert_candidate(db, tenant_id=tenant_id, tenant_name=tenant_name, alerts=alerts, candidate=candidate, ev=None)
    return {
        "ok": any(item["status"] == "sent" for item in results),
        "results": results,
    }
