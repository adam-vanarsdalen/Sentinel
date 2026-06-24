# Contributing

## Development Setup

**Requirements:** Python 3.11+, Node.js 20+, Docker, Docker Compose

```bash
git clone https://github.com/adam-vanarsdalen/Sentinel.git
cd Sentinel

# Start infrastructure
docker compose up -d postgres redis

# Backend
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Open http://localhost:3000.

---

## Project Layout

```
backend/
  layers/          # One file per pipeline layer (layer1_ingestion.py … layer7_compliance.py)
  services/        # Business logic: kill switch, anomaly engine, compliance generator
  api/             # FastAPI routers — one file per resource
  models/          # SQLAlchemy ORM models
  schemas/         # Pydantic request/response schemas
  regulatory/      # Regulation-to-control-ID mappers
  tests/           # pytest suites

frontend/
  src/app/         # Next.js App Router pages
  src/components/  # React components
  src/hooks/       # Data-fetching and WebSocket hooks
  src/lib/         # API client, TypeScript types
```

---

## Running Tests

```bash
cd backend
pytest --tb=short
```

74 tests across all layers. All must pass before submitting a PR.

To run a specific layer's tests:

```bash
pytest tests/test_layers/test_layer3.py -v
pytest tests/test_layers/test_layer6.py -v
pytest tests/test_layers/test_layer7.py -v
```

---

## Architecture Invariants

These rules are enforced by tests. Do not break them.

1. **Layer 3 runs before Layer 4.** Enforcement checks happen before any provider API call. The pipeline orchestrator (`services/pipeline.py`) enforces this order.

2. **Audit-first kill switch transitions.** In `services/kill_switch.py`, every state transition writes to `audit_log` before writing to Redis. If the audit write fails, the Redis write must not happen.

3. **Append-only audit log.** Never add UPDATE or DELETE paths to `audit_log`. The PostgreSQL role-level constraint will reject them anyway, but the application code must not attempt them.

4. **request_id threads through all layers.** The UUID4 generated in Layer 1 must appear in every audit entry, alert, and Redis key for that request.

5. **Regulation control IDs must match `skills/compliance-mapper.md` exactly.** Any new control added to the regulatory mappers in `backend/regulatory/` must use the canonical ID format defined in that file.

---

## Adding a New Regulation

1. Create `backend/regulatory/<regulation_name>.py` with a `CONTROLS` dict mapping layer numbers to control ID lists.
2. Register it in `backend/regulatory/mapper.py`.
3. Add test cases to `tests/test_layers/test_layer7.py` verifying the new control IDs appear in audit entries.
4. Document the control descriptions in `docs/compliance.md`.

---

## Adding a New Layer Check (Layer 3)

Layer 3 enforcement checks are additive. To add a new check:

1. Implement it as a private async function in `backend/layers/layer3_enforcement.py`.
2. Call it from `layer3_enforce()` in the correct order (kill switch → action limit → purpose binding → forbidden endpoints → your check).
3. If the check blocks, return `EnforcementCheck(allowed=False, blocked_reason="...")`.
4. Add test cases to `tests/test_layers/test_layer3.py`.
5. Update the regulatory mappings if the check satisfies new controls.

---

## Pull Request Checklist

- [ ] All 74 existing tests pass
- [ ] New tests added for new functionality
- [ ] Layer I/O signatures match `skills/layer-interface.md`
- [ ] Regulation control IDs match `skills/compliance-mapper.md`
- [ ] No UPDATE or DELETE on `audit_log`
- [ ] Kill switch transitions write audit before Redis

---

## Commit Style

Use conventional commits:

```
feat: add GDPR Article 22 mapping to Layer 3
fix: correct throttle window check in kill switch
test: add Layer 6 cross-agent correlation cases
docs: update compliance mapping for NIST MANAGE-2.4
```
