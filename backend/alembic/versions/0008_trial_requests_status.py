"""Add status to trial_requests.

Revision ID: 0008_trial_requests_status
Revises: 0007_trial_requests
Create Date: 2026-03-06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0008_trial_requests_status"
down_revision = "0007_trial_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add as nullable with default, backfill, then enforce NOT NULL for portability.
    with op.batch_alter_table("trial_requests") as batch:
        batch.add_column(sa.Column("status", sa.String(length=40), nullable=True, server_default="pending"))
    op.execute("UPDATE trial_requests SET status = 'pending' WHERE status IS NULL")
    with op.batch_alter_table("trial_requests") as batch:
        batch.alter_column("status", nullable=False, server_default="pending")


def downgrade() -> None:
    with op.batch_alter_table("trial_requests") as batch:
        batch.drop_column("status")

