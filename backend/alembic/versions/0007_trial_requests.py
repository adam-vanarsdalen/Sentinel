"""Add trial_requests table.

Revision ID: 0007_trial_requests
Revises: 0006_audit_matter_metadata
Create Date: 2026-03-06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_trial_requests"
down_revision = "0006_audit_matter_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trial_requests",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("firm_name", sa.String(length=200), nullable=False),
        sa.Column("contact_name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_trial_requests_created_at", "trial_requests", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_trial_requests_created_at", table_name="trial_requests")
    op.drop_table("trial_requests")

