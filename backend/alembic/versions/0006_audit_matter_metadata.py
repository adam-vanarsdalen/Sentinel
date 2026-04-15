"""Add matter/practice metadata to audit events.

Revision ID: 0006_audit_matter_metadata
Revises: 0005_tenant_slug_status
Create Date: 2026-02-26
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0006_audit_matter_metadata"
down_revision = "0005_tenant_slug_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("audit_events") as batch:
        batch.add_column(sa.Column("matter_id", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("practice_group", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("client_name", sa.String(length=200), nullable=True))

    op.create_index("ix_audit_events_tenant_matter", "audit_events", ["tenant_id", "matter_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_tenant_matter", table_name="audit_events")
    with op.batch_alter_table("audit_events") as batch:
        batch.drop_column("client_name")
        batch.drop_column("practice_group")
        batch.drop_column("matter_id")

