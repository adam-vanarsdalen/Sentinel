# Logging & Retention (Pilot Defaults)

This document summarizes what SentinelLaw logs, what is intentionally *not* logged by default, and recommended retention/handling practices aligned to NIST SP 800-92 guidance (see `docs/References.md`).

## Logging goals
- Support defensible AI activity logging for legal environments (who/what/when/outcome).
- Enable governance metrics (volume, model usage, estimated cost).
- Generate security signals (confidential-data risk, prompt injection cues) without storing raw content by default.

## What SentinelLaw logs (pilot)

For each LLM request or admin action, SentinelLaw writes an immutable `audit_events` row including:
- `tenant_id`, `api_key_id`, optional `user_id`
- timestamp, action type, outcome + reason
- model/provider
- confidential-data risk score + risk flags + severity
- token usage (actual if returned by provider; estimated otherwise) + approximate cost

## Content handling policy (pilot)

- Default: store `prompt_hash` + `response_hash` only (SHA-256).
- Optional (tenant policy): store redacted snippets (first ~200 chars with patterns masked).
- Disabled by default: raw prompt/response persistence.

## Retention recommendations (pilot)

NIST SP 800-92 emphasizes defining and enforcing log management policies, including retention and protection of log data.

Recommended starting point for pilot deployments:
- Online searchable retention: 30–90 days (operational monitoring)
- Archive retention: 1–6 years depending on organizational policy and regulatory needs

SentinelLaw does not hard-code retention; you should implement DB-level retention/archival procedures appropriate for your environment.

## Protection & access
- Restrict access to audit exports by role (`auditor` / `tenant_admin` / `super_admin`).
- Treat audit logs as sensitive data (potential sensitive client data in redacted snippets if enabled).
- Prefer centralization and integrity controls (append-only storage, backups, access logging).
