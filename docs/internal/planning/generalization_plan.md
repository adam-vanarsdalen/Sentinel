# Sentinel Generalization Plan

## Scope and intent

This document audits the current `Sentinel-Law/` reference application and defines a low-risk path to build a generalized `Sentinel` platform while preserving `SentinelLaw` as a legal preset/edition.

Prompt 1 constraints observed:

- No broad refactor was performed.
- No working subsystems were replaced.
- No new app scaffold was introduced.
- Only root-level planning scaffolding was added in `Sentinel/`.

Current workspace reality:

- `Sentinel/` currently contains the reference app in `Sentinel-Law/`.
- There is no generalized root app yet.
- The plan below assumes Prompts 2–5 will reuse the `Sentinel-Law` architecture rather than inventing a new one.

## Current architecture summary

`Sentinel-Law` already has a reusable multi-tenant AI governance platform core:

- Backend: FastAPI, SQLAlchemy, Alembic, Postgres, Redis, Celery stubs, provider routing, policy enforcement, audit logging, alerts, metrics, evaluations.
- Frontend: Next.js App Router, React Query, Tailwind, role-gated admin console.
- Operational model: tenant-scoped gateway, API-key auth for proxied LLM traffic, JWT auth for console users, export/reporting, seeded demo environment.

Shared core product logic that should remain shared:

- Authentication and role enforcement.
- Tenant isolation and platform tenant management.
- Provider configuration and routing.
- Gateway request validation, preflight/postflight policy checks, rate limiting, fallback handling.
- Audit event capture, integrity chain, search, export, and reporting infrastructure.
- Alerts, settings, metrics, and evaluation runner infrastructure.
- Basic demo/bootstrap machinery.

The architecture is already closer to "general AI governance control plane" than the UI copy suggests. Most generalization work is naming, preset packaging, and metadata abstraction.

## Audit findings

### 1. Shared product copy already reusable

These areas are mostly neutral and should stay in shared core with light renaming only:

- Provider configuration flows in `Sentinel-Law/frontend/src/app/(app)/providers/page.tsx`
- Settings and alert delivery mechanics in `Sentinel-Law/frontend/src/app/(app)/settings/page.tsx` and `Sentinel-Law/frontend/src/app/(app)/alerts/page.tsx`
- Auth, tenancy, provider routing, rate limiting, cost tracking, evaluations, audit integrity in `Sentinel-Law/backend/app/`
- Platform tenant management mechanics in `Sentinel-Law/backend/app/api/routes/platform_tenants.py`

### 2. Law-specific UI copy

Hardcoded law/firm copy is concentrated in:

- Landing page and hero copy:
  - `Sentinel-Law/frontend/src/app/page.tsx`
- Login/help/support copy:
  - `Sentinel-Law/frontend/src/app/(auth)/login/page.tsx`
  - `Sentinel-Law/frontend/src/app/(app)/help/page.tsx`
- Shell/nav/product name:
  - `Sentinel-Law/frontend/src/components/layout/app-shell.tsx`
- Dashboard empty states and governance labels:
  - `Sentinel-Law/frontend/src/app/(app)/dashboard/page.tsx`
- Policies UI:
  - `Sentinel-Law/frontend/src/app/(app)/policies/page.tsx`
- Logs/report UI:
  - `Sentinel-Law/frontend/src/app/(app)/logs/page.tsx`
- Users/roles UI:
  - `Sentinel-Law/frontend/src/app/(app)/users/page.tsx`
- Trial request form:
  - `Sentinel-Law/frontend/src/app/request-trial-button.tsx`

Examples of legal coupling:

- "AI governance built for law firms"
- "ABA Rule 1.6 risks"
- "Firm AI Rules"
- "Firm Admin"
- "Compliance Reviewer"
- "client-ready SentinelLaw report"
- "drafting request through SentinelLaw"

### 3. Law-specific dashboard and report terminology

The main domain-specific reporting vocabulary is:

- `firm`
- `matter`
- `practice group`
- `client`

This vocabulary is baked into:

- Frontend dashboard:
  - `Sentinel-Law/frontend/src/app/(app)/dashboard/page.tsx`
- Frontend logs and exports:
  - `Sentinel-Law/frontend/src/app/(app)/logs/page.tsx`
- Frontend help glossary:
  - `Sentinel-Law/frontend/src/app/(app)/help/page.tsx`
- Audit reports:
  - `Sentinel-Law/backend/app/services/audit_reports.py`
  - `Sentinel-Law/backend/app/api/routes/audit.py`
- Metrics:
  - `Sentinel-Law/backend/app/services/metrics_service.py`

### 4. Law-specific roles

Backend role codes are mostly reusable, but UI labels/descriptions are legal-specific:

- Role codes:
  - `super_admin`, `tenant_admin`, `auditor`, `developer`, `viewer`
- Legal UI labels:
  - `Firm Admin`
  - `Compliance Reviewer`
  - `Integration User`
  - `Staff`

Files:

- `Sentinel-Law/frontend/src/app/(app)/users/page.tsx`
- `Sentinel-Law/frontend/src/app/(app)/help/page.tsx`
- `Sentinel-Law/frontend/src/lib/schemas.ts`

### 5. Seed and demo data

The demo environment is strongly law-shaped:

- Demo tenant name: `Demo Law Firm`
- Demo admin email: `admin@demolaw.com`
- Default policy template: `legal_default_policy_v1`
- Demo API key name: `demo-contract-review`
- Eval suite examples mention clauses, client data, and matter identifiers

Files:

- `Sentinel-Law/backend/app/scripts/seed_demo.py`
- `Sentinel-Law/backend/tests/test_policies_templates_seed.py`
- `Sentinel-Law/frontend/tests/*.spec.ts`

### 6. Policy packs / rules examples

Policy templates are currently fully legal-specific:

- Template ids:
  - `legal_default_policy_v1`
  - `legal_strict_confidentiality_v1`
  - `legal_strict_no_client_data_v1`
- Template body uses:
  - "legal drafting assistant"
  - "firm governance rules"
  - "contracts, pleadings, emails"
  - "client matters"

Files:

- `Sentinel-Law/backend/app/services/policy_templates.py`
- `Sentinel-Law/backend/app/services/policy.py`
- `Sentinel-Law/frontend/src/app/(app)/policies/page.tsx`
- `Sentinel-Law/frontend/src/lib/policy-schema.ts`

### 7. Landing page / hero copy

Law-specific marketing copy is explicit in:

- `Sentinel-Law/frontend/src/app/page.tsx`
- `Sentinel-Law/README.md`
- `Sentinel-Law/INSTRUCTIONS.md`
- `Sentinel-Law/docs/LegalPositioning.md`

### 8. Report/export labels

Legal/firms/client-report language appears in:

- `Sentinel-Law/frontend/src/app/(app)/logs/page.tsx`
- `Sentinel-Law/backend/app/services/audit_reports.py`
- `Sentinel-Law/backend/app/api/routes/audit.py`

Examples:

- `sentinellaw-client-audit-report.pdf`
- `SentinelLaw Client Audit Report`
- "Top matters"
- "Top practice groups"
- "client-ready"

### 9. Hardcoded legal assumptions in backend/domain objects

The largest backend domain assumptions are:

- `TrialRequest.firm_name`
- `AuditEvent.matter_id`
- `AuditEvent.practice_group`
- `AuditEvent.client_name`
- gateway metadata headers:
  - `X-Matter-Id`
  - `X-Practice-Group`
  - `X-Client-Name`
- legal policy section:
  - `policy_json.legal`

Files:

- `Sentinel-Law/backend/app/db/models.py`
- `Sentinel-Law/backend/alembic/versions/0006_audit_matter_metadata.py`
- `Sentinel-Law/backend/alembic/versions/0007_trial_requests.py`
- `Sentinel-Law/backend/app/api/routes/gateway.py`
- `Sentinel-Law/backend/app/services/gateway.py`
- `Sentinel-Law/backend/app/api/routes/public.py`
- `Sentinel-Law/backend/app/services/policy.py`

### 10. Frontend components that should become terminology-driven

Highest-priority terminology-driven components:

- `frontend/src/components/layout/app-shell.tsx`
- `frontend/src/app/page.tsx`
- `frontend/src/app/request-trial-button.tsx`
- `frontend/src/app/(app)/dashboard/page.tsx`
- `frontend/src/app/(app)/logs/page.tsx`
- `frontend/src/app/(app)/policies/page.tsx`
- `frontend/src/app/(app)/users/page.tsx`
- `frontend/src/app/(app)/help/page.tsx`
- `frontend/src/app/(app)/firms/page.tsx`
- `frontend/src/app/(app)/firms/[id]/page.tsx`
- `frontend/src/components/exposure-badge.tsx`

## Important non-legal drift found during audit

There is also legacy healthcare terminology in the repo:

- `phi` is used as the confidential-data scanner name throughout backend and frontend.
- `FHIR` export compatibility remains in audit export code and docs.
- `docs/ARCHITECTURE.md` still says `Hospital App / Service`.

Files:

- `Sentinel-Law/backend/app/services/phi.py`
- `Sentinel-Law/backend/app/services/gateway.py`
- `Sentinel-Law/frontend/src/lib/policy-schema.ts`
- `Sentinel-Law/frontend/src/lib/schemas.ts`
- `legacy architecture reference doc`
- `Sentinel-Law/docs/AuditEventMapping.md`
- `Sentinel-Law/backend/app/services/fhir_audit.py`

This means the future generalized product should not merely strip legal language. It also needs a clean shared "sensitive data" vocabulary.

## Recommended target model

### Shared core product logic

Keep these shared and edition-agnostic:

- Tenant/platform management
- Auth and RBAC mechanics
- Provider setup and routing
- Policy engine and validation framework
- Rate limiting
- Audit logging and integrity chain
- Metrics and alerts engine
- Export/reporting engine
- Eval runner
- Settings storage

### Preset-driven concerns

Move these behind preset config:

- Product name and product description
- Landing page, hero copy, and support/help text
- Navigation labels
- Tenant label and role labels
- Policy template catalog
- Default demo tenant, demo users, and seeded eval cases
- Report titles, file names, and context field labels
- Trial request form fields
- Default audit metadata labels
- Default glossary terms

## Best abstraction points

### 1. Terminology map, not immediate schema rewrite

Best first abstraction:

- Treat existing storage fields as aliasable slots in the UI and reporting layer.

Initial alias map for generalized Sentinel default:

- `tenant` -> `organization`
- `matter_id` -> `work item`
- `practice_group` -> `workstream`
- `client_name` -> `customer`
- `Firm AI Rules` -> `AI Rules`

Why:

- This avoids breaking the current DB schema and exports in Prompts 2–3.
- It lets the generalized demo look neutral before any migration.
- It keeps `SentinelLaw` working by swapping in legal labels.

### 2. Preset registry in shared config files

Recommended location:

- `Sentinel/config/presets/<preset-id>/`

Recommended per-preset files:

- `manifest.json`
- `terminology.json`
- `copy.json`
- `roles.json`
- `policy_templates.json`
- `demo_seed.json`

Why JSON:

- Both Python and Next.js can load it without a custom build step.
- It keeps preset content out of code-heavy modules.

### 3. Backend preset loader

Add a thin loader in the backend that:

- selects the active preset
- loads policy templates and default demo seed from preset files
- exposes terminology and preset metadata to the frontend as needed

Do not rewrite gateway logic for this. Only swap the source of copy/templates/defaults.

### 4. Frontend terminology provider

Add a small frontend layer that resolves labels from the active preset:

- product name
- organization label
- rules label
- activity log label
- context field labels
- role display labels

This should be consumed by pages/components rather than hardcoded strings.

## Where terminology mapping should live

Primary source of truth:

- `Sentinel/config/presets/<preset-id>/terminology.json`

Suggested contents:

- `product_name`
- `console_name`
- `tenant.singular`
- `tenant.plural`
- `rules_label`
- `activity_log_label`
- `report_label`
- `context_fields.primary_id`
- `context_fields.group`
- `context_fields.external_party`
- `trial_request.organization_label`

Short-term compatibility rule:

- Backend DB fields stay unchanged.
- Frontend and report renderers read preset terminology and relabel those fields.

## Where industry presets should live

Recommended structure:

- `Sentinel/config/presets/default/`
- `Sentinel/config/presets/legal/`

Edition intent:

- `default`: domain-neutral demo preset for generalized Sentinel
- `legal`: SentinelLaw preset preserving current firm/matter/client language and legal policy templates

## Where seed/demo data should live

Recommended location:

- `Sentinel/config/presets/<preset-id>/demo_seed.json`

Move these out of hardcoded Python:

- default tenant/org name
- demo users
- demo API key names
- demo eval cases
- default template id
- landing page CTA metadata if needed

Backend seed scripts should become loaders of preset data, not owners of preset content.

## Recommended role generalization strategy

Keep backend permission codes stable first:

- `super_admin`
- `tenant_admin`
- `auditor`
- `developer`
- `viewer`

Do not rename DB/API role codes in the first generalization pass.

Instead:

- map role display labels and descriptions through preset config
- optionally rename `tenant_admin` in UI to `Org Admin`
- optionally rename `developer` in UI to `Integration Admin` or `Operator`
- keep capability checks code-based, not label-based

Why:

- avoids migration churn
- preserves tests and API compatibility
- lets SentinelLaw keep legal labels while generic Sentinel gets neutral labels

## Recommended risk taxonomy split

### Shared risk taxonomy

These belong in shared core:

- prompt injection
- embedded instruction hijacking
- hidden prompt/system prompt exposure
- secret exfiltration attempts
- unsafe/sensitive request patterns
- provider failures
- blocked-by-policy outcomes
- generic sensitive-data exposure score and flags

### Legal-specific risk taxonomy

These should live in the legal preset:

- matter-specific examples and sample identifiers
- client confidentiality framing
- ABA Rule 1.6 or legal ethics references
- contracts, pleadings, annexes, legal drafting examples
- legal-specific system prompt prefixes

### Naming recommendation

Short-term:

- keep `phi` in the API/backend for compatibility

Medium-term:

- introduce a shared neutral alias such as `sensitive_data` or `confidentiality`
- gradually shift UI/report copy to the neutral label
- leave `phi` as an internal compatibility field until migrations are worth it

## Phased implementation plan for Prompts 2–5

### Prompt 2: preset and terminology scaffolding

Goal:

- introduce the minimal preset/config system without changing core behavior

Work:

- add preset directory structure under `config/presets/`
- create `default` and `legal` preset configs
- define shared terminology schema
- define shared preset manifest schema
- add a tiny backend preset loader
- add a tiny frontend terminology helper/provider

Do not do:

- DB schema changes
- role code changes
- gateway logic rewrites

Primary files to add/change:

- new root preset files under `config/presets/`
- future generalized equivalents of:
  - `backend/app/services/policy_templates.py`
  - `frontend/src/components/layout/app-shell.tsx`

### Prompt 3: frontend copy and terminology extraction

Goal:

- make the UI domain-neutral by default while preserving a legal preset

Work:

- replace hardcoded `SentinelLaw`, `firm`, `matter`, `practice group`, `client`, `Firm AI Rules` strings with preset-driven labels
- generalize landing page, help page, nav, dashboard, logs, users, firms screens
- make report/export filenames and titles preset-driven

Primary files to change first:

- `Sentinel-Law/frontend/src/components/layout/app-shell.tsx`
- `Sentinel-Law/frontend/src/app/page.tsx`
- `Sentinel-Law/frontend/src/app/request-trial-button.tsx`
- `Sentinel-Law/frontend/src/app/(app)/dashboard/page.tsx`
- `Sentinel-Law/frontend/src/app/(app)/logs/page.tsx`
- `Sentinel-Law/frontend/src/app/(app)/policies/page.tsx`
- `Sentinel-Law/frontend/src/app/(app)/users/page.tsx`
- `Sentinel-Law/frontend/src/app/(app)/help/page.tsx`

### Prompt 4: backend preset extraction and seed generalization

Goal:

- externalize legal preset content from backend code

Work:

- move policy template definitions into preset files
- make seed script consume preset demo seed
- generalize trial request payload from `firm_name` to a preset-driven org label in UI, then backend
- stop auto-seeding new tenants with hardcoded legal template ids
- make alert/report labels read terminology config where feasible

Primary files to change first:

- `Sentinel-Law/backend/app/services/policy_templates.py`
- `Sentinel-Law/backend/app/scripts/seed_demo.py`
- `Sentinel-Law/backend/app/api/routes/platform_tenants.py`
- `Sentinel-Law/backend/app/api/routes/public.py`
- `Sentinel-Law/backend/tests/test_policies_templates_seed.py`

### Prompt 5: metadata abstraction, compatibility aliases, and cleanup

Goal:

- make audit/report context generic without breaking existing legal flows

Work:

- treat `matter_id`, `practice_group`, `client_name` as preset-labeled context fields in UI/reports
- optionally add generic aliases in API payload handling while still honoring old legal headers
- separate shared confidentiality language from legal-specific language
- isolate or clearly label FHIR/healthcare compatibility as legacy or optional
- update tests, docs, and exports

Only if still needed after aliasing:

- design an additive generic context object for future schema expansion

Avoid in this phase unless unavoidable:

- renaming existing DB columns
- destructive migrations

Primary files to change first:

- `Sentinel-Law/backend/app/services/gateway.py`
- `Sentinel-Law/backend/app/api/routes/gateway.py`
- `Sentinel-Law/backend/app/services/metrics_service.py`
- `Sentinel-Law/backend/app/services/audit_reports.py`
- `Sentinel-Law/backend/app/api/routes/audit.py`
- `Sentinel-Law/frontend/src/lib/schemas.ts`
- `Sentinel-Law/frontend/src/app/(app)/logs/page.tsx`
- `Sentinel-Law/frontend/src/app/(app)/dashboard/page.tsx`

## Risks and migration concerns

### 1. Audit schema coupling

`matter_id`, `practice_group`, and `client_name` are wired through:

- DB model
- migrations
- gateway metadata
- metrics
- report generation
- frontend schemas and filters

This is the biggest structural coupling. Use label aliasing first.

### 2. Policy template coupling

Legal template ids are referenced by:

- seed scripts
- tenant bootstrap
- tests
- policies UI

Changing ids too early will break demo flows and tests.

### 3. String-coupled tests

E2E and backend tests depend on:

- legal emails
- firm labels
- exact demo API key names
- exact policy template ids

Tests need to be migrated alongside preset extraction, not after.

### 4. Existing customer/demo compatibility

If any running environment already uses:

- legal template ids
- legal headers
- report filenames
- exported JSON fields

then the generalized platform must preserve those as the legal edition behavior.

### 5. Mixed legal and healthcare naming

The repo already mixes:

- legal terminology
- generic governance terms
- healthcare/PHI/FHIR language

If cleaned piecemeal, the result will stay inconsistent. The right split is:

- shared neutral naming in core
- legal preset naming in legal preset
- optional healthcare compatibility called out explicitly if retained

## Likely files and modules to modify next

Highest-value next changes:

- `Sentinel-Law/frontend/src/components/layout/app-shell.tsx`
- `Sentinel-Law/frontend/src/app/page.tsx`
- `Sentinel-Law/frontend/src/app/(app)/dashboard/page.tsx`
- `Sentinel-Law/frontend/src/app/(app)/logs/page.tsx`
- `Sentinel-Law/frontend/src/app/(app)/policies/page.tsx`
- `Sentinel-Law/frontend/src/app/(app)/users/page.tsx`
- `Sentinel-Law/frontend/src/app/(app)/help/page.tsx`
- `Sentinel-Law/backend/app/services/policy_templates.py`
- `Sentinel-Law/backend/app/scripts/seed_demo.py`
- `Sentinel-Law/backend/app/api/routes/platform_tenants.py`
- `Sentinel-Law/backend/app/services/gateway.py`
- `Sentinel-Law/backend/app/services/audit_reports.py`
- `Sentinel-Law/backend/app/services/metrics_service.py`
- `Sentinel-Law/backend/app/db/models.py`

## Recommendation summary

Do first:

- add preset config and terminology mapping
- make UI/report labels preset-driven
- externalize legal templates and demo seed data

Delay until later:

- DB column renames
- role code renames
- gateway contract breaks

Preserve as SentinelLaw edition:

- legal policy templates
- legal role labels
- legal landing/report copy
- legal demo seed data
- legal audit vocabulary
