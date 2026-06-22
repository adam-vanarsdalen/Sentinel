"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "agents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("purpose_binding", sa.Text),
        sa.Column("state", sa.String(20), nullable=False, server_default="active"),
        sa.Column("config", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.CheckConstraint("state IN ('active','throttled','paused','terminated')", name="agents_state_check"),
    )

    op.create_table(
        "policies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.Integer, server_default="1"),
        sa.Column("action_limit_session", sa.Integer, server_default="1000"),
        sa.Column("budget_hourly_usd", sa.Numeric(10, 4)),
        sa.Column("budget_daily_usd", sa.Numeric(10, 4)),
        sa.Column("budget_monthly_usd", sa.Numeric(10, 4)),
        sa.Column("allowed_models", ARRAY(sa.String), server_default="{}"),
        sa.Column("forbidden_endpoints", ARRAY(sa.String), server_default="{}"),
        sa.Column("forbidden_data_classes", ARRAY(sa.String), server_default="{}"),
        sa.Column("config", JSONB, server_default="{}"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "agent_policies",
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id"), primary_key=True),
        sa.Column("policy_id", UUID(as_uuid=True), sa.ForeignKey("policies.id"), primary_key=True),
    )

    op.create_table(
        "request_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("request_id", UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id")),
        sa.Column("source", sa.String(50)),
        sa.Column("model_requested", sa.String(100)),
        sa.Column("model_used", sa.String(100)),
        sa.Column("status", sa.String(20)),
        sa.Column("blocked_reason", sa.Text),
        sa.Column("input_tokens", sa.Integer),
        sa.Column("output_tokens", sa.Integer),
        sa.Column("cost_usd", sa.Numeric(10, 6)),
        sa.Column("latency_ms", sa.Integer),
        sa.Column("grounding_score", sa.Numeric(3, 2)),
        sa.Column("anomaly_score", sa.Numeric(3, 2)),
        sa.Column("layer_reached", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('passed','blocked','flagged','error')", name="request_log_status_check"
        ),
    )

    op.create_table(
        "alerts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id")),
        sa.Column("request_id", UUID(as_uuid=True)),
        sa.Column("alert_type", sa.String(30)),
        sa.Column("severity", sa.String(10)),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("resolved", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.CheckConstraint(
            "alert_type IN ('kill_switch','anomaly','grounding','budget','manual')",
            name="alerts_type_check",
        ),
        sa.CheckConstraint(
            "severity IN ('low','medium','high','critical')", name="alerts_severity_check"
        ),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("request_id", UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", UUID(as_uuid=True)),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("layer", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20)),
        sa.Column("model", sa.String(100)),
        sa.Column("source", sa.String(50)),
        sa.Column("latency_ms", sa.Integer),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("regulation_mappings", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "compliance_packages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("time_range_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("time_range_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("regulations", ARRAY(sa.String), nullable=False),
        sa.Column("total_requests", sa.Integer),
        sa.Column("blocked_requests", sa.Integer),
        sa.Column("anomalies_detected", sa.Integer),
        sa.Column("kill_switch_events", sa.Integer),
        sa.Column("evidence_json", JSONB, nullable=False),
        sa.Column("gap_analysis", JSONB, nullable=False),
        sa.Column("pdf_url", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # Create application role and enforce append-only on audit_log
    op.execute("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='sentinel_app') THEN CREATE ROLE sentinel_app; END IF; END $$")
    op.execute("GRANT INSERT, SELECT ON audit_log TO sentinel_app")
    op.execute("REVOKE UPDATE, DELETE ON audit_log FROM sentinel_app")

    # Indexes
    op.create_index("ix_request_log_tenant_created", "request_log", ["tenant_id", "created_at"])
    op.create_index("ix_request_log_agent", "request_log", ["agent_id"])
    op.create_index("ix_audit_log_tenant_created", "audit_log", ["tenant_id", "created_at"])
    op.create_index("ix_audit_log_request_id", "audit_log", ["request_id"])
    op.create_index("ix_alerts_tenant_created", "alerts", ["tenant_id", "created_at"])


def downgrade() -> None:
    op.drop_table("compliance_packages")
    op.drop_table("audit_log")
    op.drop_table("alerts")
    op.drop_table("request_log")
    op.drop_table("agent_policies")
    op.drop_table("policies")
    op.drop_table("agents")
