from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import TrialRequest


def test_public_trial_request_creates_row(client: TestClient, db_session: Session):
    r = client.post(
        "/public/trial-requests",
        json={"firm_name": "Anderson & Cole LLP", "contact_name": "Jordan Smith", "email": "jordan@example.com"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body.get("ok") is True
    assert isinstance(body.get("id"), str) and body["id"]

    rows = db_session.query(TrialRequest).all()
    assert len(rows) == 1
    assert rows[0].firm_name == "Anderson & Cole LLP"
    assert rows[0].contact_name == "Jordan Smith"
    assert rows[0].email == "jordan@example.com"
    assert rows[0].status == "pending"
