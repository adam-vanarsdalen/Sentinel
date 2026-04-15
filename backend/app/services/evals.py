from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models import EvalResult, EvalRun, EvalTestCase, TenantPolicy
from app.services.policy import DEFAULT_POLICY
from app.services.phi import scan_phi
from app.services.security_flags import detect_security_signals

logger = logging.getLogger(__name__)


def run_eval_suite_sync(run_id: str) -> None:
    db: Session = SessionLocal()
    tenant_id: str | None = None
    try:
        run = db.get(EvalRun, run_id)
        if not run:
            return
        tenant_id = run.tenant_id
        run.status = "running"
        db.add(run)
        db.commit()

        cases = db.query(EvalTestCase).filter(EvalTestCase.tenant_id == run.tenant_id).all()
        policy_row = db.get(TenantPolicy, run.tenant_id)
        policy = policy_row.policy_json if policy_row else DEFAULT_POLICY

        passed = 0
        for c in cases:
            prompt_text = "\n".join([m.get("content", "") for m in c.input_messages])
            sec = detect_security_signals(prompt_text)
            phi = scan_phi(prompt_text)

            expected = set(c.expected_flags or [])
            observed = set(sec.flags)
            ok = expected.issubset(observed) if expected else True
            if ok:
                passed += 1

            db.add(
                EvalResult(
                    tenant_id=run.tenant_id,
                    run_id=run.id,
                    test_case_id=c.id,
                    passed=ok,
                    observed_flags=sorted(observed),
                    phi_score=phi.score,
                    risk_severity=sec.severity,
                    details={"policy_allowed_models": policy.get("allowed_models", [])},
                )
            )
        run.status = "finished"
        run.finished_at = datetime.now(timezone.utc)
        run.summary = {"total": len(cases), "passed": passed, "failed": len(cases) - passed}
        db.add(run)
        db.commit()
    except Exception:
        # Best-effort: mark run failed and log for operators.
        try:
            db.rollback()
        except Exception:
            pass
        try:
            run = db.get(EvalRun, run_id)
            if run:
                tenant_id = run.tenant_id
                run.status = "failed"
                run.finished_at = datetime.now(timezone.utc)
                db.add(run)
                db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
        logger.exception("Eval suite execution failed", extra={"tenant_id": tenant_id})
    finally:
        db.close()
