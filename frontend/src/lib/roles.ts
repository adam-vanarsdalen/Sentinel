import type { Role } from "./schemas";

export const ASSIGNABLE_ROLES = ["org_admin", "compliance_admin", "operator", "reviewer", "auditor"] as const;

export function hasAnyRole(role: Role | null | undefined, allowed: readonly Role[]) {
  return !!role && allowed.includes(role);
}

export function isPlatformAdmin(role: Role | null | undefined) {
  return role === "super_admin";
}
