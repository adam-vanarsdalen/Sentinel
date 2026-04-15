# SentinelLaw Pilot Plan

Milestones are ordered for an end-to-end working “pilot” with Docker Compose.

## M0 — Scaffold + Local Runtime
- Repo structure (`backend/`, `frontend/`, `docs/`, `infra/`)
- `docker-compose.yml` (postgres, redis, backend, worker, frontend)
- `.env.example` + secrets guidance

## M1 — Backend Core (Multi-tenant + Auth + Audit)
- Tenants, users, RBAC (`super_admin`, `tenant_admin`, `auditor`, `developer`, `viewer`)
- Email/password auth + JWT for UI
- API keys for gateway usage (hashed at rest)
- Immutable audit event table + basic export endpoints

## M2 — LLM Gateway
- `POST /v1/chat/completions` (OpenAI-compatible-ish)
- Provider routing: `mock` (deterministic) + `openai` (optional)
- Validation: prompt length, allowed models, rate limiting
- Usage/cost estimation + metadata logging

## M3 — Policy Engine (Pilot Scope)
- Tenant policy schema (allowed models, max tokens, regex blocks, system prefix, output validation)
- Preflight enforcement + postflight flags

## M4 — Risk Signals (Pilot Heuristics)
- Confidential-data heuristic scanner (score + masked snippets)
- Prompt injection + security flags (signals, not guarantees)

## M5 — Admin Dashboard (Next.js)
- Login + tenant selector (for `super_admin`)
- Overview analytics, logs table, API keys management, policy editor, evaluations UI

## M6 — Evaluation Harness
- Seeded test suite
- Runner (async task) + results storage + UI trends

## M7 — Tests + Docs Completion
- Minimal unit/integration tests: tenant isolation, policy block, API key auth, audit event creation
- Docs: architecture, threat model, logging/retention, deployment, audit export mapping (optional), references
