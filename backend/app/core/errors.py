from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.core.request_context import get_request_id


ERROR_MESSAGES: dict[str, str] = {
    "AUTH_REQUIRED": "Authentication required.",
    "FORBIDDEN": "You do not have access to this resource.",
    "TENANT_SCOPE_ERROR": "Organization context is required.",
    "PROVIDER_UNAVAILABLE": "The AI provider is currently unavailable.",
    "PROVIDER_TIMEOUT": "The AI provider did not respond in time.",
    "POLICY_BLOCKED": "Blocked by AI Rules.",
    "VALIDATION_ERROR": "The request could not be processed.",
    "EXPORT_FAILED": "Unable to generate the requested export.",
    "INTERNAL_ERROR": "An unexpected error occurred.",
    "NOT_FOUND": "The requested resource was not found.",
    "RATE_LIMITED": "Too many requests.",
    "CONFLICT": "The request conflicts with existing data.",
}


@dataclass(slots=True)
class ApiError(Exception):
    status_code: int
    code: str
    detail: str | None = None
    message: str | None = None
    retryable: bool = False
    extra: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] | None = None

    def __post_init__(self) -> None:
        Exception.__init__(self, self.detail or self.message or self.code)
        if self.message is None:
            self.message = ERROR_MESSAGES.get(self.code, "Request failed.")


@dataclass(slots=True)
class ProviderServiceError(Exception):
    status_code: int
    detail: str
    retryable: bool
    code: str
    provider_status_code: int | None = None
    error_class: str | None = None
    attempt_trace: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        Exception.__init__(self, self.detail)


def error_payload(
    *,
    code: str,
    message: str | None = None,
    detail: str | None = None,
    retryable: bool = False,
    request_id: str | None = None,
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message or ERROR_MESSAGES.get(code, "Request failed."),
            "detail": detail,
            "request_id": request_id or get_request_id(),
            "retryable": retryable,
        }
    }


def error_response(
    *,
    status_code: int,
    code: str,
    message: str | None = None,
    detail: str | None = None,
    retryable: bool = False,
    extra: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    payload = error_payload(code=code, message=message, detail=detail, retryable=retryable)
    payload["detail"] = detail or payload["error"]["message"]
    if extra:
        payload.update(extra)
    return JSONResponse(status_code=status_code, content=payload, headers=headers)


def raise_api_error(
    *,
    status_code: int,
    code: str,
    detail: str | None = None,
    message: str | None = None,
    retryable: bool = False,
    extra: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> None:
    raise ApiError(
        status_code=status_code,
        code=code,
        detail=detail,
        message=message,
        retryable=retryable,
        extra=extra or {},
        headers=headers,
    )


def _http_detail_text(detail: Any) -> str | None:
    if detail is None:
        return None
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        parts: list[str] = []
        for item in detail:
            if isinstance(item, dict) and item.get("msg"):
                parts.append(str(item["msg"]))
            else:
                parts.append(str(item))
        return "; ".join(parts)
    return str(detail)


def map_http_exception(exc: HTTPException) -> ApiError:
    detail = _http_detail_text(exc.detail)
    status_code = int(exc.status_code)
    lowered = (detail or "").lower()

    if status_code == status.HTTP_401_UNAUTHORIZED:
        message = "Authentication failed." if "invalid credential" in lowered else ERROR_MESSAGES["AUTH_REQUIRED"]
        return ApiError(status_code=status_code, code="AUTH_REQUIRED", detail=detail, message=message, headers=exc.headers)
    if "tenant context required" in lowered or "tenant override not permitted" in lowered or "invalid x-tenant-id" in lowered:
        return ApiError(
            status_code=status_code,
            code="TENANT_SCOPE_ERROR",
            detail=detail,
            message=ERROR_MESSAGES["TENANT_SCOPE_ERROR"],
            headers=exc.headers,
        )
    if status_code == status.HTTP_403_FORBIDDEN:
        return ApiError(status_code=status_code, code="FORBIDDEN", detail=detail, headers=exc.headers)
    if status_code in {status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY}:
        return ApiError(status_code=status_code, code="VALIDATION_ERROR", detail=detail, headers=exc.headers)
    if status_code == status.HTTP_404_NOT_FOUND:
        return ApiError(status_code=status_code, code="NOT_FOUND", detail=detail, headers=exc.headers)
    if status_code == status.HTTP_409_CONFLICT:
        return ApiError(status_code=status_code, code="CONFLICT", detail=detail, headers=exc.headers)
    if status_code == status.HTTP_429_TOO_MANY_REQUESTS:
        return ApiError(status_code=status_code, code="RATE_LIMITED", detail=detail, message=ERROR_MESSAGES["RATE_LIMITED"], retryable=True, headers=exc.headers)
    if status_code == status.HTTP_504_GATEWAY_TIMEOUT:
        return ApiError(status_code=status_code, code="PROVIDER_TIMEOUT", detail=detail, retryable=True, headers=exc.headers)
    if status_code in {status.HTTP_502_BAD_GATEWAY, status.HTTP_503_SERVICE_UNAVAILABLE}:
        return ApiError(status_code=status_code, code="PROVIDER_UNAVAILABLE", detail=detail, retryable=True, headers=exc.headers)
    if status_code >= 500:
        return ApiError(status_code=status_code, code="INTERNAL_ERROR", detail=detail, headers=exc.headers)
    return ApiError(status_code=status_code, code="VALIDATION_ERROR", detail=detail, headers=exc.headers)


def api_error_from_request_validation(exc) -> ApiError:
    detail = _http_detail_text(exc.errors())
    return ApiError(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code="VALIDATION_ERROR",
        detail=detail,
    )


def api_error_response_from_exception(request: Request, exc: ApiError) -> JSONResponse:
    return error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        detail=exc.detail,
        retryable=exc.retryable,
        extra=exc.extra,
        headers=exc.headers,
    )
