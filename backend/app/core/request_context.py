from __future__ import annotations

import uuid
from contextvars import ContextVar

from starlette.requests import Request
from starlette.responses import Response

_request_id: ContextVar[str | None] = ContextVar("sentinel_request_id", default=None)
_tenant_id: ContextVar[str | None] = ContextVar("sentinel_tenant_id", default=None)


def get_request_id() -> str | None:
    return _request_id.get()


def get_tenant_id() -> str | None:
    return _tenant_id.get()


def set_tenant_id(tenant_id: str | None) -> None:
    _tenant_id.set(tenant_id)


async def request_id_middleware(request: Request, call_next):
    # Allow upstream (reverse proxy / gateway) to provide an ID for correlation.
    incoming = request.headers.get("x-request-id")
    rid = incoming.strip() if incoming and incoming.strip() else str(uuid.uuid4())
    token = _request_id.set(rid)
    tenant_token = _tenant_id.set(None)
    try:
        resp: Response = await call_next(request)
        resp.headers["X-Request-Id"] = rid
        return resp
    finally:
        _tenant_id.reset(tenant_token)
        _request_id.reset(token)
