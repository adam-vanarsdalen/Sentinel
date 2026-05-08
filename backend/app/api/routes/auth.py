from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, status
import jwt
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DbDep
from app.core.config import settings
from app.core.rate_limit import enforce_login_rate_limits, _hash_identifier
from app.core.roles import canonical_role
from app.core.security import verify_and_update_password
from app.db.models import User
from app.services.audit_log import write_auth_audit_event

router = APIRouter()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    id: str
    # Stored as string; validated on write. Response should not fail if legacy/demo data contains
    # an email that does not pass strict validators.
    email: str
    role: str
    tenant_id: str | None


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: DbDep, request: Request) -> TokenResponse:
    normalized_email = req.email.lower()
    client_ip = request.client.host if request.client else "unknown"
    enforce_login_rate_limits(ip_address=client_ip, identifier=normalized_email)

    # Email is globally unique in this pilot (unique index on `users.email`), so authentication is not
    # tenant-scoped at query time. Tenant context is derived from the authenticated user record.
    user: User | None = db.query(User).filter(User.email == normalized_email).one_or_none()
    ok = False
    updated_hash: str | None = None
    if user and user.is_active:
        ok, updated_hash = verify_and_update_password(req.password, user.password_hash)
    if not user or not user.is_active or not ok:
        if user and user.tenant_id:
            write_auth_audit_event(
                db,
                tenant_id=user.tenant_id,
                user_id=user.id,
                action_type="AUTH_LOGIN_FAILED",
                outcome="fail",
                reason="Invalid credentials",
                event_data={"ip_address": client_ip, "identifier_hash": _hash_identifier(normalized_email)},
            )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if updated_hash is not None:
        user.password_hash = updated_hash
        db.add(user)
        db.commit()

    if user.tenant_id:
        write_auth_audit_event(
            db,
            tenant_id=user.tenant_id,
            user_id=user.id,
            action_type="AUTH_LOGIN_SUCCESS",
            outcome="success",
            reason="Login successful",
            event_data={"ip_address": client_ip},
        )

    exp_ts = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expires_minutes)
    claims = {
        "sub": user.id,
        "role": canonical_role(user.role),
        "tenant_id": user.tenant_id,
        "aud": settings.jwt_audience,
        "iss": settings.jwt_issuer,
        "exp": int(exp_ts.timestamp()),
    }
    token = jwt.encode(claims, settings.jwt_secret, algorithm="HS256")
    return TokenResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
def me(user: CurrentUser) -> MeResponse:
    return MeResponse(id=user.id, email=user.email, role=canonical_role(user.role), tenant_id=user.effective_tenant_id)
