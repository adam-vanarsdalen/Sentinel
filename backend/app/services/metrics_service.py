from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import AuditEvent


def range_to_window(range: str) -> timedelta:
    if range == "24h":
        return timedelta(hours=24)
    if range == "7d":
        return timedelta(days=7)
    if range == "30d":
        return timedelta(days=30)
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid range")


def compute_overview(*, db: Session, tenant_id: str, range: str = "7d") -> dict:
    now = datetime.now(timezone.utc)
    start = now - range_to_window(range)

    q = db.query(AuditEvent).filter(AuditEvent.tenant_id == tenant_id, AuditEvent.timestamp >= start)

    total_requests = q.filter(AuditEvent.action_type == "LLM_REQUEST").count()
    policy_blocks = q.filter(AuditEvent.action_type == "POLICY_BLOCK").count()
    phi_flagged = q.filter(AuditEvent.action_type == "PHI_FLAG").count()

    avg_phi = (
        db.query(func.avg(AuditEvent.phi_score))
        .filter(AuditEvent.tenant_id == tenant_id, AuditEvent.timestamp >= start, AuditEvent.phi_score.isnot(None))
        .scalar()
    )
    avg_phi_score = float(avg_phi) if avg_phi is not None else 0.0

    cost_sum = (
        db.query(func.coalesce(func.sum(AuditEvent.cost_usd), 0))
        .filter(AuditEvent.tenant_id == tenant_id, AuditEvent.timestamp >= start, AuditEvent.cost_usd.isnot(None))
        .scalar()
    )
    estimated_cost_usd = float(cost_sum or 0)

    top_keys = (
        db.query(AuditEvent.api_key_id, func.count(AuditEvent.id).label("n"))
        .filter(AuditEvent.tenant_id == tenant_id, AuditEvent.timestamp >= start, AuditEvent.api_key_id.isnot(None))
        .group_by(AuditEvent.api_key_id)
        .order_by(func.count(AuditEvent.id).desc())
        .limit(10)
        .all()
    )

    rows = q.filter(AuditEvent.risk_flags.isnot(None)).all()
    flags_counts: dict[str, int] = {}
    severity_counts: dict[str, int] = {"low": 0, "med": 0, "high": 0}
    for r in rows:
        if r.severity in severity_counts:
            severity_counts[r.severity] += 1
        for f in (r.risk_flags or []):
            flags_counts[f] = flags_counts.get(f, 0) + 1

    day = func.date_trunc("day", AuditEvent.timestamp).label("day")
    series = (
        db.query(day, func.count(AuditEvent.id))
        .filter(AuditEvent.tenant_id == tenant_id, AuditEvent.timestamp >= start, AuditEvent.action_type == "LLM_REQUEST")
        .group_by(day)
        .order_by(day)
        .all()
    )
    requests_over_time = [{"t": d.isoformat(), "value": int(n)} for d, n in series]

    cost_series = (
        db.query(day, func.coalesce(func.sum(AuditEvent.cost_usd), 0))
        .filter(AuditEvent.tenant_id == tenant_id, AuditEvent.timestamp >= start, AuditEvent.cost_usd.isnot(None))
        .group_by(day)
        .order_by(day)
        .all()
    )
    cost_over_time = [{"t": d.isoformat(), "value": float(v)} for d, v in cost_series]

    return {
        "range": range,
        "start": start.isoformat(),
        "end": now.isoformat(),
        "cards": {
            "total_requests": total_requests,
            "policy_blocks": policy_blocks,
            "phi_flagged": phi_flagged,
            "avg_phi_score": avg_phi_score,
            "estimated_cost_usd": estimated_cost_usd,
        },
        "top_api_keys": [{"api_key_id": api_key_id, "count": int(n)} for api_key_id, n in top_keys],
        "flags_counts": flags_counts,
        "severity_counts": severity_counts,
        "requests_over_time": requests_over_time,
        "cost_over_time": cost_over_time,
    }


def compute_risk_summary(*, db: Session, tenant_id: str, range: str = "7d") -> dict:
    now = datetime.now(timezone.utc)
    start = now - range_to_window(range)

    base = db.query(AuditEvent).filter(AuditEvent.tenant_id == tenant_id, AuditEvent.timestamp >= start)

    total_ai_requests = base.filter(AuditEvent.action_type == "LLM_REQUEST").count()
    blocked_requests = base.filter(AuditEvent.action_type.in_(["POLICY_BLOCK", "PHI_FLAG"]), AuditEvent.outcome == "fail").count()
    high_exposure = base.filter(AuditEvent.phi_score.isnot(None), AuditEvent.phi_score >= 67).count()

    rows = base.filter(AuditEvent.risk_flags.isnot(None)).all()
    injection_flag = "PROMPT_INJECTION_SUSPECTED"
    injection_attempts_flagged = 0
    for r in rows:
        if injection_flag in (r.risk_flags or []):
            injection_attempts_flagged += 1

    top_matters = (
        db.query(AuditEvent.matter_id, func.count(AuditEvent.id).label("n"))
        .filter(
            AuditEvent.tenant_id == tenant_id,
            AuditEvent.timestamp >= start,
            AuditEvent.action_type == "LLM_REQUEST",
            AuditEvent.matter_id.isnot(None),
        )
        .group_by(AuditEvent.matter_id)
        .order_by(func.count(AuditEvent.id).desc())
        .limit(3)
        .all()
    )

    return {
        "range": range,
        "start": start.isoformat(),
        "end": now.isoformat(),
        "total_ai_requests": int(total_ai_requests),
        "injection_attempts_flagged": int(injection_attempts_flagged),
        "blocked_requests": int(blocked_requests),
        "high_confidentiality_exposure": int(high_exposure),
        "top_matters": [{"matter_id": matter_id, "count": int(n)} for matter_id, n in top_matters],
    }


def compute_cost_summary(*, db: Session, tenant_id: str) -> dict:
    """
    Cost summary derived from `audit_events.cost_usd` for a tenant.

    Time boundaries are computed in UTC:
    - today: from 00:00 UTC
    - this week: from Monday 00:00 UTC
    - this month: from day 1 00:00 UTC
    """
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    base = db.query(AuditEvent).filter(
        AuditEvent.tenant_id == tenant_id,
        AuditEvent.action_type == "LLM_REQUEST",
        AuditEvent.cost_usd.isnot(None),
    )

    def _sum_since(start: datetime) -> float:
        v = (
            db.query(func.coalesce(func.sum(AuditEvent.cost_usd), 0))
            .filter(
                AuditEvent.tenant_id == tenant_id,
                AuditEvent.action_type == "LLM_REQUEST",
                AuditEvent.timestamp >= start,
                AuditEvent.cost_usd.isnot(None),
            )
            .scalar()
        )
        return float(v or 0)

    by_model_rows = (
        base.filter(AuditEvent.timestamp >= month_start, AuditEvent.model.isnot(None))
        .with_entities(
            AuditEvent.model,
            func.coalesce(func.sum(AuditEvent.cost_usd), 0).label("total_usd"),
            func.count(AuditEvent.id).label("requests"),
        )
        .group_by(AuditEvent.model)
        .order_by(func.sum(AuditEvent.cost_usd).desc())
        .all()
    )

    return {
        "as_of": now.isoformat(),
        "today": {"start": today_start.isoformat(), "total_usd": _sum_since(today_start)},
        "this_week": {"start": week_start.isoformat(), "total_usd": _sum_since(week_start)},
        "this_month": {"start": month_start.isoformat(), "total_usd": _sum_since(month_start)},
        "by_model_this_month": [
            {"model": model, "total_usd": float(total_usd or 0), "requests": int(requests or 0)}
            for model, total_usd, requests in by_model_rows
        ],
    }
