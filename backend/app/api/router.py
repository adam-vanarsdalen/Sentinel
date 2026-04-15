from fastapi import APIRouter

from app.api.routes import alerts, audit, auth, evals, gateway, health, keys, metrics, platform_tenants, policies, provider_configs, public, settings, tenants, users

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(public.router, prefix="/public", tags=["public"])
api_router.include_router(keys.router, prefix="/admin/api-keys", tags=["admin"])
api_router.include_router(tenants.router, prefix="/admin/tenants", tags=["admin"])
api_router.include_router(policies.router, prefix="/admin/policy", tags=["admin"])
api_router.include_router(settings.router, prefix="/admin/settings", tags=["admin"])
api_router.include_router(alerts.router, prefix="/admin/alerts", tags=["admin"])
api_router.include_router(provider_configs.router, prefix="/admin/provider-configs", tags=["admin"])
api_router.include_router(audit.router, prefix="/admin/audit-events", tags=["admin"])
api_router.include_router(audit.integrity_router, prefix="/audit/integrity", tags=["audit"])
api_router.include_router(metrics.router, prefix="/admin/metrics", tags=["admin"])
api_router.include_router(evals.router, prefix="/admin/evals", tags=["admin"])
api_router.include_router(users.router, prefix="/admin/users", tags=["admin"])

api_router.include_router(platform_tenants.router, prefix="/platform/tenants", tags=["platform"])

api_router.include_router(gateway.router, prefix="/v1", tags=["gateway"])
