# Presets

## Overview

Sentinel uses a preset system to keep one shared product core while presenting different vertical editions. The default shared product is `general`. `legal`, `finance`, and `healthcare` are vertical presets layered on the same platform.

The preset system is intentionally lightweight:

- shared backend and frontend logic remain in `backend/` and `frontend/`
- preset definitions live in `config/presets/<preset-id>/`
- the active preset changes visible terminology, product naming, demo framing, default policy template selection, and seeded demo data

## Sentinel vs SentinelLaw

- `Sentinel` is the shared platform and the default conceptual product.
- `SentinelLaw` is the legal preset, with legal terminology such as `Firm`, `Matter`, `Practice Group`, and `Client Audit Report`.
- Legal-specific docs and policy templates remain in the repo as a preserved vertical edition, not as the shared default.

## Preset file structure

Each preset lives in:

```text
config/presets/<preset-id>/
```

Current presets:

- `general`
- `legal`
- `finance`
- `healthcare`

Each preset directory contains:

- `manifest.json`
  Purpose: product identity, support email, default policy template id, demo defaults.
- `terminology.json`
  Purpose: visible labels for organizations, rules, reports, workflow entities, and user-facing messages.
- `copy.json`
  Purpose: landing page and trial/onboarding copy.
- `roles.json`
  Purpose: display labels/descriptions for canonical roles.
- `risk_taxonomy.json`
  Purpose: shared vs preset-specific risk categories shown in the product.
- `demo_seed.json`
  Purpose: seeded org, users, providers, policy versions, activity examples, approval events, reports, and evals for that preset.

## How presets are loaded

Backend:

- loader: `backend/app/core/presets.py`
- default preset id: `general`
- active preset source: `SENTINEL_PRESET`
- key helpers:
  - `list_presets()`
  - `get_preset()`
  - `get_active_preset_id()`
  - `get_demo_seed()`
  - `build_public_app_config()`

Frontend:

- loader: `frontend/src/lib/app-config-server.ts`
- default preset id: `general`
- active preset sources, in order:
  - `sentinel_preset` cookie
  - `NEXT_PUBLIC_SENTINEL_PRESET`
  - `SENTINEL_PRESET`
  - fallback to `general`

## Terminology mapping

Terminology is preset-driven rather than scattered across components.

Primary mapping file:

- `config/presets/<preset-id>/terminology.json`

Typical fields:

- `organization_singular`
- `organization_plural`
- `organization_context`
- `rules_label`
- `report_label`
- `activity_log_label`
- `workflow.primary_entity_label`
- `workflow.secondary_entity_label`
- `workflow.external_party_label`
- `messages.blocked_by_rules`

Examples:

- `general`: `Organization`, `Work Item`, `Workstream`, `Audit Report`
- `legal`: `Firm`, `Matter`, `Practice Group`, `Client Audit Report`
- `finance`: `Institution`, `Engagement`, `Desk`, `Oversight Report`
- `healthcare`: `Care Organization`, `Case`, `Department`, `Safety Review Report`

Compatibility note:

- underlying storage fields like `matter_id`, `practice_group`, and `client_name` still exist for compatibility
- shared UI surfaces read them through preset terminology instead of exposing legal names by default

## Roles

Canonical shared roles are:

- `org_admin`
- `compliance_admin`
- `operator`
- `reviewer`
- `auditor`

Legacy roles remain accepted for compatibility, but preset files control display labels and descriptions.

## Adding a new preset

1. Create a new directory:

```text
config/presets/<new-preset>/
```

2. Add:

- `manifest.json`
- `terminology.json`
- `copy.json`
- `roles.json`
- `risk_taxonomy.json`
- `demo_seed.json`

3. Choose a distinct:

- product name
- terminology mapping
- default policy template id
- demo org identity and activity examples

4. If the preset needs unique policy examples, add new templates in:

- `backend/app/services/policy_templates.py`

5. If needed, add or update tests in:

- `backend/tests/test_presets.py`
- `backend/tests/test_policies_templates_seed.py`

## Known boundaries

- The preset layer changes framing, terminology, demo content, and defaults.
- It does not replace core product capabilities such as provider routing, policy enforcement, audit logging, metrics, alerts, or eval infrastructure.
- Some legal compatibility names still exist in schema fields and route names for stability.
