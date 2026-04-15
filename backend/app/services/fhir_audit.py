from __future__ import annotations

from app.db.models import AuditEvent


def to_fhir_audit_event(ev: AuditEvent) -> dict:
    # Pilot mapping: conceptually shape like FHIR AuditEvent (not full conformance).
    # See docs/AuditEventMapping.md for mapping notes.
    return {
        "resourceType": "AuditEvent",
        "id": ev.id,
        "recorded": ev.timestamp.isoformat(),
        "outcome": "0" if ev.outcome == "success" else "8",
        "type": {"text": ev.action_type},
        "agent": [
            {
                "who": {"identifier": {"value": ev.user_id or ev.api_key_id or "unknown"}},
                "requestor": True if ev.user_id else False,
            }
        ],
        "source": {"observer": {"identifier": {"value": "sentinel"}}},
        "entity": [
            {
                "what": {"identifier": {"value": ev.model or "llm"}},
                "detail": [
                    {"type": "provider", "valueString": ev.provider or ""},
                    {"type": "phi_score", "valueString": str(ev.phi_score) if ev.phi_score is not None else ""},
                ],
            }
        ],
    }

