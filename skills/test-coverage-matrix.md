# Required Test Coverage Matrix

## Layer 3 — Pre-call enforcement (test_layer3.py)
Must include ALL of these test cases — no exceptions:
- action limit: session at exactly N-1 actions passes, session at N blocks
- action limit: limit of 0 blocks all calls immediately
- purpose binding: call within declared purpose passes
- purpose binding: call accessing data class outside purpose is blocked
- purpose binding: purpose field None on agent = block all tool calls
- forbidden endpoint: exact match blocks
- forbidden endpoint: prefix match blocks (e.g., /admin/* blocks /admin/users)
- forbidden endpoint: non-matching endpoint passes
- kill switch active: passes through to policy checks
- kill switch throttled: first call in window passes, second within 10s blocks
- kill switch paused: all calls return queued status, nothing executes
- kill switch terminated: all calls block, reason includes "terminated"
- tool interception: tool call allowed by policy executes
- tool interception: tool call blocked by policy returns denial message to model
- tool interception: blocked tool call does NOT appear in model's tool_results

## Layer 6 — Anomaly detection (test_layer6.py)
Must include ALL of these test cases:
- frequency anomaly: burst above baseline triggers correct σ level
- cost anomaly: single expensive request against low-cost baseline
- data access anomaly: new data class never seen in baseline
- error rate anomaly: sudden spike in errors
- graduated response: z=2.5 → log only, no containment
- graduated response: z=3.5 → throttle fires via kill switch service
- graduated response: z=5.0 → pause fires via kill switch service
- graduated response: z=7.0 → terminate fires via kill switch service
- cross-agent: two agents same tenant anomalous simultaneously → tenant alert
- new agent (no baseline): no false positives on first 10 requests
- state capture: containment event stores snapshot of last 20 actions

## Layer 7 — Compliance output (test_layer7.py)
Must include ALL of these test cases:
- EU AI Act: all 6 articles map to correct layer events
- NIST AI RMF: GOVERN, MAP, MEASURE, MANAGE all have at least one mapping
- Colorado SB205: disclosure and accuracy controls present
- HIPAA: audit control 164.312(b) maps to Layer 7 events
- gap analysis: control with zero events correctly identified as gap
- gap analysis: gap description names which layer produces the missing evidence
- evidence refs: every evidence_present=True control has at least one audit entry ID
- export JSON: valid JSON, all required fields present
- export PDF: non-empty bytes, opens without error
- append-only: direct UPDATE on audit_log raises psycopg PermissionError
- append-only: direct DELETE on audit_log raises psycopg PermissionError
