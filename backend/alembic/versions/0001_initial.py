"""Initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2026-02-25
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=500), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])

    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("key_prefix", sa.String(length=16), nullable=False),
        sa.Column("key_salt", sa.String(length=64), nullable=False),
        sa.Column("key_hash", sa.String(length=128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "name", name="uq_api_keys_tenant_name"),
    )
    op.create_index("ix_api_keys_tenant_id", "api_keys", ["tenant_id"])
    op.create_index("ix_api_keys_prefix", "api_keys", ["key_prefix"])

    op.create_table(
        "tenant_policies",
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("policy_json", sa.JSON(), nullable=False),
        sa.Column("updated_by_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("api_key_id", sa.String(length=36), sa.ForeignKey("api_keys.id"), nullable=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("action_type", sa.String(length=60), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("provider", sa.String(length=40), nullable=True),
        sa.Column("prompt_hash", sa.String(length=64), nullable=True),
        sa.Column("response_hash", sa.String(length=64), nullable=True),
        sa.Column("redacted_prompt", sa.String(length=500), nullable=True),
        sa.Column("redacted_response", sa.String(length=500), nullable=True),
        sa.Column("phi_score", sa.Integer(), nullable=True),
        sa.Column("risk_flags", sa.JSON(), nullable=True),
        sa.Column("severity", sa.String(length=10), nullable=True),
        sa.Column("tokens_prompt", sa.Integer(), nullable=True),
        sa.Column("tokens_completion", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("event_data", sa.JSON(), nullable=True),
    )
    op.create_index("ix_audit_events_tenant_time", "audit_events", ["tenant_id", "timestamp"])
    op.create_index("ix_audit_events_action", "audit_events", ["action_type"])

    op.create_table(
        "eval_test_cases",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("input_messages", sa.JSON(), nullable=False),
        sa.Column("expected_flags", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("tenant_id", "name", name="uq_eval_cases_tenant_name"),
    )
    op.create_index("ix_eval_cases_tenant_id", "eval_test_cases", ["tenant_id"])

    op.create_table(
        "eval_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.JSON(), nullable=True),
    )
    op.create_index("ix_eval_runs_tenant_time", "eval_runs", ["tenant_id", "started_at"])

    op.create_table(
        "eval_results",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("eval_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("test_case_id", sa.String(length=36), sa.ForeignKey("eval_test_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("observed_flags", sa.JSON(), nullable=True),
        sa.Column("phi_score", sa.Integer(), nullable=True),
        sa.Column("risk_severity", sa.String(length=10), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
    )
    op.create_index("ix_eval_results_run", "eval_results", ["run_id"])


def downgrade() -> None:
    op.drop_table("eval_results")
    op.drop_table("eval_runs")
    op.drop_table("eval_test_cases")
    op.drop_table("audit_events")
    op.drop_table("tenant_policies")
    op.drop_table("api_keys")
    op.drop_table("users")
    op.drop_table("tenants")

