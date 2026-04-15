from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from fastapi import Depends
from pydantic import BaseModel

from app.api.deps import DbDep, require_role
from app.core.model_catalog import normalize_model_id, normalize_provider_id
from app.db.models import EvalResult, EvalRun, EvalTestCase, User
from app.services.evals import run_eval_suite_sync

router = APIRouter()


class EvalRunRequest(BaseModel):
    provider: str
    model: str


EvalRunner = Annotated[User, Depends(require_role("super_admin", "org_admin", "operator"))]
EvalReader = Annotated[User, Depends(require_role("super_admin", "org_admin", "compliance_admin", "operator", "reviewer", "auditor"))]


@router.post("/run", response_model=dict)
def run_eval(req: EvalRunRequest, db: DbDep, user: EvalRunner, bg: BackgroundTasks) -> dict:
    tenant_id = user.effective_tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")

    try:
        provider = normalize_provider_id(req.provider, allow_mock=True)
        model = normalize_model_id(provider, req.model, allow_empty=False)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    run = EvalRun.new(tenant_id=tenant_id, provider=provider, model=model)
    db.add(run)
    db.commit()
    db.refresh(run)

    # Pilot: run synchronously in a background task (Celery integration can be enabled later).
    bg.add_task(run_eval_suite_sync, run.id)
    return {"run_id": run.id, "status": run.status}


@router.get("/runs", response_model=list[dict])
def list_runs(db: DbDep, user: EvalReader) -> list[dict]:
    tenant_id = user.effective_tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")
    runs = (
        db.query(EvalRun)
        .filter(EvalRun.tenant_id == tenant_id)
        .order_by(EvalRun.started_at.desc())
        .limit(100)
        .all()
    )
    return [r.to_dict() for r in runs]


@router.get("/suites", response_model=list[dict])
def list_suites(db: DbDep, user: EvalReader) -> list[dict]:
    tenant_id = user.effective_tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")
    cases = (
        db.query(EvalTestCase)
        .filter(EvalTestCase.tenant_id == tenant_id)
        .order_by(EvalTestCase.created_at.asc())
        .all()
    )
    return [
        {
            "id": c.id,
            "name": c.name,
            "category": c.category,
            "input_messages": c.input_messages,
            "expected_flags": c.expected_flags or [],
            "created_at": c.created_at.isoformat(),
        }
        for c in cases
    ]


@router.get("/runs/{run_id}", response_model=dict)
def get_run(run_id: str, db: DbDep, user: EvalReader) -> dict:
    tenant_id = user.effective_tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")
    run = db.get(EvalRun, run_id)
    if not run or run.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    results = (
        db.query(EvalResult)
        .filter(EvalResult.tenant_id == tenant_id, EvalResult.run_id == run_id)
        .all()
    )
    return {
        "run": run.to_dict(),
        "results": [
            {
                "id": r.id,
                "test_case_id": r.test_case_id,
                "passed": r.passed,
                "observed_flags": r.observed_flags or [],
                "phi_score": r.phi_score,
                "risk_severity": r.risk_severity,
                "details": r.details or {},
            }
            for r in results
        ],
    }
