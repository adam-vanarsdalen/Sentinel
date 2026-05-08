from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from fastapi.testclient import TestClient
import jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.roles import canonical_role
from app.core.security import hash_password
from app.db.models import AuditEvent, Tenant, User


def _mk_tenant(db: Session, tenant_id: str = "t_auth") -> Tenant:
    tenant = Tenant(id=tenant_id, name="Auth Tenant", slug=tenant_id, status="active")
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


def _jwt_for_user(user: User) -> str:
    exp_ts = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expires_minutes)
    return jwt.encode(
        {
            "sub": user.id,
            "role": canonical_role(user.role),
            "tenant_id": user.tenant_id,
            "aud": settings.jwt_audience,
            "iss": settings.jwt_issuer,
            "exp": int(exp_ts.timestamp()),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )


def test_failed_login_response_does_not_reveal_whether_user_exists(client: TestClient, db_session: Session):
    tenant = _mk_tenant(db_session)
    _mk_user(db_session, "u_auth", tenant.id, "user@example.com", "correct-password", "org_admin")

    known = client.post("/auth/login", json={"email": "user@example.com", "password": "wrong-password"})
    unknown = client.post("/auth/login", json={"email": "missing@example.com", "password": "wrong-password"})

    assert known.status_code == status.HTTP_401_UNAUTHORIZED
    assert unknown.status_code == status.HTTP_401_UNAUTHORIZED
    assert known.json()["detail"] == unknown.json()["detail"] == "Invalid credentials"
    assert known.json()["error"]["code"] == unknown.json()["error"]["code"] == "AUTH_REQUIRED"
    assert known.json()["error"]["message"] == unknown.json()["error"]["message"] == "Authentication failed."


def test_login_rate_limit_checks_ip_and_identifier(monkeypatch):
    import app.core.rate_limit as rate_limit

    calls: list[tuple[str, int, int]] = []

    def _record(key: str, limit: int, window_seconds: int = 60) -> bool:
        calls.append((key, limit, window_seconds))
        return True

    monkeypatch.setattr(rate_limit, "_hit", _record)

    rate_limit.enforce_login_rate_limits(
        ip_address="203.0.113.8",
        identifier="User@Example.COM",
        ip_per_minute=3,
        identifier_per_minute=2,
    )

    assert calls[0] == ("login:ip:203.0.113.8", 3, 60)
    identifier_key, identifier_limit, identifier_window = calls[1]
    assert identifier_key.startswith("login:identifier:")
    assert "User@Example.COM" not in identifier_key
    assert identifier_limit == 2
    assert identifier_window == 60


def test_repeated_failed_login_attempts_eventually_return_rate_limited(monkeypatch, client: TestClient):
    import app.api.routes.auth as auth_route

    attempts: dict[tuple[str, str], int] = {}

    def _limited(*, ip_address: str, identifier: str, **kwargs) -> None:
        key = (ip_address, identifier.lower())
        attempts[key] = attempts.get(key, 0) + 1
        if attempts[key] > 2:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")

    monkeypatch.setattr(auth_route, "enforce_login_rate_limits", _limited)

    first = client.post("/auth/login", json={"email": "missing@example.com", "password": "wrong-password"})
    second = client.post("/auth/login", json={"email": "missing@example.com", "password": "wrong-password"})
    third = client.post("/auth/login", json={"email": "missing@example.com", "password": "wrong-password"})

    assert first.status_code == status.HTTP_401_UNAUTHORIZED
    assert second.status_code == status.HTTP_401_UNAUTHORIZED
    assert third.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert third.json()["detail"] == "Rate limit exceeded"
    assert third.json()["error"]["code"] == "RATE_LIMITED"


def test_unrelated_admin_endpoint_is_not_login_rate_limited(monkeypatch, client: TestClient, db_session: Session):
    import app.api.routes.auth as auth_route

    tenant = _mk_tenant(db_session)
    admin = _mk_user(db_session, "admin", tenant.id, "admin@example.com", "correct-password", "org_admin")

    def _blocked(**kwargs) -> None:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")

    monkeypatch.setattr(auth_route, "enforce_login_rate_limits", _blocked)

    response = client.get("/admin/users", headers={"Authorization": f"Bearer {_jwt_for_user(admin)}"})

    assert response.status_code == 200, response.text


def test_failed_and_successful_login_write_audit_events(client: TestClient, db_session: Session):
    tenant = _mk_tenant(db_session)
    user = _mk_user(db_session, "u_auth", tenant.id, "user@example.com", "correct-password", "org_admin")

    failed = client.post("/auth/login", json={"email": "user@example.com", "password": "wrong-password"})
    assert failed.status_code == status.HTTP_401_UNAUTHORIZED

    token = _login(client, "user@example.com", "correct-password")
    assert token

    events = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.tenant_id == tenant.id)
        .order_by(AuditEvent.timestamp.asc())
        .all()
    )
    assert [event.action_type for event in events] == ["AUTH_LOGIN_FAILED", "AUTH_LOGIN_SUCCESS"]
    assert [event.outcome for event in events] == ["fail", "success"]
    assert all(event.user_id == user.id for event in events)
    assert "identifier_hash" in (events[0].event_data or {})
    assert "email" not in (events[0].event_data or {})


def test_admin_created_user_writes_audit_event(client: TestClient, db_session: Session):
    tenant = _mk_tenant(db_session)
    admin = _mk_user(db_session, "admin", tenant.id, "admin@example.com", "correct-password", "org_admin")
    token = _login(client, "admin@example.com", "correct-password")

    response = client.post(
        "/admin/users",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "created@example.com", "role": "reviewer"},
    )

    assert response.status_code == 200, response.text
    event = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.action_type == "ADMIN_USER_CREATE")
        .order_by(AuditEvent.timestamp.desc())
        .first()
    )
    assert event is not None
    assert event.tenant_id == tenant.id
    assert event.user_id == admin.id
    assert event.outcome == "success"
    assert event.event_data["email"] == "created@example.com"
