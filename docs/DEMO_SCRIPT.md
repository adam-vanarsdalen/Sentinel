# Demo Script

This script supports two formats:

- 5-minute recruiter/overview demo
- 15-minute enterprise governance demo

Use default Sentinel framing (`general`) unless your audience asks for legal-specific flow (`legal` preset / SentinelLaw).

## Demo prep

1. Start stack: `docker compose up --build -d`
2. Confirm health: `http://localhost:8000/ready`
3. Log in:
- Org admin: `admin@demoorg.com` / `ChangeMe!12345`
- Platform admin: `platform-admin@example.com` / `ChangeMe!12345`

Optional legal mode login:
- `admin@demolaw.com` / `ChangeMe!12345`

## 5-minute recruiter flow

1. Landing + login
- Show Sentinel as governed AI infrastructure.
- Explain it is a control layer between applications and model providers.

2. Dashboard
- Show request volume, policy outcomes, risk flags, and cost trend.
- Explain this is governance visibility, not just model usage analytics.

3. Policy page
- Show policy controls and versioned governance posture.
- Mention allow/block/flag/review workflow.

4. Logs/audit page
- Show structured events and export options.
- Explain defensibility: who did what, when, and why decisions were made.

5. Preset switch
- Switch to legal preset to show SentinelLaw framing without changing core product.

## 15-minute enterprise flow

1. Governance context
- Why AI usage needs tenant controls, provider restrictions, and auditability.

2. Provider settings
- Show approved providers/models and default route controls.
- Explain policy-aware provider routing.

3. Policy engine behavior
- Show configurable controls and expected outcomes.
- Explain preflight + postflight checks.

4. AI activity log and reporting
- Filter high-severity events.
- Open an event and walk through outcome/reason/risk flags.
- Export report (CSV/JSON/PDF or summary format).

5. Users/roles
- Show org admin, compliance, reviewer, and auditor boundaries.

6. Platform admin (optional)
- Show multi-org model and preset-aware organization metadata.

## Handling common questions

- "Is this replacing legal/compliance judgment?"
- "No. Sentinel enforces controls and provides evidence; human decision-making remains required."

- "Do you store raw prompts and responses?"
- "Default posture is metadata/hashes with optional redacted snippets."

- "Can this work outside legal?"
- "Yes. Sentinel is shared core; SentinelLaw is one vertical preset."
