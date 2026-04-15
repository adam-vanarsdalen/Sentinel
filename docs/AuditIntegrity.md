# Audit Integrity

Sentinel’s audit trail is designed to be append-only and independently verifiable.

## What changed

- `audit_events` now includes:
  - `previous_event_hash`
  - `event_hash`
- New audit rows are hash-chained per tenant.
- Normal application paths cannot update or delete existing audit rows.
- Sentinel exposes an integrity verification endpoint to detect tampering.

## Append-only protections

Sentinel enforces append-only behavior in two layers:

1. Application/ORM layer
   - SQLAlchemy session hooks reject updates and deletes of `AuditEvent` rows.
   - Normal runtime paths can only insert new audit records.

2. Database layer (PostgreSQL deployments)
   - Alembic migration `0010_audit_integrity` installs triggers that reject `UPDATE` and `DELETE` against `audit_events`.
   - This protects against raw SQL mutation attempts that bypass normal ORM code paths.

Important note:
- Existing read/export/reporting paths still work as before.
- Integrity hardening does not make the database tamper-proof against a privileged operator who can disable triggers or alter the schema, but it materially improves the credibility of the audit trail in normal operations.

## Hash chain design

For each tenant, Sentinel computes:

`event_hash = SHA256(previous_event_hash + canonical_event_payload)`

The canonical payload is a stable JSON representation of immutable event content, including fields such as:
- `id`
- `tenant_id`
- `api_key_id`
- `user_id`
- `request_id`
- `timestamp`
- `action_type`
- `outcome`
- `reason`
- `provider`
- `model`
- request/response hashes
- matter/practice/client fields
- severity / scores / usage / cost
- `event_data`

Each event points back to the previous event in the same tenant’s chain via `previous_event_hash`.

## Verification

Use:

- `GET /audit/integrity/verify?from=&to=&tenant_id=`

Response:

- `total_events_checked`
- `chain_valid`
- `first_broken_event_id`

Behavior:
- Verification runs in tenant scope.
- If a row has been altered after insertion, chain verification should fail at the first broken event.
- Sentinel logs verification activity as `AUDIT_VERIFY_RUN`.

## Export behavior

Sentinel JSON exports now include:
- `previous_event_hash`
- `event_hash`

CSV exports also include the same fields so downstream reviewers can retain integrity metadata outside Sentinel.
