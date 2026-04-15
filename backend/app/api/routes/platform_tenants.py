from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import DbDep, require_role
from app.core.presets import get_default_policy_template_id
from app.core.slug import normalize_slug, slugify_name, validate_slug
from app.db.models import Tenant, TenantPolicy, User
from app.services.audit_log import write_admin_audit_event
from app.services.metrics_service import compute_overview
from app.services.policy import DEFAULT_POLICY
from app.services.policy_templates import get_policy_template

router = APIRouter()

PlatformSuperAdmin = Annotated[User, Depends(require_role("super_admin"))]

TenantStatus = Literal["active", "suspended", "archived"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TenantCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(default=None, description="Optional. URL-safe: [a-z0-9]+(?:-[a-z0-9]+)*")
    status: TenantStatus = "active"


class TenantUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(default=None, description="URL-safe: [a-z0-9]+(?:-[a-z0-9]+)*")
    status: TenantStatus | None = None


class TenantListResponse(BaseModel):
    items: list[dict]
    total: int
    page: int
    page_size: int


def _ensure_unique_slug(db: Session, *, base_slug: str) -> str:
    slug = base_slug
    i = 2
    while db.query(Tenant).filter(Tenant.slug == slug).count() > 0:
        slug = f"{base_slug}-{i}"
        i += 1
    return slug


@router.get("", response_model=TenantListResponse)
def list_platform_tenants(
    db: DbDep,
    user: PlatformSuperAdmin,
    query: str | None = None,
    status_filter: TenantStatus | None = Query(default=None, alias="status"),
    page: int = 1,
    page_size: int = 20,
    sort: str = "created_at_desc",
) -> TenantListResponse:
    page = max(1, page)
    page_size = max(1, min(100, page_size))

    q = db.query(Tenant)
    if query:
        like = f"%{query.strip().lower()}%"
        q = q.filter((Tenant.name.ilike(like)) | (Tenant.slug.ilike(like)))
    if status_filter:
        q = q.filter(Tenant.status == status_filter)

    total = q.count()

    if sort == "created_at_desc":
        q = q.order_by(Tenant.created_at.desc())
    elif sort == "created_at_asc":
        q = q.order_by(Tenant.created_at.asc())
    elif sort == "name_asc":
        q = q.order_by(Tenant.name.asc())
    elif sort == "name_desc":
        q = q.order_by(Tenant.name.desc())
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid sort")

    items = q.offset((page - 1) * page_size).limit(page_size).all()
    return TenantListResponse(items=[t.to_platform_dict() for t in items], total=total, page=page, page_size=page_size)


@router.post("", response_model=dict, status_code=201)
def create_platform_tenant(db: DbDep, user: PlatformSuperAdmin, req: TenantCreateRequest) -> dict:
    slug = normalize_slug(req.slug) if req.slug else slugify_name(req.name)
    if not slug:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Slug is required")
    try:
        validate_slug(slug)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    if not req.slug:
        slug = _ensure_unique_slug(db, base_slug=slug)
    else:
        if db.query(Tenant).filter(Tenant.slug == slug).count() > 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug already exists")

    tenant = Tenant(
        id=str(uuid.uuid4()),
        name=req.name.strip(),
        slug=slug,
        status=req.status,
        created_at=_utcnow(),
        updated_at=_utcnow(),
        settings_json=None,
    )
    db.add(tenant)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        msg = str(e.orig) if getattr(e, "orig", None) else "Integrity error"
        if "uq_tenants_slug" in msg or "tenants.slug" in msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug already exists") from e
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant") from e

    write_admin_audit_event(
        db,
        tenant_id=tenant.id,
        user_id=user.id,
        action_type="TENANT_CREATE",
        outcome="success",
        reason="Tenant created",
        event_data={
            "actor_role": user.role,
            "new": {"name": tenant.name, "slug": tenant.slug, "status": tenant.status},
            "policy_template_id": get_default_policy_template_id(),
        },
    )

    # Initialize a safe default policy for new firms so governance is ready on first login.
    # This is tenant-scoped and does not change any existing firms.
    if not db.get(TenantPolicy, tenant.id):
        default_template_id = get_default_policy_template_id()
        tpl = get_policy_template(default_template_id)
        db.add(TenantPolicy(tenant_id=tenant.id, policy_json=(tpl["policy_json"] if tpl else DEFAULT_POLICY)))
        db.commit()

    return {"tenant": tenant.to_platform_dict()}


@router.get("/{tenant_id}", response_model=dict)
def get_platform_tenant(db: DbDep, user: PlatformSuperAdmin, tenant_id: str) -> dict:
    t = db.get(Tenant, tenant_id)
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return {"tenant": {**t.to_platform_dict(), "settings_json": t.settings_json or {}}}


@router.patch("/{tenant_id}", response_model=dict)
def update_platform_tenant(db: DbDep, user: PlatformSuperAdmin, tenant_id: str, req: TenantUpdateRequest) -> dict:
    t = db.get(Tenant, tenant_id)
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    old = {"name": t.name, "slug": t.slug, "status": t.status}
    changed: dict = {}

    if req.name is not None:
        t.name = req.name.strip()
        changed["name"] = t.name

    if req.slug is not None:
        slug = normalize_slug(req.slug)
        try:
            validate_slug(slug)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        if slug != t.slug and db.query(Tenant).filter(Tenant.slug == slug).count() > 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug already exists")
        t.slug = slug
        changed["slug"] = slug

    if req.status is not None:
        t.status = req.status
        changed["status"] = t.status

    if not changed:
        return {"tenant": t.to_platform_dict()}

    t.updated_at = _utcnow()
    db.add(t)
    db.commit()
    db.refresh(t)

    action_type = "TENANT_STATUS_CHANGE" if "status" in changed and len(changed) == 1 else "TENANT_UPDATE"
    write_admin_audit_event(
        db,
        tenant_id=t.id,
        user_id=user.id,
        action_type=action_type,
        outcome="success",
        reason="Tenant updated",
        event_data={"actor_role": user.role, "old": old, "new": {**old, **changed}},
    )

    return {"tenant": t.to_platform_dict()}


@router.post("/{tenant_id}/switch", response_model=dict)
def switch_platform_tenant(db: DbDep, user: PlatformSuperAdmin, tenant_id: str) -> dict:
    t = db.get(Tenant, tenant_id)
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    if t.status != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant is not active")

    write_admin_audit_event(
        db,
        tenant_id=t.id,
        user_id=user.id,
        action_type="TENANT_SWITCH",
        outcome="success",
        reason="Switched tenant context",
        event_data={"actor_role": user.role, "tenant": {"id": t.id, "name": t.name, "slug": t.slug}},
    )
    return {"current_tenant": t.to_platform_dict()}


@router.get("/{tenant_id}/summary", response_model=dict)
def tenant_summary(db: DbDep, user: PlatformSuperAdmin, tenant_id: str, range: str = "7d") -> dict:
    t = db.get(Tenant, tenant_id)
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return {"tenant": t.to_platform_dict(), "summary": compute_overview(db=db, tenant_id=tenant_id, range=range)}
