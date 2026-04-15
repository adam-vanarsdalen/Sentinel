"""Tenant slug/status fields

Revision ID: 0005_tenant_slug_status
Revises: 0004_audit_request_id
Create Date: 2026-02-26
"""

from __future__ import annotations

import re

from alembic import op
import sqlalchemy as sa


revision = "0005_tenant_slug_status"
down_revision = "0004_audit_request_id"
branch_labels = None
depends_on = None


_slug_re = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    s = (name or "").strip().lower()
    s = _slug_re.sub("-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "firm"


def upgrade() -> None:
    op.add_column("tenants", sa.Column("slug", sa.String(length=120), nullable=True))
    op.add_column("tenants", sa.Column("status", sa.String(length=20), nullable=True))
    op.add_column("tenants", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.add_column("tenants", sa.Column("settings_json", sa.JSON(), nullable=True))

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, name FROM tenants ORDER BY created_at ASC")).fetchall()
    seen: set[str] = set()
    for tenant_id, name in rows:
        base = _slugify(name)
        slug = base
        i = 2
        while slug in seen:
            slug = f"{base}-{i}"
            i += 1
        seen.add(slug)
        bind.execute(sa.text("UPDATE tenants SET slug=:slug, status='active' WHERE id=:id"), {"slug": slug, "id": tenant_id})

    op.alter_column("tenants", "slug", existing_type=sa.String(length=120), nullable=False)
    op.alter_column("tenants", "status", existing_type=sa.String(length=20), nullable=False)
    op.create_unique_constraint("uq_tenants_slug", "tenants", ["slug"])
    op.create_check_constraint("ck_tenants_status", "tenants", "status in ('active','suspended','archived')")


def downgrade() -> None:
    op.drop_constraint("ck_tenants_status", "tenants", type_="check")
    op.drop_constraint("uq_tenants_slug", "tenants", type_="unique")
    op.drop_column("tenants", "settings_json")
    op.drop_column("tenants", "updated_at")
    op.drop_column("tenants", "status")
    op.drop_column("tenants", "slug")

