from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models import AuditEvent, Tenant, User


def test_audit_export_pdf_returns_pdf(client: TestClient, db_session: Session):
    tenant = Tenant(id="t_pdf", name="Tenant PDF", slug="tenant-pdf", status="active")
    user = User(
        id="u_pdf",
        tenant_id=tenant.id,
        email="auditor@example.com",
        password_hash=hash_password("pw12345!"),
        role="auditor",
        is_active=True,
    )
    db_session.add_all([tenant, user])
    db_session.commit()

    db_session.add(
        AuditEvent(
            tenant_id=tenant.id,
            user_id=user.id,
            action_type="LLM_REQUEST",
            outcome="success",
            model="mock",
            provider="mock",
            risk_flags=["PROMPT_INJECTION_SUSPECTED"],
            phi_score=10,
            severity="med",
            tokens_prompt=10,
            tokens_completion=5,
            cost_usd=Decimal("0.00"),
        )
    )
    db_session.commit()

    r_login = client.post("/auth/login", json={"email": "auditor@example.com", "password": "pw12345!"})
    assert r_login.status_code == 200, r_login.text
    token = r_login.json()["access_token"]

    r = client.get("/admin/audit-events/export.pdf", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert r.content[:4] == b"%PDF"

