"""Add policy history metadata, active-version pointer, and backfill.

Revision ID: 0011_policy_history_metadata
Revises: 0010_audit_integrity
Create Date: 2026-04-03
"""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa


revision = "0011_policy_history_metadata"
down_revision = "0010_audit_integrity"
branch_labels = None
depends_on = None


tenant_policies = sa.table(
    "tenant_policies",
    sa.column("tenant_id", sa.String(length=36)),
    sa.column("policy_json", sa.JSON()),
    sa.column("updated_by_user_id", sa.String(length=36)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
    sa.column("active_version_id", sa.String(length=36)),
)

tenant_policy_versions = sa.table(
    "tenant_policy_versions",
    sa.column("id", sa.String(length=36)),
    sa.column("tenant_id", sa.String(length=36)),
    sa.column("policy_json", sa.JSON()),
    sa.column("created_by_user_id", sa.String(length=36)),
    sa.column("change_note", sa.String(length=500)),
    sa.column("source_template_id", sa.String(length=120)),
    sa.column("source_version_id", sa.String(length=36)),
    sa.column("created_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    with op.batch_alter_table("tenant_policy_versions") as batch:
        batch.add_column(sa.Column("change_note", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("source_template_id", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("source_version_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key(
            "fk_tenant_policy_versions_source_version_id",
            "tenant_policy_versions",
            ["source_version_id"],
            ["id"],
        )

    with op.batch_alter_table("tenant_policies") as batch:
        batch.add_column(sa.Column("active_version_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key(
            "fk_tenant_policies_active_version_id",
            "tenant_policy_versions",
            ["active_version_id"],
            ["id"],
        )

    bind = op.get_bind()
    versions_by_tenant: dict[str, list[dict]] = {}
    version_rows = bind.execute(
        sa.select(
            tenant_policy_versions.c.id,
            tenant_policy_versions.c.tenant_id,
            tenant_policy_versions.c.policy_json,
            tenant_policy_versions.c.created_by_user_id,
            tenant_policy_versions.c.created_at,
        )
        .order_by(
            tenant_policy_versions.c.tenant_id.asc(),
            tenant_policy_versions.c.created_at.desc(),
            tenant_policy_versions.c.id.desc(),
        )
    ).mappings()
    for row in version_rows:
        versions_by_tenant.setdefault(row["tenant_id"], []).append(dict(row))

    policy_rows = bind.execute(
        sa.select(
            tenant_policies.c.tenant_id,
            tenant_policies.c.policy_json,
            tenant_policies.c.updated_by_user_id,
            tenant_policies.c.updated_at,
        )
    ).mappings()

    for policy_row in policy_rows:
        tenant_id = policy_row["tenant_id"]
        chosen_version_id: str | None = None
        for version_row in versions_by_tenant.get(tenant_id, []):
            if version_row["policy_json"] == policy_row["policy_json"]:
                chosen_version_id = version_row["id"]
                break
        if not chosen_version_id:
            chosen_version_id = str(uuid.uuid4())
            bind.execute(
                tenant_policy_versions.insert().values(
                    id=chosen_version_id,
                    tenant_id=tenant_id,
                    policy_json=policy_row["policy_json"],
                    created_by_user_id=policy_row["updated_by_user_id"],
                    change_note="Backfilled active policy snapshot",
                    source_template_id=None,
                    source_version_id=None,
                    created_at=policy_row["updated_at"],
                )
            )
        bind.execute(
            tenant_policies.update()
            .where(tenant_policies.c.tenant_id == tenant_id)
            .values(active_version_id=chosen_version_id)
        )


def downgrade() -> None:
    with op.batch_alter_table("tenant_policies") as batch:
        batch.drop_constraint("fk_tenant_policies_active_version_id", type_="foreignkey")
        batch.drop_column("active_version_id")

    with op.batch_alter_table("tenant_policy_versions") as batch:
        batch.drop_constraint("fk_tenant_policy_versions_source_version_id", type_="foreignkey")
        batch.drop_column("source_version_id")
        batch.drop_column("source_template_id")
        batch.drop_column("change_note")
