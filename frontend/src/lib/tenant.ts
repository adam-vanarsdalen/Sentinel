import * as React from "react";

const KEY = "sentinel_active_tenant_id";
const OVERRIDE_KEY = "sentinel_tenant_override_enabled";
const EVENT = "sentinel-tenant-change";

export function getActiveTenantId(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function isTenantOverrideEnabled(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(OVERRIDE_KEY) === "1";
  } catch {
    return false;
  }
}

export function setTenantOverrideEnabled(enabled: boolean) {
  if (typeof window === "undefined") return;
  try {
    if (enabled) window.localStorage.setItem(OVERRIDE_KEY, "1");
    else window.localStorage.removeItem(OVERRIDE_KEY);
    window.dispatchEvent(new Event(EVENT));
  } catch {
    // ignore
  }
}

export function setActiveTenantId(tenantId: string | null) {
  if (typeof window === "undefined") return;
  try {
    if (tenantId) window.localStorage.setItem(KEY, tenantId);
    else window.localStorage.removeItem(KEY);
    window.dispatchEvent(new Event(EVENT));
  } catch {
    // ignore
  }
}

export function useActiveTenantId(): string | null {
  const [tenantId, setTenantId] = React.useState<string | null>(() => getActiveTenantId());

  React.useEffect(() => {
    function refresh() {
      setTenantId(getActiveTenantId());
    }
    window.addEventListener("storage", refresh);
    window.addEventListener(EVENT, refresh);
    return () => {
      window.removeEventListener("storage", refresh);
      window.removeEventListener(EVENT, refresh);
    };
  }, []);

  return tenantId;
}
