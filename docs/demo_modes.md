# Demo Modes

## Overview

Sentinel ships with four preset-owned demo organizations:

- `general`: `Northwind Operations`
- `legal`: `Calder & Pine LLP`
- `finance`: `Harborview Capital Advisors`
- `healthcare`: `Riverbend Care Network`

The default first-run experience is the `general` preset and the `Northwind Operations` demo org.

## Where demo data lives

Each preset owns its demo definition in:

```text
config/presets/<preset-id>/demo_seed.json
```

That file defines:

- org name, slug, profile, summary
- users and canonical roles
- seeded API keys
- provider settings and restrictions
- policy versions
- settings and alerts
- AI activity log entries
- review and approval events
- audit/export context
- evaluation cases and run results

The backend seeder assembles all demo orgs from those files:

- `backend/app/scripts/seed_demo.py`

## Default demo mode

Use this for the shared Sentinel experience:

```env
SENTINEL_PRESET=general
NEXT_PUBLIC_SENTINEL_PRESET=general
SEED_DEMO=1
DEMO_TENANT_ADMIN_EMAIL=admin@demoorg.com
DEMO_TENANT_ADMIN_PASSWORD=ChangeMe!12345
```

Default logins:

- Org admin: `admin@demoorg.com` / `ChangeMe!12345`
- Platform admin: `platform-admin@example.com` / `ChangeMe!12345`

What it demonstrates:

- organization-first governance framing
- provider controls across internal operations workflows
- prompt-injection blocking
- confidential data exposure flags
- human review and approval events
- exportable audit reporting

## Legal demo mode

Use this when you want the SentinelLaw edition framing:

```env
SENTINEL_PRESET=legal
NEXT_PUBLIC_SENTINEL_PRESET=legal
SEED_DEMO=1
```

Recommended legal login:

- Org admin: `admin@demolaw.com` / `ChangeMe!12345`

What it demonstrates:

- law-firm framing and terminology
- matter/practice-group/client-oriented audit context
- legal policy templates
- strict confidentiality policy history
- partner review and client audit export flows

## Finance demo mode

Use this when you want a regulated-finance framing:

```env
SENTINEL_PRESET=finance
NEXT_PUBLIC_SENTINEL_PRESET=finance
SEED_DEMO=1
```

Recommended finance login:

- Org admin: `admin@harborview.example` / `ChangeMe!12345`

What it demonstrates:

- engagement/desk/counterparty terminology
- committee memo workflows
- provider fallback governance
- approval-required outbound commentary
- oversight exports

## Healthcare demo mode

Use this when you want a healthcare-safety framing:

```env
SENTINEL_PRESET=healthcare
NEXT_PUBLIC_SENTINEL_PRESET=healthcare
SEED_DEMO=1
```

Recommended healthcare login:

- Org admin: `admin@riverbend.example` / `ChangeMe!12345`

What it demonstrates:

- case/department/patient terminology
- discharge-summary and care-plan workflows
- PHI-sensitive review paths
- safety-policy blocking
- clinical oversight exports

## Runtime demo switching

The landing page and authenticated shell include a preset selector. It writes a `sentinel_preset` cookie and refreshes server-loaded config so you can switch visible framing without redeploying.

Use the selector when:

- you want to compare vertical terminology quickly
- you want one running environment for multiple demos

Use environment variables when:

- you want a fixed default preset at startup
- you are running a guided demo and want the first impression pinned to one edition

## Notes

- All four demo orgs are seeded together when `SEED_DEMO=1`.
- `general` remains the default first-run login path.
- Legal compatibility is preserved by also seeding `admin@demolaw.com` and `demo-contract-review` for the legal org.
