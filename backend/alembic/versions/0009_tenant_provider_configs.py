"""Add tenant-scoped provider configs.

Revision ID: 0009_tenant_provider_configs
Revises: 0008_trial_requests_status
Create Date: 2026-04-03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0009_tenant_provider_configs"
down_revision = "0008_trial_requests_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_provider_configs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("provider_type", sa.String(length=40), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("model_allowlist", sa.JSON(), nullable=True),
        sa.Column("config_json", sa.JSON(), nullable=True),
        sa.Column("encrypted_secret_blob", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "provider_type", name="uq_tenant_provider_configs_tenant_provider"),
    )
    op.create_index(
        "ix_tenant_provider_configs_tenant_default",
        "tenant_provider_configs",
        ["tenant_id", "is_default"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_tenant_provider_configs_tenant_default", table_name="tenant_provider_configs")
    op.drop_table("tenant_provider_configs")
