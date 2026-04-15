from __future__ import annotations

from fastapi import HTTPException, status


PLATFORM_ADMIN_ROLE = "super_admin"
CORE_ROLES = {"org_admin", "compliance_admin", "operator", "reviewer", "auditor"}
ALL_ROLES = CORE_ROLES | {PLATFORM_ADMIN_ROLE}
LEGACY_ROLE_ALIASES = {
    "tenant_admin": "org_admin",
    "developer": "operator",
    "viewer": "reviewer",
}


def canonical_role(role: str | None) -> str:
    value = str(role or "").strip().lower()
    if not value:
        return ""
    return LEGACY_ROLE_ALIASES.get(value, value)


def is_valid_role(role: str | None, *, allow_platform_admin: bool = True) -> bool:
    value = canonical_role(role)
    if not value:
        return False
    if allow_platform_admin:
        return value in ALL_ROLES
    return value in CORE_ROLES


def normalize_assignable_role(role: str | None) -> str:
    value = canonical_role(role)
    if not is_valid_role(value, allow_platform_admin=False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role. Allowed roles: org_admin, compliance_admin, operator, reviewer, auditor",
        )
    return value


def role_matches(user_role: str | None, allowed_roles: tuple[str, ...]) -> bool:
    candidate = canonical_role(user_role)
    allowed = {canonical_role(role) for role in allowed_roles}
    return candidate in allowed


def storage_values_for_role(role: str) -> list[str]:
    canonical = canonical_role(role)
    values = [canonical]
    for legacy, mapped in LEGACY_ROLE_ALIASES.items():
        if mapped == canonical:
            values.append(legacy)
    return values
