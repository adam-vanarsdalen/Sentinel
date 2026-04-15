"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { RequireTenantScope } from "@/components/layout/require-tenant";
import { RequireRole } from "@/components/layout/require-role";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api-client";
import { Badge } from "@/components/ui/badge";
import { hasAnyRole, isPlatformAdmin } from "@/lib/roles";
import { useActiveTenantId } from "@/lib/tenant";

export default function EvalCaseDetailPage() {
  const params = useParams<{ id: string }>();
  const id = String(params.id);
  const tenantId = useActiveTenantId();

  const meQuery = useQuery({ queryKey: ["me"], queryFn: () => api.auth.me() });
  const canView = hasAnyRole(meQuery.data?.role, ["org_admin", "operator", "super_admin"]);
  const tenantReady = !!meQuery.data && (!isPlatformAdmin(meQuery.data.role) || !!tenantId);

  const suitesQuery = useQuery({ queryKey: ["evals", "suites"], queryFn: () => api.evals.suites(), enabled: canView && tenantReady });
  const item = (suitesQuery.data ?? []).find((c) => c.id === id) ?? null;

  return (
    <main className="space-y-4" data-testid="eval-case-detail">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Test Case</h1>
        <Link className="text-sm text-slate-700 hover:underline" href="/evaluations">
          Back to tests
        </Link>
      </div>

      <RequireRole allow={["super_admin", "org_admin", "operator"]}>
        <RequireTenantScope>
          {suitesQuery.isLoading ? (
            <div className="text-sm text-slate-600">Loading…</div>
          ) : suitesQuery.isError ? (
            <div className="text-sm text-red-700">Failed to load suite.</div>
          ) : !item ? (
            <div className="rounded border border-slate-200 bg-white p-4 text-sm text-slate-700">Case not found.</div>
          ) : (
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
              <Card className="lg:col-span-1">
                <CardHeader className="p-4">
                  <CardTitle className="text-base">Metadata</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 p-4 pt-0 text-sm">
                  <div className="font-medium">{item.name}</div>
                  <div className="text-slate-600">{item.category}</div>
                  <div className="text-xs text-slate-600">Test case ID</div>
                  <div className="font-mono text-xs">{item.id}</div>
                  <div className="text-xs text-slate-600">Expected flags</div>
                  <div className="flex flex-wrap gap-1">
                    {(item.expected_flags ?? []).length ? (
                      (item.expected_flags ?? []).map((f) => <Badge key={f}>{f}</Badge>)
                    ) : (
                      <span className="text-sm text-slate-600">—</span>
                    )}
                  </div>
                </CardContent>
              </Card>

              <Card className="lg:col-span-2">
                <CardHeader className="p-4">
                  <CardTitle className="text-base">Input Messages</CardTitle>
                </CardHeader>
                <CardContent className="p-4 pt-0">
                  <pre className="max-h-[520px] overflow-auto rounded bg-slate-100 p-3 text-xs">
                    {JSON.stringify(item.input_messages, null, 2)}
                  </pre>
                </CardContent>
              </Card>
            </div>
          )}
        </RequireTenantScope>
      </RequireRole>
    </main>
  );
}
