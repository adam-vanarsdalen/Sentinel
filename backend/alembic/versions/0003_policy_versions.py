"""Policy versions

Revision ID: 0003_policy_versions
Revises: 0002_tenant_settings
Create Date: 2026-02-25
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_policy_versions"
down_revision = "0002_tenant_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_policy_versions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("policy_json", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_policy_versions_tenant_time", "tenant_policy_versions", ["tenant_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_policy_versions_tenant_time", table_name="tenant_policy_versions")
    op.drop_table("tenant_policy_versions")

