# Audit and Logging

## Audit philosophy

Sentinel is designed to provide reviewable governance evidence without defaulting to high-risk content retention.

Core goals:

- who/what/when/outcome traceability
- tenant-scoped accountability
- operationally useful risk context
- defensible export paths

## What gets logged

For gateway/admin actions, Sentinel stores structured event metadata including:

- tenant, actor, and API key context
- action type, outcome, reason
- provider/model route context
- risk flags, severity, and risk score fields
- usage and estimated cost fields
- request correlation identifiers
- content hashes (default)

## What should not be logged by default

- raw prompt content
- raw model response content
- provider secrets or API credentials

Optional redacted snippets can be enabled by policy where needed for triage.

## Retention principles

Sentinel does not hardcode retention periods. Operators should define retention/archival policies by regulatory and business requirements, and apply DB/storage controls accordingly.

## Integrity and tamper concerns

- append-only audit posture is enforced in application paths
- Postgres deployments include DB-level protections against update/delete mutation
- hash-chain verification endpoints support integrity checks

For high-assurance operation, periodically export logs to immutable external storage and monitor integrity verification outcomes.

## Reviewability

Audit data is exposed through:

- UI activity logs
- export endpoints (CSV/JSON/PDF/report formats)
- correlation IDs for operational incident review

## Supplemental references

- `docs/AuditIntegrity.md`
- `docs/AuditEventMapping.md`
- `docs/LoggingAndRetention.md`
- `docs/DataHandling.md`
