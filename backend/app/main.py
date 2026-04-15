from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.errors import ApiError, api_error_from_request_validation, api_error_response_from_exception, map_http_exception
from app.core.logging import configure_logging
from app.core.metrics import metrics_middleware, metrics_router
from app.core.request_context import request_id_middleware


configure_logging()
logger = logging.getLogger(__name__)

docs_enabled = (settings.environment or "").strip().lower() != "production"

app = FastAPI(
    title="Sentinel Backend",
    version="0.1.0",
    debug=False,
    docs_url="/docs" if docs_enabled else None,
    redoc_url="/redoc" if docs_enabled else None,
    openapi_url="/openapi.json" if docs_enabled else None,
)

if settings.jwt_secret == "dev":
    logger.warning("JWT_SECRET is set to the insecure default 'dev'. Set a strong random JWT_SECRET for production.")
if settings.seed_demo:
    logger.warning("SEED_DEMO is enabled. Disable SEED_DEMO for production deployments unless explicitly required.")
if "*" in settings.cors_origins_list:
    logger.warning("CORS_ORIGINS includes '*'. Do not use wildcard CORS origins in production.")

app.middleware("http")(metrics_middleware)
app.middleware("http")(request_id_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    if exc.status_code >= 500:
        logger.error("API error response", extra={"error_code": exc.code, "status_code": exc.status_code})
    return api_error_response_from_exception(request, exc)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return api_error_response_from_exception(request, map_http_exception(exc))


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    return api_error_response_from_exception(request, api_error_from_request_validation(exc))


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Avoid leaking internal details to clients; always log for investigation.
    logger.exception("Unhandled server exception")
    return api_error_response_from_exception(request, ApiError(status_code=500, code="INTERNAL_ERROR"))


app.include_router(api_router)
app.include_router(metrics_router)
