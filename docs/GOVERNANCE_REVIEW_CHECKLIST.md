# Governance Review Checklist

This checklist helps reviewers evaluate Sentinel as an AI governance gateway for regulated teams. It is a public, product-level review guide rather than an internal audit log.

## Security and GenAI Risk Review

For each control, verify that it is tenant-scoped, auditable, and documented with clear limits.

- Prompt injection: preflight blocks, risk signals, explainable policy outcomes, and no claims of perfect detection.
- Sensitive data exposure: redaction-oriented defaults, configurable storage behavior, and export warnings.
- Excessive agency: gateway behavior does not grant unintended external actions.
- Provider routing: tenant-scoped provider settings, encrypted provider secrets, fallback behavior, and audit records.
- Authentication and authorization: role-based access control, API key hashing, login rate limiting, and no UI-only authorization.
- Rate limiting and availability: safe default rate controls and observable failure modes.
- Logging and monitoring: structured logs, request correlation, metrics controls, and no secrets in logs.
- Supply chain: pinned dependencies, Docker builds, CI validation, and Dependabot coverage.

## AI Governance Review

Use this section to evaluate whether the deployment supports governance conversations with security, legal, compliance, and operations stakeholders.

### Govern

- Roles and permissions are clear.
- Admin changes create audit events.
- Defaults reflect a conservative posture for sensitive data.
- Policy changes can be reviewed and tested before rollout.

### Map

- Teams can identify where AI is used through gateway API keys and audit logs.
- Intended use, provider, model, and tenant context are visible.
- Presets are clearly separated from the shared Sentinel platform core.

### Measure

- Policy blocks, flags, usage, and provider outcomes are measurable.
- Evaluation workflows can detect regressions.
- Risk signals are explainable and documented as signals rather than guarantees.

### Manage

- Operators can revoke API keys, adjust provider settings, update policies, and export audit evidence.
- Incidents can be traced with request IDs and audit events.
- Deployment docs describe production controls and required environment variables.

## Log Management Review

Use this section to confirm that audit and operational logs support incident response and compliance review.

- Collection: important actions create audit events, including LLM requests, policy blocks, provider changes, user administration, and authentication events.
- Storage: audit events follow an append-only posture with integrity verification support.
- Protection: raw prompt and response storage is controlled and disabled by default.
- Analysis: logs can be filtered, exported, and correlated with request IDs.
- Retention: retention guidance is documented and production teams can set their own policy.
- Integrity: timestamps, actors, tenant IDs, request IDs, and event hashes are consistently available.

## Product Quality Review

- Navigation and page layouts are consistent.
- Empty states explain the next operational step.
- Error messages are clear without exposing sensitive internals.
- Export and long-running workflows provide visible outcomes.
- API docs, deployment docs, and troubleshooting docs match current behavior.
- Validation commands pass before release.
