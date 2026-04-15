from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models import AuditEvent, Tenant, User


def test_cost_summary_returns_period_totals_and_by_model(client: TestClient, db_session: Session):
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    tenant = Tenant(id="t_cost", name="Tenant Cost", slug="tenant-cost", status="active")
    db_session.add(tenant)
    db_session.add(
        User(
            id="u_cost",
            tenant_id=tenant.id,
            email="admin-cost@example.com",
            password_hash=hash_password("pw12345!"),
            role="tenant_admin",
            is_active=True,
        )
    )
    db_session.commit()

    # Events:
    # - in this month/week/today: 1.00 (mock)
    # - in this month/week but not today: 2.00 (gpt-4)
    # - in this month but not this week: 3.00 (mock)
    # - outside this month: 4.00 (ignored for month)
    events = [
        AuditEvent(
            tenant_id=tenant.id,
            action_type="LLM_REQUEST",
            outcome="success",
            model="mock",
            provider="mock",
            cost_usd=Decimal("1.00"),
            timestamp=today_start + timedelta(hours=1),
        ),
        AuditEvent(
            tenant_id=tenant.id,
            action_type="LLM_REQUEST",
            outcome="success",
            model="gpt-4",
            provider="openai",
            cost_usd=Decimal("2.00"),
            timestamp=today_start - timedelta(days=1),
        ),
        AuditEvent(
            tenant_id=tenant.id,
            action_type="LLM_REQUEST",
            outcome="success",
            model="mock",
            provider="mock",
            cost_usd=Decimal("3.00"),
            timestamp=month_start + timedelta(days=1),
        ),
        AuditEvent(
            tenant_id=tenant.id,
            action_type="LLM_REQUEST",
            outcome="success",
            model="mock",
            provider="mock",
            cost_usd=Decimal("4.00"),
            timestamp=month_start - timedelta(days=1),
        ),
    ]
    db_session.add_all(events)
    db_session.commit()

    r_login = client.post("/auth/login", json={"email": "admin-cost@example.com", "password": "pw12345!"})
    assert r_login.status_code == 200, r_login.text
    token = r_login.json()["access_token"]

    r = client.get("/admin/metrics/cost-summary", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    body = r.json()

    assert "as_of" in body
    assert body["today"]["start"].startswith(today_start.isoformat()[:10])
    assert body["this_week"]["start"].startswith(week_start.isoformat()[:10])
    assert body["this_month"]["start"].startswith(month_start.isoformat()[:10])

    today_total = body["today"]["total_usd"]
    week_total = body["this_week"]["total_usd"]
    month_total = body["this_month"]["total_usd"]

    assert abs(today_total - 1.0) < 1e-9
    # week includes any rows whose timestamps fall on or after the computed week start.
    expected_week = 1.0
    if (today_start - timedelta(days=1)) >= week_start:
        expected_week += 2.0
    if (month_start + timedelta(days=1)) >= week_start:
        expected_week += 3.0
    if (month_start - timedelta(days=1)) >= week_start:
        expected_week += 4.0
    assert abs(week_total - expected_week) < 1e-9

    assert abs(month_total - (1.0 + 2.0 + 3.0)) < 1e-9

    by_model = {row["model"]: row for row in body.get("by_model_this_month", [])}
    assert abs(by_model["mock"]["total_usd"] - (1.0 + 3.0)) < 1e-9
    assert abs(by_model["gpt-4"]["total_usd"] - 2.0) < 1e-9
