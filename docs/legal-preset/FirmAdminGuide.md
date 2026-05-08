# Firm Admin Guide (Pilot)

This guide is for firm administrators (`tenant_admin`) operating SentinelLaw day-to-day: onboarding users, managing Firm AI Rules, issuing API keys to internal tools, and exporting audit reports.

## How to sign in (and confirm you are in the right firm)

1) Open the dashboard:
   - `http://localhost:${FRONTEND_PORT}` (local) or your deployed URL.
2) Sign in at `/login` using your firm admin credentials.
3) If you are a platform `super_admin`, select the firm in the firm selector at the top before using any firm-scoped pages.

## How to create a user (and assign a role)

UI method:
1) Go to **Users & Roles** (`/users`).
2) Click **Create user**.
3) Enter the user’s email and choose a role.
4) Save and record the **temporary password** shown by the UI (pilot behavior: shown once).
5) Give the user the login URL, their email, and the temporary password.

Operational note: user “deletion” is implemented as **deactivation** (soft-delete) so audit trails remain intact.

## How to deactivate a user

1) Go to **Users & Roles** (`/users`).
2) Find the user and choose **Delete/Deactivate**.
3) If you do not see the user afterwards, enable **Show inactive** to confirm status.

Guardrail: the system prevents deactivating the last active `tenant_admin` for a firm.

## How to set or update Firm AI Rules (policy)

UI method (publish a policy):
1) Go to **Firm AI Rules** (`/policies`).
2) Review the current JSON policy.
3) Make your change (common actions: adjust `allowed_models`, token limits, prompt-block patterns, metadata requirements).
4) Click **Publish**.
5) Confirm by reloading and checking `updated_at` or by validating behavior with a test request.

UI method (start from a template):
1) Go to **Firm AI Rules** (`/policies`) → **Templates**.
2) Choose a template (e.g., `legal_default_policy_v1`, `legal_strict_confidentiality_v1`, `legal_strict_no_client_data_v1`).
3) Apply the template, then review and **Publish**.

How to dry-run a policy (without changing production rules):
1) Go to **Firm AI Rules** (`/policies`).
2) Use **Test Policy (Dry Run)**.
3) Paste a sample prompt (and optionally a sample response) and run it.
4) Review `outcome`, `flags`, and the confidential-data risk signals before publishing.

API method (for change control):
- `GET /admin/policy/current`
- `PUT /admin/policy/current` with `{ "policy_json": { ... } }`
- `GET /admin/policy/versions` to review version history

## How to create an API key for an internal tool

Use API keys for machine-to-machine use of the gateway (`POST /v1/chat/completions`).

UI method:
1) Go to **API Keys** (`/api-keys`).
2) Click **Create key** and provide a name that identifies the tool/workflow.
3) Copy the key token **immediately**. It is shown once.
4) Store it in your secret manager (recommended) and configure the calling application to send it as `Authorization: Bearer sk_...` (or `X-API-Key`, depending on your client).

## How to revoke an API key

UI method:
1) Go to **API Keys** (`/api-keys`).
2) Locate the key and click **Revoke**.
3) Confirm the key is inactive and note `revoked_at`.

API method:
- `POST /admin/api-keys/{api_key_id}/revoke`

## How to read the AI Activity Log (Audit Trail)

1) Go to **AI Activity Log** (`/logs`).
2) Filter by:
   - time range
   - action type and outcome (allowed vs blocked)
   - severity and flags (e.g., injection suspected)
   - API key (to investigate a specific app/tool)
   - matter/practice group (if your tools send metadata)
3) Click an event to open **Event Details**:
   - review `risk_flags`, `phi_score`, `severity`, token usage, and hashes
   - review redacted snippets **only if enabled by policy**
4) Use the correlation ID (`request_id` / `X-Request-Id`) to match UI events with upstream logs.

## How to export audit reports (CSV/JSON)

UI method:
1) Go to **AI Activity Log** (`/logs`).
2) Apply the filters that define your report scope (range, API key, outcome, etc.).
3) Click **Export CSV** or **Export JSON**.
4) Store exports as you would other sensitive operational records.

API method:
- `GET /admin/audit-events/export.csv` (filters via query params)
- `GET /admin/audit-events/export.json?format=sentinel|fhir`

## How to run evaluations before and after a policy change

Goal: establish a baseline and detect regressions when changing rules, providers, or models.

1) Go to **Safety & Consistency Tests** (`/evaluations`).
2) Select the provider and model you intend to use.
3) Run the suite (baseline).
4) Make your policy change (or apply a template) and publish it.
5) Re-run the suite using the **same provider/model**.
6) Review:
   - overall pass rate
   - deltas vs the previous run
   - any newly failing cases and the associated flags

API method:
- `POST /admin/evals/run` with `{ "provider": "...", "model": "..." }`
- `GET /admin/evals/runs` and `GET /admin/evals/runs/{run_id}`

## Role reference (what each role can and cannot do)

These are the practical permissions implied by the current pilot RBAC.

### `tenant_admin`
Can:
- create/deactivate users and assign roles
- create and revoke API keys
- publish Firm AI Rules (policy) and update tenant settings
- view and export audit logs
- run evaluations

Cannot:
- perform platform-wide firm administration (create/switch firms) unless also a `super_admin`

### `auditor`
Can:
- view AI Activity Log and event details
- export audit reports (CSV/JSON)
- view Firm AI Rules and settings (read-only)
- view evaluations and results

Cannot:
- create/revoke API keys
- create/deactivate users or change roles
- publish Firm AI Rules or update settings
- run evaluations

### `developer`
Can:
- view AI Activity Log and event details
- create API keys (for development/integration)
- view Firm AI Rules and run policy dry-runs (read/test)
- run evaluations

Cannot:
- export audit reports
- revoke API keys
- create/deactivate users or change roles
- publish Firm AI Rules or update settings

### `viewer`
Can:
- view dashboards, logs, policies, settings, and evaluation results (read-only)

Cannot:
- create/revoke API keys
- export audit reports
- create/deactivate users or change roles
- publish policies or update settings
- run evaluations

