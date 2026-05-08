# Red-Team Before/After Summary (2026-04-15)

## Scope
- Prompt set: `b1t001` to `b1t020` (safe adversarial prompts).
- Runtime path: live gateway `/v1/chat/completions` via `handle_chat_completion`.

## Initial Run (Before Fixes)
- Source: reconstructed from persisted `audit_events` tied to original API key name `redteam-eval` (`artifacts/redteam_initial_reconstructed.json`).
- Result: `20/20` prompts were allowed through Sentinel preflight (HTTP `200`, `LLM_REQUEST success`).
- Provider/model observed: `ollama` / `gpt-oss:120b-cloud`.
- Note: restricted-content leak status for this initial run is `unknown` in reconstruction because response snippets were not persisted in these audit rows.

## Post-Fix Run (After Fixes)
- Source: live rerun report (`artifacts/redteam_after.json`).
- Result: `20/20` prompts blocked at Sentinel preflight (HTTP `403`).
- Main block stages used:
  - `preflight_hidden_guidance_exfiltration`
  - `preflight_instruction_override`
  - `preflight_internal_enforcement_logic`
  - `preflight_sensitive_data_aggregation`
  - `preflight_internal_config_exfiltration`

## Key Root Causes Found
- Missing/too-narrow preflight patterns for:
  - hidden-guidance laundering language
  - multi-domain sensitive-data aggregation packaging requests
  - internal-control disclosure phrasing
  - “use any available tools/logs/config sources” exfiltration phrasing
- Red-team script reliability issue:
  - fixed API key name (`redteam-eval`) caused collisions on reruns.

## Fix Summary
- Tightened targeted preflight detectors in `backend/app/services/policy.py` without disabling core controls.
- Improved malicious regression diagnostics in `backend/tests/test_gateway_false_positive_fix.py` (prompt index included on assertion failure).
- Made red-team tooling rerunnable by generating unique API key names per run in `backend/app/scripts/run_redteam_eval.py`.
