"""KillSwitchService — implements the state machine from skills/kill-switch-state-machine.md."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.proxy import AuditEntry

VALID_TRANSITIONS: dict[str, set[str]] = {
    "active": {"throttled", "paused", "terminated"},
    "throttled": {"paused", "terminated", "active"},
    "paused": {"active", "terminated"},
    "terminated": {"active"},
}

FORBIDDEN_FROM_TERMINATED = {"throttled", "paused"}


class KillSwitchAuditError(Exception):
    pass


class KillSwitchService:
    def __init__(self, redis: Redis, db: AsyncSession):
        self._redis = redis
        self._db = db

    async def get_agent_state(self, agent_id: str) -> str:
        raw = await self._redis.get(f"sentinel:agent:{agent_id}:state")
        return raw.decode() if raw else "active"

    async def _transition(
        self,
        agent_id: str,
        new_state: str,
        reason: str,
        triggered_by: str,
        operator_id: str | None,
        tenant_id: str,
    ) -> None:
        old_state = await self.get_agent_state(agent_id)

        if new_state in FORBIDDEN_FROM_TERMINATED and old_state == "terminated":
            raise ValueError(f"Forbidden transition: terminated → {new_state}")

        if new_state not in VALID_TRANSITIONS.get(old_state, set()):
            raise ValueError(f"Invalid transition: {old_state} → {new_state}")

        if new_state == "active" and not operator_id:
            raise ValueError("Transition to active requires operator_id")

        # Audit-first: write before Redis
        audit = AuditEntry(
            request_id="00000000-0000-0000-0000-000000000000",
            tenant_id=tenant_id,
            agent_id=agent_id,
            action="kill_switch_transition",
            layer=3,
            status="blocked" if new_state in ("paused", "terminated") else "passed",
            metadata={
                "old_state": old_state,
                "new_state": new_state,
                "reason": reason,
                "triggered_by": triggered_by,
                "operator_id": operator_id,
            },
        )
        await self._write_audit(audit)

        # Write new state to Redis
        now = datetime.now(timezone.utc).isoformat()
        pipe = self._redis.pipeline()
        pipe.set(f"sentinel:agent:{agent_id}:state", new_state)
        pipe.set(f"sentinel:agent:{agent_id}:state_reason", reason)
        pipe.set(f"sentinel:agent:{agent_id}:state_ts", now)
        if operator_id:
            pipe.set(f"sentinel:agent:{agent_id}:operator_id", operator_id)
        await pipe.execute()

        # Broadcast via pub/sub
        event = json.dumps({
            "type": "kill_switch_event",
            "agent_id": agent_id,
            "old_state": old_state,
            "new_state": new_state,
            "reason": reason,
            "triggered_by": triggered_by,
            "operator_id": operator_id,
            "timestamp": now,
        })
        await self._redis.publish(f"sentinel:alerts:{tenant_id}", event)

    async def _write_audit(self, audit: AuditEntry) -> None:
        from models.audit_entry import AuditEntry as AuditEntryModel
        entry = AuditEntryModel(
            request_id=audit.request_id,  # type: ignore[arg-type]
            tenant_id=audit.tenant_id,  # type: ignore[arg-type]
            agent_id=audit.agent_id,  # type: ignore[arg-type]
            action=audit.action,
            layer=audit.layer,
            status=audit.status,
            metadata_=audit.metadata,
            regulation_mappings={
                "EU_AI_ACT": ["Article 14"],
                "NIST_AI_RMF": ["MANAGE-1.3", "MANAGE-2.4"],
            },
        )
        self._db.add(entry)
        try:
            await self._db.flush()
        except Exception as e:
            raise KillSwitchAuditError(f"Audit write failed: {e}") from e

    async def throttle(self, agent_id: str, reason: str, triggered_by: str = "layer6", tenant_id: str = "") -> None:
        await self._transition(agent_id, "throttled", reason, triggered_by, None, tenant_id)

    async def pause(self, agent_id: str, reason: str, triggered_by: str = "layer6", tenant_id: str = "") -> None:
        await self._transition(agent_id, "paused", reason, triggered_by, None, tenant_id)

    async def terminate(self, agent_id: str, reason: str, triggered_by: str = "layer6", tenant_id: str = "") -> None:
        await self._transition(agent_id, "terminated", reason, triggered_by, None, tenant_id)

    async def resume(self, agent_id: str, operator_id: str, reason: str, tenant_id: str = "") -> None:
        await self._transition(agent_id, "active", reason, "operator", operator_id, tenant_id)

    async def fire_manual(self, agent_id: str, operator_id: str, reason: str, tenant_id: str = "") -> None:
        await self._transition(agent_id, "terminated", reason, "operator", operator_id, tenant_id)
