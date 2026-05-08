# SentinelLaw UI Guide (Pilot)

## Login
- Go to `/login`, sign in with a seeded demo user (configured in `.env`).
- Sessions are stored in an `httpOnly` cookie set by the Next.js route handler (`frontend/src/app/api/auth/login/route.ts`).

## Tenant context (super_admin)
- If your role is `super_admin`, select a firm in the top bar.
- Firm-scoped pages (dashboard, activity log, keys, rules, tests, settings, users) require an active firm context.

## Dashboard (`/dashboard`)
- Use the time range selector to view request volume, estimated cost, risk flag counts, and severity distribution.
- “Top API Keys” ranks by request count for the selected range.

## AI Activity Log (Audit Trail) (`/logs`)
- Use filters (time range, action, outcome, severity, API key, flag substring) with server-side pagination.
- Save common filters as “Views” (stored locally in your browser for this pilot).
- Click a row to open “Event Details”:
  - shows risk flags, confidential-data risk score, hashes, and redacted snippets (if enabled by firm policy)
  - includes a “Related Events” section (same API key ±5 minutes)
- Export:
  - Export CSV / JSON for the current filtered view.

## API Keys (`/api-keys`)
- `tenant_admin` and `super_admin` can create/revoke keys.
- The secret is shown once on creation; store it securely.

## Firm AI Rules (`/policies`)
- `tenant_admin` and `super_admin` can edit and publish policy JSON.
- `developer`/`auditor` can view (read-only).
- Use “Test Policy (Dry Run)” to evaluate a sample prompt/response against the candidate policy.

## Safety & Consistency Tests (`/evaluations`)
- Run the seeded suite against a provider/model.
- Open a run to see pass/fail results and pass-rate deltas vs the previous run (same provider/model).
- Click a test case ID to open the case detail page.

## Users & Roles (`/users`)
- `tenant_admin` and `super_admin` can create users (pilot: temporary password shown once) and assign roles.

## Settings (`/settings`)
- Configure storage mode and alert thresholds.
- Enabling “full content” storage requires explicit confirmation.
