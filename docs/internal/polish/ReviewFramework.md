# SentinelLaw Polish Review Framework

This framework is the checklist used for the product-wide review and polish pass. It is designed for a **law firm pilot** where security, auditability, and usability matter, while keeping scope realistic.

## 1) Security and GenAI Risk Checklist (OWASP LLM Top 10 framing)
Goal: reduce common LLM application risks without over-claiming “perfect detection”.

For each category, verify:
- The platform has a clear control (prevent / detect / respond).
- The control is tenant-scoped and auditable.
- Defaults minimize sensitive data storage.
- UI explains limitations as “signals”, not guarantees.

Checklist:
- Prompt injection defenses: preflight blocks, system prompt hardening, “signals” in logs, explainability.
- Sensitive information disclosure: redaction defaults, “do not store raw content” by default, export warnings.
- Data/Model poisoning considerations: document non-goals, guardrails for evaluation datasets, admin change audit.
- Insecure output handling: output validation rules, safe formatting, no automatic execution behavior.
- Excessive agency: ensure gateway does not perform unintended external actions.
- Supply chain risks: dependency hygiene, pinned versions, container builds.
- Authentication and authorization: least privilege RBAC, no UI-only auth, API key hashing.
- Rate limiting and DoS: per-tenant and per-key controls, safe failure modes.
- Logging and monitoring: structured logs, correlation IDs, no secret leakage.

## 2) AI Governance Checklist (NIST AI RMF 1.0 functions)
Goal: support governance conversations with compliance/ops stakeholders.

### GOVERN
- Roles and responsibilities are clear (who can change policy/settings/keys/users).
- Every admin change writes an audit event with “who/what/when”.
- Defaults reflect a conservative stance on confidential-data handling.

### MAP
- Document what SentinelLaw does and does not do (not legal advice; not a DMS).
- Identify where AI is used (apps/api keys) and the intended purpose.
- Identify impact areas: client confidentiality, operational risk, vendor dependency, uptime.

### MEASURE
- Provide metrics and evaluation harness to measure drift and regressions.
- Provide explainable flags and confidential-data heuristic scores (with limitations).
- Track policy blocks and trends.

### MANAGE
- Provide change control flows: policy draft → test → publish.
- Provide remediation flows: revoke key, tighten policy, rerun evaluations.
- Provide export and retention guidance to support audits.

## 3) Log Management Checklist (NIST SP 800-92 principles)
Goal: make logs useful for audits and incident response.

Checklist:
- Collection: ensure all important actions create audit events (LLM calls, policy blocks, confidential-data flags, admin changes).
- Storage: immutability of audit events (append-only, no edits).
- Protection: avoid storing raw sensitive content by default; avoid secrets in logs.
- Analysis: filters, saved views, export, and drill-down support typical investigations.
- Retention: defaults and guidance are documented; “full content storage” requires explicit confirmation.
- Integrity: correlation/request IDs, timestamps, and consistent schemas.

## 4) Audit Event Modeling Checklist (Structured Export Readiness)
Goal: produce audit events that can be mapped conceptually to a standardized audit schema for downstream review tools.

Checklist:
- Actor (who): user_id, api_key_id, tenant_id are recorded.
- Action (what): consistent `action_type`, `outcome`, and `reason`.
- Context (where/when): timestamps, provider/model, request identifiers.
- Export: provide JSON export that can be shaped for downstream systems (pilot mapping).
- Documentation: mapping explains what is supported and what is not (pilot scope).

## 5) SaaS Product Quality Checklist
Goal: “enterprise clean” UX + maintainable code + reliable behavior.

### Usability and consistency
- Navigation and page layouts are consistent.
- Empty states explain “what to do next”.
- Export and long-running operations show progress and clear outcomes.
- Copy-to-clipboard actions provide confirmation feedback.

### Reliability and error handling
- Clear, non-technical error messages for end users.
- Detailed errors available for admins (without leaking secrets/confidential data).
- Frontend gracefully handles missing data and network errors.

### Maintainability
- Typed API client aligned with backend schemas.
- Consistent pagination/filtering conventions.
- Minimal duplication; shared components for tables, dialogs, forms.

### Observability
- Structured logs are consistent and include correlation IDs.
- Metrics endpoint is stable and documented.
- Health/readiness endpoints exist and are documented.
