from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, status
import jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.roles import role_matches
from app.core.request_context import set_tenant_id
from app.core.security import verify_api_key
from app.db.session import get_db
from app.db.models import ApiKey, User


DbDep = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbDep,
    authorization: Annotated[Optional[str], Header()] = None,
    x_tenant_id: Annotated[Optional[str], Header()] = None,
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
        )
    except jwt.exceptions.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    # For super_admin, tenant context can be selected via X-Tenant-Id for admin views.
    if user.role == "super_admin" and x_tenant_id:
        # Validate tenant exists
        from app.db.models import Tenant

        if not db.get(Tenant, x_tenant_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid X-Tenant-Id")
        user = user.with_effective_tenant(x_tenant_id)

    set_tenant_id(user.effective_tenant_id)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: str):
    def _inner(user: Annotated[User, Depends(get_current_user)]) -> User:
        if not role_matches(user.role, roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user

    return _inner


def get_api_key_auth(
    db: DbDep,
    authorization: Annotated[Optional[str], Header()] = None,
    x_api_key: Annotated[Optional[str], Header()] = None,
) -> ApiKey:
    presented = None
    if authorization and authorization.lower().startswith("bearer "):
        presented = authorization.split(" ", 1)[1].strip()
    elif x_api_key:
        presented = x_api_key.strip()

    if not presented:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")

    api_key = verify_api_key(db, presented)
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    set_tenant_id(api_key.tenant_id)
    return api_key


ApiKeyAuth = Annotated[ApiKey, Depends(get_api_key_auth)]
