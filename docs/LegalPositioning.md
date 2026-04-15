# SentinelLaw positioning (pilot)

SentinelLaw is a governance layer for law firms using LLMs in drafting and review workflows. It is designed to help firms use AI with better **confidentiality posture**, **auditability**, and **defensible controls**.

This is not legal advice. Firms should review applicable professional responsibility rules and local bar guidance for their jurisdiction (see `docs/References.md`).

## The problem SentinelLaw addresses
Law firms want the productivity upside of AI, but face common risks:
- confidential client data appearing in prompts/outputs
- prompt injection embedded inside contracts, emails, or “copied text”
- unclear “who did what and when” during an incident review
- inconsistent behavior across models and tools

## What SentinelLaw provides

### 1) Firm-scoped AI rules (policy)
SentinelLaw lets a firm centrally enforce rules such as:
- allowed models and token limits
- preflight blocks for common prompt-injection phrases
- a required system prompt prefix that instructs the model not to reveal hidden instructions and not to follow embedded document instructions
- postflight validation flags (e.g., output looks like it contains hidden prompt content)

Built-in starting point: `legal_default_policy_v1` (see `docs/Policies/SentinelLawPolicy.md`).

### 2) AI Activity Log (audit trail)
Every gateway request and admin action produces an immutable audit event, including:
- timestamp, actor (API key/user), model/provider
- outcome (allowed/blocked) and reason
- risk flags (e.g., prompt injection suspected)
- confidential-data risk score (heuristic)

Export supports review workflows and defensibility (CSV/JSON).

### 3) Confidentiality posture by default
SentinelLaw keeps raw prompt/response storage **OFF** by default. Firms can enable redacted snippets or full content storage only with explicit configuration and appropriate retention controls.

### 4) Safety & Consistency Tests
SentinelLaw includes a small evaluation harness (seeded tests) so teams can:
- validate rules before/after policy changes
- detect regressions when changing providers/models

## How to explain this to a firm (short script)
“SentinelLaw is a gateway and governance dashboard for AI drafting tools. It helps us enforce firm AI rules, detect prompt injection and confidential-data risk signals, and keep a defensible audit trail we can export during reviews—without storing raw prompts/responses by default.”

