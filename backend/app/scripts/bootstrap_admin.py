from __future__ import annotations

import os
import uuid

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models import User
from app.db.session import SessionLocal


def main() -> None:
    email = (os.getenv("BOOTSTRAP_ADMIN_EMAIL") or "").strip().lower()
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD") or ""
    if not email or not password:
        raise SystemExit("BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD are required")

    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one_or_none()
        action = "updated"
        if not user:
            user = User(
                id=str(uuid.uuid4()),
                tenant_id=None,
                email=email,
                password_hash=hash_password(password),
                role="super_admin",
                is_active=True,
            )
            db.add(user)
            action = "created"
        else:
            user.tenant_id = None
            user.password_hash = hash_password(password)
            user.role = "super_admin"
            user.is_active = True
            db.add(user)
        db.commit()
        print(f"{action} super_admin {email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
