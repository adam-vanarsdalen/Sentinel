from __future__ import annotations

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
    # In production, restrict metrics access at the network layer. As a defense-in-depth option,
    # allow configuring a simple token check via METRICS_TOKEN.
    if settings.metrics_token and x_metrics_token != settings.metrics_token:
        return Response(status_code=404)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


async def metrics_middleware(request: Request, call_next):
    path = request.url.path
    method = request.method
    with LATENCY.labels(path=path, method=method).time():
        resp = await call_next(request)
    REQUESTS.labels(path=path, method=method, status=str(resp.status_code)).inc()
    return resp
