# Sentinel → FHIR AuditEvent Mapping (Pilot)

This is a *pilot* conceptual mapping from Sentinel’s internal `audit_events` table to HL7 FHIR R4 `AuditEvent`.
It is intended to support export/use in downstream audit systems and to guide future full conformance work.

Reference: see `docs/References.md` (FHIR R4 AuditEvent).

## Sentinel fields → FHIR AuditEvent (conceptual)

- `audit_events.id` → `AuditEvent.id`
- `audit_events.timestamp` → `AuditEvent.recorded`
- `audit_events.action_type` → `AuditEvent.type.text` (pilot); future: map to coded `AuditEvent.type` + `subtype`
- `audit_events.outcome` → `AuditEvent.outcome` (pilot uses 0=success / 8=serious failure)
- `audit_events.user_id` → `AuditEvent.agent.who.identifier.value`
- `audit_events.api_key_id` → `AuditEvent.agent.who.identifier.value` (when user absent)
- `audit_events.provider` → `AuditEvent.entity.detail` (type=`provider`)
- `audit_events.model` → `AuditEvent.entity.what.identifier.value` (pilot)
- `audit_events.phi_score` → `AuditEvent.entity.detail` (type=`phi_score`)
- `audit_events.risk_flags` → `AuditEvent.entity.detail` (future: consider `securityLabel` or coded extensions)

## Notes / non-goals (pilot)

- Not full conformance: this export is *not* guaranteed to validate against all FHIR profiles.
- No subject identity mapping by default: SentinelLaw does not ingest client identifiers and does not create FHIR `Patient` references.
- Consider adding `OperationOutcome` containment for failed operations if Sentinel becomes a FHIR API gateway (see FHIR guidance).
