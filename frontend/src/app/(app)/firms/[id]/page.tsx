"use client";

import * as React from "react";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { RequireRole } from "@/components/layout/require-role";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription as DialogDesc, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api } from "@/lib/api-client";
import { useAppConfig } from "@/lib/app-config-context";
import { setActiveTenantId } from "@/lib/tenant";
import { useToast } from "@/components/toaster";
import { HttpError } from "@/lib/http";
import { isPlatformAdmin } from "@/lib/roles";

type Tab = "overview" | "settings" | "activity";

export default function FirmDetailPage() {
  const appConfig = useAppConfig();
  const params = useParams<{ id: string }>();
  const tenantId = String(params.id);
  const router = useRouter();
  const qc = useQueryClient();
  const toast = useToast();
  const orgSingular = appConfig.terminology.organization_singular;
  const orgContext = appConfig.terminology.organization_context;
  const presetNames = React.useMemo(
    () => Object.fromEntries(appConfig.available_presets.map((preset) => [preset.id, preset.name])),
    [appConfig.available_presets],
  );

  const meQuery = useQuery({ queryKey: ["me"], queryFn: () => api.auth.me() });
  const canView = isPlatformAdmin(meQuery.data?.role);

  const [tab, setTab] = React.useState<Tab>("overview");
  const [range, setRange] = React.useState<"24h" | "7d" | "30d">("7d");

  const firmQuery = useQuery({
    queryKey: ["platformTenants", "get", tenantId],
    queryFn: () => api.platformTenants.get(tenantId),
    enabled: canView,
  });
  const summaryQuery = useQuery({
    queryKey: ["platformTenants", "summary", tenantId, range],
    queryFn: () => api.platformTenants.summary(tenantId, range),
    enabled: canView,
  });

  const switchMut = useMutation({
    mutationFn: async () => api.platformTenants.switch(tenantId),
    onSuccess: async (res) => {
      setActiveTenantId(res.current_tenant.id);
      await qc.invalidateQueries({ queryKey: ["me"] });
      toast.push({ title: `Switched ${orgContext} context`, description: res.current_tenant.name });
      router.push("/dashboard");
    },
  });

  const firm = firmQuery.data?.tenant ?? null;

  const [name, setName] = React.useState("");
  const [slug, setSlug] = React.useState("");
  const [status, setStatus] = React.useState("active");
  const [saveError, setSaveError] = React.useState<string | null>(null);
  const [confirmStatusOpen, setConfirmStatusOpen] = React.useState(false);
  const [pendingStatusChange, setPendingStatusChange] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!firm) return;
    setName(firm.name);
    setSlug(firm.slug ?? "");
    setStatus(firm.status ?? "active");
  }, [firm]);

  const saveMut = useMutation({
    mutationFn: async () => api.platformTenants.update(tenantId, { name, slug, status }),
    onSuccess: async () => {
      setSaveError(null);
      await qc.invalidateQueries({ queryKey: ["platformTenants", "get", tenantId] });
      await qc.invalidateQueries({ queryKey: ["platformTenants"] });
      toast.push({ title: `${orgSingular} updated` });
    },
    onError: (e) => {
      if (e instanceof HttpError && e.status === 409) setSaveError("Slug already exists.");
      else setSaveError(`Failed to update ${orgContext}.`);
    },
  });

  const activityQuery = useQuery({
    queryKey: ["audit", "search", "firm", tenantId],
    queryFn: () =>
      api.audit.search(
        {
          limit: 25,
          offset: 0,
        },
        { tenantId },
      ),
    enabled: canView,
  });

  return (
    <RequireRole allow={["super_admin"]}>
      <main className="space-y-4" data-testid="firm-detail">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-xl font-semibold">{firm ? firm.name : orgSingular}</h1>
            {firm ? <div className="text-xs text-slate-600">{orgSingular} (Tenant): {firm.slug}</div> : null}
            {firm ? (
              <div className="mt-2 flex flex-wrap gap-2">
                {firm.preset_id ? <Badge variant="secondary">{presetNames[firm.preset_id] ?? firm.preset_id}</Badge> : null}
                {firm.demo_profile ? <Badge variant="secondary">{firm.demo_profile}</Badge> : null}
              </div>
            ) : null}
            {firm?.demo_summary ? <div className="mt-2 max-w-2xl text-sm text-slate-600">{firm.demo_summary}</div> : null}
          </div>
          <Button variant="outline" disabled={switchMut.isPending || !firm || firm.status !== "active"} onClick={() => switchMut.mutate()}>
            {switchMut.isPending ? "Switching…" : `Switch to this ${orgContext}`}
          </Button>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button variant={tab === "overview" ? "default" : "outline"} onClick={() => setTab("overview")}>
            Overview
          </Button>
          <Button variant={tab === "settings" ? "default" : "outline"} onClick={() => setTab("settings")}>
            Settings
          </Button>
          <Button variant={tab === "activity" ? "default" : "outline"} onClick={() => setTab("activity")}>
            Activity
          </Button>
        </div>

        {tab === "overview" ? (
          <div className="space-y-3">
            <Card>
              <CardHeader className="p-4">
                <CardTitle className="text-base">Usage summary</CardTitle>
                <CardDescription>Key metrics from the AI activity log.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 p-4 pt-0">
                <div className="w-[220px]">
                  <Select value={range} onValueChange={(v) => setRange(v as any)}>
                    <SelectTrigger aria-label="Time range">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="24h">Last 24 hours</SelectItem>
                      <SelectItem value="7d">Last 7 days</SelectItem>
                      <SelectItem value="30d">Last 30 days</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {summaryQuery.isLoading ? (
                  <div className="text-sm text-slate-600">Loading…</div>
                ) : summaryQuery.isError ? (
                  <div className="text-sm text-red-700">Failed to load summary.</div>
                ) : summaryQuery.data ? (
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
                    <Metric title="Requests" value={summaryQuery.data.summary.cards.total_requests} />
                    <Metric title="Policy blocks" value={summaryQuery.data.summary.cards.policy_blocks} />
                    <Metric title="Confidential data flagged" value={summaryQuery.data.summary.cards.phi_flagged} />
                    <Metric title="Est. cost (USD)" value={summaryQuery.data.summary.cards.estimated_cost_usd.toFixed(2)} />
                  </div>
                ) : null}
              </CardContent>
            </Card>
          </div>
        ) : null}

        {tab === "settings" ? (
          <Card>
            <CardHeader className="p-4">
              <CardTitle className="text-base">{orgSingular} Profile</CardTitle>
              <CardDescription>Edit {orgContext} metadata. Slug must be URL-safe.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 p-4 pt-0">
              <div className="space-y-1">
                <div className="text-xs text-slate-600">Name</div>
                <Input value={name} onChange={(e) => setName(e.target.value)} />
              </div>
              <div className="space-y-1">
                <div className="text-xs text-slate-600">Slug</div>
                <Input value={slug} onChange={(e) => setSlug(e.target.value)} />
                <div className="text-xs text-slate-600">Format: `a-z`, `0-9`, hyphens.</div>
              </div>
              <div className="space-y-1">
                <div className="text-xs text-slate-600">Status</div>
                <Select value={status} onValueChange={setStatus}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="active">active</SelectItem>
                    <SelectItem value="suspended">suspended</SelectItem>
                    <SelectItem value="archived">archived</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {saveError ? <div className="rounded border border-red-200 bg-red-50 p-2 text-xs text-red-900">{saveError}</div> : null}

              <Dialog open={confirmStatusOpen} onOpenChange={setConfirmStatusOpen}>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Confirm status change</DialogTitle>
                    <DialogDesc>Change {orgContext} status to {pendingStatusChange ?? "—"}? This may restrict access for {orgContext} users.</DialogDesc>
                  </DialogHeader>
                  <DialogFooter>
                    <Button
                      variant="outline"
                      onClick={() => {
                        setConfirmStatusOpen(false);
                        setPendingStatusChange(null);
                      }}
                    >
                      Cancel
                    </Button>
                    <Button
                      onClick={() => {
                        setConfirmStatusOpen(false);
                        setPendingStatusChange(null);
                        saveMut.mutate();
                      }}
                    >
                      Confirm
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>

              <div className="flex items-center gap-2">
                <Button
                  disabled={!firm || saveMut.isPending}
                  onClick={() => {
                    if (firm && firm.status !== status && (status === "suspended" || status === "archived")) {
                      setPendingStatusChange(status);
                      setConfirmStatusOpen(true);
                      return;
                    }
                    saveMut.mutate();
                  }}
                >
                  {saveMut.isPending ? "Saving…" : "Save"}
                </Button>
                <Button variant="outline" onClick={() => router.push("/firms")}>
                  Back
                </Button>
              </div>
            </CardContent>
          </Card>
        ) : null}

        {tab === "activity" ? (
          <Card>
            <CardHeader className="p-4">
              <CardTitle className="text-base">Recent activity</CardTitle>
              <CardDescription>Most recent audit events for this {orgContext}.</CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              {activityQuery.isLoading ? (
                <div className="p-4 text-sm text-slate-600">Loading…</div>
              ) : activityQuery.isError ? (
                <div className="p-4 text-sm text-red-700">Failed to load activity.</div>
              ) : (
                <div className="overflow-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 text-xs text-slate-600">
                      <tr className="border-b">
                        <th className="px-3 py-2 text-left">Time</th>
                        <th className="px-3 py-2 text-left">Action</th>
                        <th className="px-3 py-2 text-left">Outcome</th>
                        <th className="px-3 py-2 text-left">Reason</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(activityQuery.data?.items ?? []).map((e) => (
                        <tr key={e.id} className="border-b">
                          <td className="px-3 py-2 whitespace-nowrap">{new Date(e.timestamp).toLocaleString()}</td>
                          <td className="px-3 py-2 font-mono text-xs">{e.action_type}</td>
                          <td className="px-3 py-2">{e.outcome}</td>
                          <td className="px-3 py-2 text-xs text-slate-700">{e.reason ?? "—"}</td>
                        </tr>
                      ))}
                      {(activityQuery.data?.items ?? []).length === 0 ? (
                        <tr>
                          <td colSpan={4} className="px-3 py-6 text-center text-sm text-slate-600">
                            No recent activity.
                          </td>
                        </tr>
                      ) : null}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        ) : null}
      </main>
    </RequireRole>
  );
}

function Metric({ title, value }: { title: string; value: any }) {
  return (
    <div className="rounded border border-slate-200 bg-white p-3">
      <div className="text-xs text-slate-600">{title}</div>
      <div className="mt-1 text-lg font-semibold tabular-nums">{value ?? "—"}</div>
    </div>
  );
}
