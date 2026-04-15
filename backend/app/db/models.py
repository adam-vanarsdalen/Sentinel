from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy import JSON as SAJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.core.roles import canonical_role


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    settings_json: Mapped[dict | None] = mapped_column(SAJSON, nullable=True)

    def to_platform_dict(self) -> dict[str, Any]:
        settings_json = self.settings_json if isinstance(self.settings_json, dict) else {}
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "preset_id": settings_json.get("preset_id"),
            "demo_profile": settings_json.get("demo_profile"),
            "demo_summary": settings_json.get("demo_summary"),
            "is_demo": bool(settings_json.get("is_demo")),
        }


class TrialRequest(Base):
    __tablename__ = "trial_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    firm_name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    __table_args__ = (Index("ix_trial_requests_created_at", "created_at"),)


class User(Base):
    __tablename__ = "users"
    __allow_unmapped__ = True

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(500), nullable=False)
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    _effective_tenant_id: str | None = None

    @property
    def effective_tenant_id(self) -> str | None:
        return self._effective_tenant_id if self._effective_tenant_id is not None else self.tenant_id

    def with_effective_tenant(self, tenant_id: str) -> "User":
        clone = User(
            id=self.id,
            tenant_id=self.tenant_id,
            email=self.email,
            password_hash=self.password_hash,
            role=self.role,
            is_active=self.is_active,
            created_at=self.created_at,
        )
        clone._effective_tenant_id = tenant_id
        return clone

    def to_list_item(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "role": canonical_role(self.role),
            "tenant_id": self.tenant_id,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
        }


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    key_salt: Mapped[str] = mapped_column(String(64), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped["Tenant"] = relationship("Tenant")

    def revoke(self) -> None:
        self.is_active = False
        self.revoked_at = _utcnow()

    def to_list_item(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "key_prefix": self.key_prefix,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
        }


class TenantPolicy(Base):
    __tablename__ = "tenant_policies"

    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    policy_json: Mapped[dict] = mapped_column(SAJSON, nullable=False)
    updated_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    active_version_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tenant_policy_versions.id"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    def to_response(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "policy_json": self.policy_json,
            "updated_at": self.updated_at.isoformat(),
            "updated_by_user_id": self.updated_by_user_id,
            "active_version_id": self.active_version_id,
        }


class TenantPolicyVersion(Base):
    __tablename__ = "tenant_policy_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    policy_json: Mapped[dict] = mapped_column(SAJSON, nullable=False)
    created_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    change_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_template_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_version_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tenant_policy_versions.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)



class TenantSettings(Base):
    __tablename__ = "tenant_settings"

    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    settings_json: Mapped[dict] = mapped_column(SAJSON, nullable=False)
    updated_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    def to_response(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "settings_json": self.settings_json,
            "updated_at": self.updated_at.isoformat(),
            "updated_by_user_id": self.updated_by_user_id,
        }


class TenantProviderConfig(Base):
    __tablename__ = "tenant_provider_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(40), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    model_allowlist: Mapped[list[str] | None] = mapped_column(SAJSON, nullable=True)
    config_json: Mapped[dict | None] = mapped_column(SAJSON, nullable=True)
    encrypted_secret_blob: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "provider_type", name="uq_tenant_provider_configs_tenant_provider"),
        Index("ix_tenant_provider_configs_tenant_default", "tenant_id", "is_default"),
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    api_key_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("api_keys.id"), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    matter_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    practice_group: Mapped[str | None] = mapped_column(String(120), nullable=True)
    client_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    previous_event_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action_type: Mapped[str] = mapped_column(String(60), nullable=False)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    prompt_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    response_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    redacted_prompt: Mapped[str | None] = mapped_column(String(500), nullable=True)
    redacted_response: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phi_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_flags: Mapped[list[str] | None] = mapped_column(SAJSON, nullable=True)
    severity: Mapped[str | None] = mapped_column(String(10), nullable=True)
    tokens_prompt: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_completion: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    event_data: Mapped[dict | None] = mapped_column(SAJSON, nullable=True)

    __table_args__ = (
        Index("ix_audit_events_tenant_time", "tenant_id", "timestamp"),
        Index("ix_audit_events_action", "action_type"),
        Index("ix_audit_events_tenant_matter", "tenant_id", "matter_id"),
    )

    @staticmethod
    def csv_fields() -> list[str]:
        return [
            "id",
            "request_id",
            "timestamp",
            "previous_event_hash",
            "event_hash",
            "tenant_id",
            "action_type",
            "outcome",
            "reason",
            "provider",
            "model",
            "api_key_id",
            "user_id",
            "matter_id",
            "practice_group",
            "client_name",
            "phi_score",
            "severity",
            "risk_flags",
            "tokens_prompt",
            "tokens_completion",
            "cost_usd",
        ]

    def to_csv_row(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "request_id": self.request_id,
            "timestamp": self.timestamp.isoformat(),
            "previous_event_hash": self.previous_event_hash,
            "event_hash": self.event_hash,
            "tenant_id": self.tenant_id,
            "action_type": self.action_type,
            "outcome": self.outcome,
            "reason": self.reason,
            "provider": self.provider,
            "model": self.model,
            "api_key_id": self.api_key_id,
            "user_id": self.user_id,
            "matter_id": self.matter_id,
            "practice_group": self.practice_group,
            "client_name": self.client_name,
            "phi_score": self.phi_score,
            "severity": self.severity,
            "risk_flags": json.dumps(self.risk_flags or []),
            "tokens_prompt": self.tokens_prompt,
            "tokens_completion": self.tokens_completion,
            "cost_usd": str(self.cost_usd) if self.cost_usd is not None else None,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "api_key_id": self.api_key_id,
            "user_id": self.user_id,
            "matter_id": self.matter_id,
            "practice_group": self.practice_group,
            "client_name": self.client_name,
            "request_id": self.request_id,
            "timestamp": self.timestamp.isoformat(),
            "previous_event_hash": self.previous_event_hash,
            "event_hash": self.event_hash,
            "action_type": self.action_type,
            "outcome": self.outcome,
            "reason": self.reason,
            "provider": self.provider,
            "model": self.model,
            "prompt_hash": self.prompt_hash,
            "response_hash": self.response_hash,
            "redacted_prompt": self.redacted_prompt,
            "redacted_response": self.redacted_response,
            "phi_score": self.phi_score,
            "risk_flags": self.risk_flags or [],
            "severity": self.severity,
            "tokens_prompt": self.tokens_prompt,
            "tokens_completion": self.tokens_completion,
            "cost_usd": float(self.cost_usd) if self.cost_usd is not None else None,
            "event_data": self.event_data or {},
        }

    @staticmethod
    def json_dumps(obj: Any) -> str:
        return json.dumps(obj, ensure_ascii=False, default=str)


class EvalTestCase(Base):
    __tablename__ = "eval_test_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    input_messages: Mapped[list[dict]] = mapped_column(SAJSON, nullable=False)
    expected_flags: Mapped[list[str] | None] = mapped_column(SAJSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    __table_args__ = (Index("ix_eval_cases_tenant_id", "tenant_id"),)


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[dict | None] = mapped_column(SAJSON, nullable=True)

    __table_args__ = (Index("ix_eval_runs_tenant_time", "tenant_id", "started_at"),)

    @classmethod
    def new(cls, *, tenant_id: str, provider: str, model: str) -> "EvalRun":
        return cls(tenant_id=tenant_id, provider=provider, model=model, status="queued")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "provider": self.provider,
            "model": self.model,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "summary": self.summary or {},
        }


class EvalResult(Base):
    __tablename__ = "eval_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("eval_runs.id", ondelete="CASCADE"), nullable=False)
    test_case_id: Mapped[str] = mapped_column(String(36), ForeignKey("eval_test_cases.id", ondelete="CASCADE"), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    observed_flags: Mapped[list[str] | None] = mapped_column(SAJSON, nullable=True)
    phi_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_severity: Mapped[str | None] = mapped_column(String(10), nullable=True)
    details: Mapped[dict | None] = mapped_column(SAJSON, nullable=True)

    __table_args__ = (Index("ix_eval_results_run", "run_id"),)
