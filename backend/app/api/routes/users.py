from __future__ import annotations

import secrets
import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import func

from app.api.deps import DbDep, require_role
from app.core.roles import normalize_assignable_role, storage_values_for_role
from app.core.security import hash_password
from app.db.models import Tenant, User
from app.services.audit_log import write_admin_audit_event

router = APIRouter()

UsersReader = Annotated[User, Depends(require_role("super_admin", "org_admin", "compliance_admin", "operator", "reviewer", "auditor"))]
UsersWriter = Annotated[User, Depends(require_role("super_admin", "org_admin"))]


class UserListItem(BaseModel):
    id: str
    # Stored as string; validated on write. Response should not fail if legacy/demo data contains
    # an email that does not pass strict validators.
    email: str
    role: str
    tenant_id: str | None
    is_active: bool
    created_at: str


class CreateUserRequest(BaseModel):
    email: EmailStr
    role: str
    tenant_id: Optional[str] = None  # super_admin can set


class CreateUserResponse(BaseModel):
    user: UserListItem
    temp_password: str


class UpdateRoleRequest(BaseModel):
    role: str


@router.get("", response_model=list[UserListItem])
def list_users(db: DbDep, user: UsersReader) -> list[UserListItem]:
    tenant_id = user.effective_tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")
    q = db.query(User).filter(User.tenant_id == tenant_id)
    rows = q.order_by(User.created_at.desc()).limit(200).all()
    return [r.to_list_item() for r in rows]


@router.post("", response_model=CreateUserResponse)
def create_user(req: CreateUserRequest, db: DbDep, user: UsersWriter) -> CreateUserResponse:
    tenant_id = user.effective_tenant_id
    target_tenant_id = tenant_id
    if user.role == "super_admin" and req.tenant_id is not None:
        # Platform super-admins can explicitly create users for any tenant by specifying `tenant_id`.
        target_tenant_id = req.tenant_id
    if not target_tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")
    if not db.get(Tenant, target_tenant_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant_id")

    # Emails are globally unique in this pilot (unique index on `users.email`), so this check is intentionally
    # cross-tenant. Keep it minimal by selecting only the ID.
    if db.query(User.id).filter(User.email == req.email.lower()).scalar() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")

    temp_password = secrets.token_urlsafe(12)
    normalized_role = normalize_assignable_role(req.role)
    new_user = User(
        id=str(uuid.uuid4()),
        tenant_id=target_tenant_id,
        email=req.email.lower(),
        password_hash=hash_password(temp_password),
        role=normalized_role,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    write_admin_audit_event(
        db,
        tenant_id=target_tenant_id,
        user_id=user.id,
        action_type="USER_CREATE",
        outcome="success",
        reason="User created",
        event_data={"created_user_id": new_user.id, "email": new_user.email, "role": new_user.role},
    )
    return CreateUserResponse(user=new_user.to_list_item(), temp_password=temp_password)


@router.put("/{user_id}/role", response_model=UserListItem)
def update_role(user_id: str, req: UpdateRoleRequest, db: DbDep, user: UsersWriter) -> UserListItem:
    tenant_id = user.effective_tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")
    row = db.query(User).filter(User.id == user_id, User.tenant_id == tenant_id).one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    old_role = row.role
    row.role = normalize_assignable_role(req.role)
    db.add(row)
    db.commit()
    db.refresh(row)
    write_admin_audit_event(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        action_type="USER_ROLE_UPDATE",
        outcome="success",
        reason="User role updated",
        event_data={"target_user_id": row.id, "old_role": old_role, "new_role": row.role},
    )
    return row.to_list_item()


@router.delete("/{user_id}", response_model=UserListItem)
def deactivate_user(user_id: str, db: DbDep, user: UsersWriter) -> UserListItem:
    """
    "Delete" in the UI is implemented as a safe soft-delete (deactivation) so audit trails remain intact.
    """
    tenant_id = user.effective_tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")

    row = db.query(User).filter(User.id == user_id, User.tenant_id == tenant_id).one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if row.id == user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate yourself")

    if row.role in storage_values_for_role("org_admin") and row.is_active:
        active_admins = (
            db.query(func.count(User.id))
            .filter(User.tenant_id == tenant_id, User.role.in_(storage_values_for_role("org_admin")), User.is_active.is_(True))
            .scalar()
            or 0
        )
        if int(active_admins) <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot deactivate the last active org_admin for this organization",
            )

    if row.is_active:
        row.is_active = False
        db.add(row)
        db.commit()
        db.refresh(row)
        write_admin_audit_event(
            db,
            tenant_id=tenant_id,
            user_id=user.id,
            action_type="USER_DEACTIVATE",
            outcome="success",
            reason="User deactivated",
            event_data={"target_user_id": row.id, "email": row.email},
        )
    return row.to_list_item()
