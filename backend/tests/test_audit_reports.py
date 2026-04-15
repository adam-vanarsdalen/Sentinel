from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models import AuditEvent, Tenant, User


def _mk_tenant(db: Session, tenant_id: str, name: str) -> Tenant:
    tenant = Tenant(id=tenant_id, name=name, slug=name.lower().replace(" ", "-"), status="active")
    db.add(tenant)
    db.commit()
    return tenant


def _mk_user(db: Session, user_id: str, tenant_id: str | None, email: str, password: str, role: str) -> User:
    user = User(
        id=user_id,
        tenant_id=tenant_id,
        email=email.lower(),
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_audit_report_is_tenant_scoped(client: TestClient, db_session: Session):
    tenant_a = _mk_tenant(db_session, "t_report_a", "Anderson & Cole LLP")
    tenant_b = _mk_tenant(db_session, "t_report_b", "Barton Legal")
    _mk_user(db_session, "u_report_a", tenant_a.id, "auditor-a@example.com", "pw12345!", "auditor")
    _mk_user(db_session, "u_report_b", tenant_b.id, "auditor-b@example.com", "pw12345!", "auditor")

    db_session.add_all(
        [
            AuditEvent(
                tenant_id=tenant_a.id,
                user_id="u_report_a",
                request_id="req-a-1",
                action_type="LLM_REQUEST",
                outcome="success",
                matter_id="MAT-A-001",
                practice_group="Corporate",
                risk_flags=["PROMPT_INJECTION_SUSPECTED"],
            ),
            AuditEvent(
                tenant_id=tenant_b.id,
                user_id="u_report_b",
                request_id="req-b-1",
                action_type="POLICY_BLOCK",
                outcome="fail",
                matter_id="MAT-B-009",
                practice_group="Litigation",
                reason="Blocked by AI Rules",
            ),
        ]
    )
    db_session.commit()

    token_a = _login(client, "auditor-a@example.com", "pw12345!")
    response = client.get("/admin/audit-events/report.html", headers={"Authorization": f"Bearer {token_a}"})
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/html")
    html = response.text
    assert "Anderson &amp; Cole LLP" in html
    assert "MAT-A-001" in html
    assert "MAT-B-009" not in html
    assert "audit-report-v1" in html


def test_audit_report_respects_matter_filter(client: TestClient, db_session: Session):
    tenant = _mk_tenant(db_session, "t_report_filter", "Filter Firm")
    _mk_user(db_session, "u_report_filter", tenant.id, "filter-auditor@example.com", "pw12345!", "auditor")
    db_session.add_all(
        [
            AuditEvent(
                tenant_id=tenant.id,
                user_id="u_report_filter",
                request_id="req-filter-1",
                action_type="LLM_REQUEST",
                outcome="success",
                matter_id="MAT-2026-0142",
                practice_group="Corporate",
            ),
            AuditEvent(
                tenant_id=tenant.id,
                user_id="u_report_filter",
                request_id="req-filter-2",
                action_type="POLICY_BLOCK",
                outcome="fail",
                matter_id="MAT-2026-0999",
                practice_group="Employment",
                reason="Blocked by AI Rules",
            ),
        ]
    )
    db_session.commit()

    token = _login(client, "filter-auditor@example.com", "pw12345!")
    response = client.get(
        "/admin/audit-events/report.html",
        params={"matter_query": "0142"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    html = response.text
    assert "MAT-2026-0142" in html
    assert "MAT-2026-0999" not in html
    assert "Total events" in html
    assert ">1<" in html or "1</div>" in html


def test_viewer_cannot_generate_audit_report(client: TestClient, db_session: Session):
    tenant = _mk_tenant(db_session, "t_report_rbac", "RBAC Firm")
    _mk_user(db_session, "u_report_viewer", tenant.id, "viewer@example.com", "pw12345!", "viewer")
    token = _login(client, "viewer@example.com", "pw12345!")

    response = client.get("/admin/audit-events/report.html", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403, response.text
