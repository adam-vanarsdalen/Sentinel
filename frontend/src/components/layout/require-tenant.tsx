"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api-client";
import { useAppConfig } from "@/lib/app-config-context";
import { HttpError } from "@/lib/http";
import { isPlatformAdmin } from "@/lib/roles";
import { useActiveTenantId } from "@/lib/tenant";

export function RequireTenantScope({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const meQuery = useQuery({ queryKey: ["me"], queryFn: () => api.auth.me() });
  const tenantId = useActiveTenantId();
  const appConfig = useAppConfig();

  const redirectingRef = React.useRef(false);
  React.useEffect(() => {
    if (redirectingRef.current) return;
    if (!meQuery.isError) return;
    const err = meQuery.error;
    if (err instanceof HttpError && err.status === 401) {
      redirectingRef.current = true;
      fetch("/api/auth/logout", { method: "POST" }).finally(() => {
        router.replace("/login");
      });
    }
  }, [meQuery.isError, meQuery.error, router]);

  if (meQuery.isLoading) return <div className="text-sm text-slate-600">Loading…</div>;
  if (meQuery.isError) {
    const err = meQuery.error;
    if (err instanceof HttpError && err.status === 401) {
      return <div className="text-sm text-slate-600">Signing you out…</div>;
    }
    return <div className="text-sm text-red-700">Failed to load session.</div>;
  }

  if (isPlatformAdmin(meQuery.data?.role) && !tenantId) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        Select a {appConfig.terminology.organization_context} in the top bar to view scoped data.
      </div>
    );
  }
  return <>{children}</>;
}
