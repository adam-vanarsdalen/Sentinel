from __future__ import annotations

from app.worker import celery
from app.services.evals import run_eval_suite_sync


@celery.task(name="app.tasks.evals.run_eval_suite")
def run_eval_suite(run_id: str) -> None:
    run_eval_suite_sync(run_id)

