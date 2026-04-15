from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery = Celery("sentinel", broker=settings.redis_url, backend=settings.redis_url)
celery.conf.task_routes = {"app.tasks.*": {"queue": "sentinel"}}

