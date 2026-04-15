"""Add audit integrity chain fields and append-only protections.

Revision ID: 0010_audit_integrity
Revises: 0009_tenant_provider_configs
Create Date: 2026-04-03
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal

from alembic import op
import sqlalchemy as sa


revision = "0010_audit_integrity"
down_revision = "0009_tenant_provider_configs"
branch_labels = None
depends_on = None


def _json_default(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _canonical_payload(row: dict) -> str:
    payload = {
        "id": row["id"],
        "tenant_id": row["tenant_id"],
        "api_key_id": row.get("api_key_id"),
        "user_id": row.get("user_id"),
        "request_id": row.get("request_id"),
        "timestamp": row["timestamp"].isoformat() if row.get("timestamp") else None,
        "action_type": row.get("action_type"),
        "outcome": row.get("outcome"),
        "reason": row.get("reason"),
        "provider": row.get("provider"),
        "model": row.get("model"),
        "prompt_hash": row.get("prompt_hash"),
        "response_hash": row.get("response_hash"),
        "matter_id": row.get("matter_id"),
        "practice_group": row.get("practice_group"),
        "client_name": row.get("client_name"),
        "phi_score": row.get("phi_score"),
        "risk_flags": row.get("risk_flags") or [],
        "severity": row.get("severity"),
        "tokens_prompt": row.get("tokens_prompt"),
        "tokens_completion": row.get("tokens_completion"),
        "cost_usd": str(row["cost_usd"]) if row.get("cost_usd") is not None else None,
        "event_data": row.get("event_data") or {},
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=_json_default)


def _hash_event(previous_event_hash: str | None, row: dict) -> str:
    return hashlib.sha256(f"{previous_event_hash or ''}{_canonical_payload(row)}".encode("utf-8")).hexdigest()


def upgrade() -> None:
    with op.batch_alter_table("audit_events") as batch:
        batch.add_column(sa.Column("previous_event_hash", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("event_hash", sa.String(length=64), nullable=True))

    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT id, tenant_id, api_key_id, user_id, request_id, timestamp, action_type, outcome, reason,
                   provider, model, prompt_hash, response_hash, matter_id, practice_group, client_name,
                   phi_score, risk_flags, severity, tokens_prompt, tokens_completion, cost_usd, event_data
            FROM audit_events
            ORDER BY tenant_id ASC, timestamp ASC, id ASC
            """
        )
    ).mappings()

    previous_by_tenant: dict[str, str | None] = {}
    for row in rows:
        tenant_id = row["tenant_id"]
        previous = previous_by_tenant.get(tenant_id)
        event_hash = _hash_event(previous, row)
        bind.execute(
            sa.text(
                """
                UPDATE audit_events
                SET previous_event_hash = :previous_event_hash,
                    event_hash = :event_hash
                WHERE id = :id
                """
            ),
            {
                "id": row["id"],
                "previous_event_hash": previous,
                "event_hash": event_hash,
            },
        )
        previous_by_tenant[tenant_id] = event_hash

    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE OR REPLACE FUNCTION prevent_audit_event_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'audit_events is append-only';
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            """
            CREATE TRIGGER tr_audit_events_no_update
            BEFORE UPDATE ON audit_events
            FOR EACH ROW
            EXECUTE FUNCTION prevent_audit_event_mutation();
            """
        )
        op.execute(
            """
            CREATE TRIGGER tr_audit_events_no_delete
            BEFORE DELETE ON audit_events
            FOR EACH ROW
            EXECUTE FUNCTION prevent_audit_event_mutation();
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS tr_audit_events_no_update ON audit_events;")
        op.execute("DROP TRIGGER IF EXISTS tr_audit_events_no_delete ON audit_events;")
        op.execute("DROP FUNCTION IF EXISTS prevent_audit_event_mutation();")
    with op.batch_alter_table("audit_events") as batch:
        batch.drop_column("event_hash")
        batch.drop_column("previous_event_hash")
