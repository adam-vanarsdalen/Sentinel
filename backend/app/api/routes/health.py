from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from redis import Redis
from sqlalchemy import text

from app.api.deps import DbDep
from app.core.config import settings
from app.core.presets import get_active_preset_id, get_demo_defaults, get_demo_seed, get_product_name, list_presets
from app.db.models import Tenant
from app.services.policy_templates import list_policy_templates

router = APIRouter()


def _health_payload() -> dict:
    return {"ok": True, "version": settings.app_version, "preset_id": get_active_preset_id(), "product_name": get_product_name()}


@router.get("/health")
@router.get("/healthz")
def healthz() -> dict:
    return _health_payload()


@router.get("/ready")
@router.get("/readyz")
def readyz(db: DbDep) -> dict:
    checks: dict[str, dict] = {}

    # 1) DB reachable
    try:
        db.execute(text("SELECT 1"))
        checks["db"] = {"ok": True}
    except Exception as e:
        # Avoid leaking internal DB error details via an unauthenticated endpoint.
        checks["db"] = {"ok": False, "error": "db_unreachable", "type": e.__class__.__name__}

    # 2) Redis reachable
    try:
        Redis.from_url(settings.redis_url).ping()
        checks["redis"] = {"ok": True}
    except Exception as e:
        checks["redis"] = {"ok": False, "error": "redis_unreachable", "type": e.__class__.__name__}

    # 3) Demo tenants exist (only when demo seeding is enabled)
    if settings.seed_demo:
        try:
            demo_checks: list[dict] = []
            for preset in list_presets():
                preset_id = str(preset.get("id") or "").strip().lower()
                if not preset_id:
                    continue
                demo_seed = get_demo_seed(preset_id)
                tenant_meta = demo_seed.get("tenant") if isinstance(demo_seed, dict) else None
                demo_name = ""
                if isinstance(tenant_meta, dict):
                    demo_name = str(tenant_meta.get("name") or "").strip()
                if not demo_name:
                    demo_defaults = get_demo_defaults(preset_id)
                    demo_name = str(demo_defaults.get("organization_name") or "Demo Organization")
                demo = db.query(Tenant.id).filter(Tenant.name == demo_name).first()
                demo_checks.append({"preset_id": preset_id, "name": demo_name, "ok": bool(demo)})
            checks["demo_tenants"] = {"ok": all(item["ok"] for item in demo_checks), "items": demo_checks}
        except Exception as e:
            checks["demo_tenants"] = {"ok": False, "error": "demo_tenant_check_failed", "type": e.__class__.__name__}
    else:
        checks["demo_tenants"] = {"ok": True, "skipped": True, "reason": "SEED_DEMO disabled"}

    # 4) Policy templates available (code-defined templates)
    try:
        templates = list_policy_templates()
        checks["policy_templates"] = {"ok": len(templates) > 0, "count": len(templates)}
    except Exception as e:
        checks["policy_templates"] = {"ok": False, "error": "policy_templates_check_failed", "type": e.__class__.__name__}

    ok = all(bool(v.get("ok")) for v in checks.values())
    payload = {"ok": ok, "checks": checks}
    if ok:
        return payload
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=payload)
