"""Audit request_id

Revision ID: 0004_audit_request_id
Revises: 0003_policy_versions
Create Date: 2026-02-26
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_audit_request_id"
down_revision = "0003_policy_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_events", sa.Column("request_id", sa.String(length=64), nullable=True))
    op.create_index("ix_audit_events_request_id", "audit_events", ["request_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_request_id", table_name="audit_events")
    op.drop_column("audit_events", "request_id")

