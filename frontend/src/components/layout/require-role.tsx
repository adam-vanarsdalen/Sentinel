"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api-client";
import { HttpError } from "@/lib/http";
import type { Role } from "@/lib/schemas";

export function RequireRole({ allow, children }: { allow: Role[]; children: React.ReactNode }) {
  const router = useRouter();
  const meQuery = useQuery({ queryKey: ["me"], queryFn: () => api.auth.me() });

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

  React.useEffect(() => {
    if (redirectingRef.current) return;
    if (!meQuery.data) return;
    if (allow.includes(meQuery.data.role)) return;
    redirectingRef.current = true;
    router.replace("/forbidden");
  }, [allow, meQuery.data, router]);

  if (meQuery.isLoading) return <div className="text-sm text-slate-600">Loading…</div>;
  if (meQuery.isError) {
    const err = meQuery.error;
    if (err instanceof HttpError && err.status === 401) {
      return <div className="text-sm text-slate-600">Signing you out…</div>;
    }
    return <div className="text-sm text-red-700">Failed to load session.</div>;
  }
  const me = meQuery.data;
  if (!me) return <div className="text-sm text-red-700">Failed to load session.</div>;
  if (!allow.includes(me.role)) {
    return <div className="text-sm text-slate-600">Redirecting…</div>;
  }
  return <>{children}</>;
}
