from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.models import Tenant, User

from app.db.session import SessionLocal


def _resolve_default_tenant(db: Session) -> Tenant:
    tenant = (
        db.query(Tenant)
        .filter(Tenant.settings_json["default_demo"].as_boolean() == True)  # noqa: E712
        .order_by(Tenant.created_at.asc())
        .first()
    )
    if tenant:
        return tenant
    tenant = db.query(Tenant).filter(Tenant.slug == "northwind-operations").one_or_none()
    if tenant:
        return tenant

    now = datetime.now(timezone.utc)
    tenant = Tenant(
        id=str(uuid.uuid4()),
        name="Northwind Operations",
        slug="northwind-operations",
        status="active",
        created_at=now,
        updated_at=now,
        settings_json={"preset_id": "general", "is_demo": True, "default_demo": True},
    )
    db.add(tenant)
    db.flush()
    return tenant


def main() -> None:
    email = (os.getenv("BOOTSTRAP_TENANT_ADMIN_EMAIL") or settings.demo_tenant_admin_email).strip().lower()
    password = os.getenv("BOOTSTRAP_TENANT_ADMIN_PASSWORD") or settings.demo_tenant_admin_password
    if not email or not password:
        raise SystemExit("BOOTSTRAP_TENANT_ADMIN_EMAIL and BOOTSTRAP_TENANT_ADMIN_PASSWORD are required")

    db: Session = SessionLocal()
    try:
        tenant = _resolve_default_tenant(db)

        user = db.query(User).filter(User.email == email).one_or_none()
        action = "updated"
        if not user:
            user = User(
                id=str(uuid.uuid4()),
                tenant_id=tenant.id,
                email=email,
                password_hash=hash_password(password),
                role="org_admin",
                is_active=True,
            )
            db.add(user)
            action = "created"
        else:
            user.tenant_id = tenant.id
            user.password_hash = hash_password(password)
            user.role = "org_admin"
            user.is_active = True
            db.add(user)
        db.commit()
        print(f"{action} org_admin {email} in tenant {tenant.slug}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
