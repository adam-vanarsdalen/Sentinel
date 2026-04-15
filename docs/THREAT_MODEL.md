# Threat Model

## Scope

This model covers Sentinel as an AI governance gateway/control plane for multi-tenant enterprise workflows.

## Assets to protect

- tenant isolation and tenant metadata
- policy definitions and version history
- gateway API keys and user auth sessions
- provider credentials and routing policy
- audit events and reporting artifacts
- operational availability of inference governance path

## Trust boundaries

- browser/admin users to frontend/backend auth APIs
- application clients to gateway API key boundary
- backend to model provider boundary
- backend/worker to PostgreSQL + Redis

## Threat actors

- external attacker targeting auth/API keys
- malicious or negligent tenant user
- compromised integration client
- insider/operator with elevated system access
- prompt-level adversary embedding hidden instructions

## Key risks and mitigations

### Prompt injection and instruction manipulation

- Risks: model override attempts, hidden instruction payloads in documents/comments
- Mitigations: heuristic injection detection, policy-controlled block modes, required system prompt prefix, structured risk flags/audit capture

### Confidential data exposure / leakage

- Risks: sensitive data sent to providers or leaked in output
- Mitigations: confidential-data heuristics, policy thresholds and blocking, default no raw content storage, optional redacted snippets only

### Weak auth/session handling

- Risks: credential abuse, token replay, insecure cookie/session handling
- Mitigations: JWT issuer/audience/expiry checks, httpOnly cookie model in frontend proxy path, role-based API guards

### Tenant isolation failure

- Risks: cross-tenant data reads/writes or context confusion
- Mitigations: tenant-scoped queries/writes, explicit tenant context enforcement, role-gated platform tenant switching

### Audit tampering

- Risks: event mutation/deletion reducing defensibility
- Mitigations: append-only posture, database-level protections for Postgres deployments, hash-chain verification endpoints, export support

### Unsafe logging

- Risks: accidental storage of raw prompt/response or credentials
- Mitigations: raw content off by default, redaction controls, restricted secret handling, recommended retention controls

### Provider misuse / routing bypass

- Risks: unapproved provider/model usage, hidden fallback behavior
- Mitigations: tenant-approved provider/model enforcement, explicit fallback configuration, routing decision audit events

## Open risks / future hardening

- stronger default production secrets posture and secret scanning gates
- SSO/SAML and enterprise identity lifecycle integration
- broader automated detection coverage for novel injection patterns
- stronger immutable audit export workflows outside primary DB
- optional physical tenant isolation for stricter environments
