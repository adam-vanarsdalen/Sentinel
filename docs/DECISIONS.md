# Architectural Decisions

This file captures major implementation decisions and rationale.

## ADR-001: FastAPI backend

- Decision: Use FastAPI for gateway/admin APIs.
- Why: clear request modeling, async capability, ecosystem fit with Python governance logic.

## ADR-002: Next.js frontend

- Decision: Use Next.js for admin console and server-side API proxy pattern.
- Why: strong TypeScript DX, pragmatic full-stack routing, deploy flexibility.

## ADR-003: PostgreSQL primary datastore

- Decision: Store tenancy, policy, users, keys, and audit data in PostgreSQL.
- Why: transactional integrity, mature indexing/query model, clear migration workflow via Alembic.

## ADR-004: Redis + Celery for async/background work

- Decision: Use Redis for rate-limit counters and Celery broker/backend.
- Why: straightforward operational model and separation of sync gateway path vs async eval tasks.

## ADR-005: Provider abstraction layer

- Decision: Keep provider-specific adapters behind a shared provider interface.
- Why: consistent policy/routing behavior and easier expansion across providers.

## ADR-006: Preset-driven shared platform

- Decision: Keep one core product and apply vertical framing via presets.
- Why: avoid duplicated codebases while preserving SentinelLaw and enabling non-legal demos.

## ADR-007: Governance-first gateway orientation

- Decision: Treat policy, routing controls, and audit events as first-class runtime concerns.
- Why: Sentinel’s value is control-plane behavior, not simple model passthrough.
