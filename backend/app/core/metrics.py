from __future__ import annotations

from hmac import compare_digest
from time import perf_counter
from typing import Annotated, Optional

from fastapi import APIRouter, Header
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings

REQUESTS = Counter("sentinel_http_requests_total", "HTTP requests", ["path", "method", "status"])
LATENCY = Histogram("sentinel_http_request_latency_seconds", "HTTP latency", ["path", "method"])

metrics_router = APIRouter()


@metrics_router.get("/metrics")
def metrics(x_metrics_token: Annotated[Optional[str], Header()] = None) -> Response:
    configured_token = (settings.metrics_token or "").strip()
    provided_token = (x_metrics_token or "").strip()
    env = (settings.environment or "").strip().lower()

    if env == "production" and not configured_token:
        return Response(status_code=404)

    if configured_token and not compare_digest(provided_token, configured_token):
        return Response(status_code=404)

    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def _metrics_path_label(request: Request) -> str:
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    if isinstance(route_path, str) and route_path:
        return route_path
    return "__unmatched__"


async def metrics_middleware(request: Request, call_next):
    method = request.method
    started = perf_counter()
    try:
        resp = await call_next(request)
    finally:
        elapsed = perf_counter() - started
    path_label = _metrics_path_label(request)
    LATENCY.labels(path=path_label, method=method).observe(elapsed)
    REQUESTS.labels(path=path_label, method=method, status=str(resp.status_code)).inc()
    return resp
