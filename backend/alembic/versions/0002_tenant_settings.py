"""Tenant settings

Revision ID: 0002_tenant_settings
Revises: 0001_initial
Create Date: 2026-02-25
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_tenant_settings"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_settings",
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("settings_json", sa.JSON(), nullable=False),
        sa.Column("updated_by_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("tenant_settings")

