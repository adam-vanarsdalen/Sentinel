from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, status
import jwt
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DbDep
from app.core.config import settings
from app.core.roles import canonical_role
from app.core.security import verify_and_update_password
from app.db.models import User

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
def login(req: LoginRequest, db: DbDep) -> TokenResponse:
    # Email is globally unique in this pilot (unique index on `users.email`), so authentication is not
    # tenant-scoped at query time. Tenant context is derived from the authenticated user record.
    user: User | None = db.query(User).filter(User.email == req.email.lower()).one_or_none()
    ok = False
    updated_hash: str | None = None
    if user and user.is_active:
        ok, updated_hash = verify_and_update_password(req.password, user.password_hash)
    if not user or not user.is_active or not ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if updated_hash is not None:
        user.password_hash = updated_hash
        db.add(user)
        db.commit()

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
