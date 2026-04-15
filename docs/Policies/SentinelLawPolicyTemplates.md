# SentinelLaw policy templates (Firm AI Rules)

SentinelLaw ships with built-in “Firm AI Rules” templates designed for law-firm workflows. Templates are a starting point: review and publish them per firm.

## Version history and compare

When a firm publishes a template, SentinelLaw stores the published policy as a tenant-scoped immutable version. The Firm AI Rules page can then:
- show who published the version and when,
- display the change note or auto-generated summary,
- compare a template-derived version against the original template baseline,
- roll back by creating a new active version from an older one without mutating the historical row.

This is important for legal/compliance review: a template is only the starting point, and SentinelLaw preserves the published version history separately from the built-in template definition.

## Summary (which to use)

1) `legal_default_policy_v1` — baseline guardrails for most pilots
- Use when: you want good safety signals (flags) with fewer hard blocks.
- Tradeoff: higher usability, but more risky requests may still go through (flagged, not blocked).

2) `legal_strict_confidentiality_v1` — strict but usable (recommended for client work)
- Use when: you want stronger confidentiality posture and predictable, parseable outputs.
- Tradeoff: blocks more requests and enforces JSON-only responses (your tooling must parse JSON).

3) `legal_strict_no_client_data_v1` — maximum strictness (“sandbox mode”)
- Use when: you want to forbid sending client/sensitive data to AI entirely (training, prompt engineering, public-only work).
- Tradeoff: requires `metadata.data_classification` and blocks on Medium/High confidentiality exposure.

## Template details

### `legal_default_policy_v1` (baseline)
What it does:
- Blocks common prompt-injection strings (e.g., “ignore previous instructions”).
- Keeps heuristic prompt-injection handling in **flag-only** mode (`security.prompt_injection_action = "flag"`), so hidden instructions in comments/annexes are surfaced without blocking by default.
- Adds a legal-focused system prompt prefix.
- Computes a Confidentiality Exposure Level (derived from the stored `phi_score`) and flags when a high threshold is reached (does not block by default).
- Flags possible hidden-instruction disclosures in outputs (does not block by default).

Example use cases:
- Contract review workflows where you want a visible audit trail and risk flags, but you’re still tuning blocks.
- Early demos where you want to show detection before showing enforcement.

### `legal_strict_confidentiality_v1` (strict confidentiality)
Intent: allow drafting/summarization, but treat all inputs as confidential and minimize risk.

Key controls:
- Prompt injection hardening: expanded `block_prompt_patterns` and a stronger system prompt prefix.
- Heuristic prompt-injection enforcement: blocks only when the scanner reaches **HIGH** suspicion (`security.prompt_injection_action = "block_high"`), which is intended to catch obvious embedded or multi-signal attacks while keeping false positives reasonable.
- Confidentiality exposure enforcement: blocks when exposure is HIGH (pilot mapping from `phi_score` 0–100).
- Output validation: blocks if output is not valid JSON, or if it appears to disclose hidden prompts (e.g., “SYSTEM PROMPT”).
- Operational controls: reduced token limits and tighter per-policy rate limits.

When to use:
- Client-matter workflows where the firm wants stronger controls and predictable output parsing.

Tradeoffs:
- JSON-only responses mean downstream tools must parse JSON.
- More false positives (more blocks) compared to the baseline template.

Example prompts (client work):
- “Summarize this clause and return a JSON object with `summary` and `risk_notes` fields.”
- “List potential issues in this contract in JSON as an array of `{ issue, why_it_matters, suggested_fix }`.”

### `legal_strict_no_client_data_v1` (sandbox mode: no client data)
Intent: forbid sending client or sensitive data to AI models at all.

Key controls:
- Prompt injection hardening: blocks **MEDIUM/HIGH** heuristic prompt-injection signals (`security.prompt_injection_action = "block_med"`), including suspicious instructions hidden in comments, annexes, or metadata blocks.
- Hard block: blocks any request with Confidentiality Exposure Level MEDIUM or HIGH.
- Requires classification: request must include `metadata.data_classification` in `{ "PUBLIC", "INTERNAL_NON_CLIENT" }` or it is blocked.
- Output constraints: blocks unless the response is valid JSON matching the required structure.
- Logging posture: raw prompt/response storage remains OFF by default (unchanged).

When to use:
- Training, experimentation, and internal playbooks that must not include client specifics.
- Generic template drafting (no client facts), public-law summaries, and internal non-client policy writing.

Tradeoffs:
- Not suitable for client matters (it will block many real-world inputs).
- Requires your calling tool to set `metadata.data_classification`.

Example calling pattern:
- Send `metadata: { "data_classification": "PUBLIC" }` for public-only tasks.
- If your workflow might contain client data, do not use sandbox mode.

## Notes on privilege and confidentiality

These templates are designed to support common professional responsibilities around confidentiality and competence when using technology:
- Firms should validate that their actual tooling, vendor contracts, and internal policies align with their jurisdiction’s rules and guidance.
- SentinelLaw is designed to keep raw prompt/response storage OFF by default and to provide an audit trail for governance and defensibility.
- The prompt-injection heuristic is intentionally conservative: it improves detection of embedded instructions in legal documents, but it is not a claim of perfect prevention.
