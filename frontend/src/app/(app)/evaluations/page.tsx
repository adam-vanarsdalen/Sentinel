"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { RequireTenantScope } from "@/components/layout/require-tenant";
import { RequireRole } from "@/components/layout/require-role";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api } from "@/lib/api-client";
import { useAppConfig } from "@/lib/app-config-context";
import { formatDateTime } from "@/lib/format";
import { hasAnyRole, isPlatformAdmin } from "@/lib/roles";
import { ExposureBadge } from "@/components/exposure-badge";
import { exposureLevelFromScore } from "@/lib/exposure";
import Link from "next/link";
import { useActiveTenantId } from "@/lib/tenant";

const MOCK_PROVIDER = "mock";
const MOCK_MODELS = ["mock"];

export default function EvaluationsPage() {
  const appConfig = useAppConfig();
  const qc = useQueryClient();
  const tenantId = useActiveTenantId();

  React.useEffect(() => {
    document.title = `Evaluations — ${appConfig.product.name}`;
  }, [appConfig.product.name]);

  const meQuery = useQuery({ queryKey: ["me"], queryFn: () => api.auth.me() });
  const canView = hasAnyRole(meQuery.data?.role, ["org_admin", "operator", "super_admin"]);
  const tenantReady = !!meQuery.data && (!isPlatformAdmin(meQuery.data.role) || !!tenantId);
  const providerCatalogQuery = useQuery({
    queryKey: ["providerCatalog"],
    queryFn: () => api.providerConfigs.catalog(),
    enabled: canView && tenantReady,
  });

  const providerModels = React.useMemo(() => {
    const models: Record<string, string[]> = { [MOCK_PROVIDER]: MOCK_MODELS };
    for (const provider of providerCatalogQuery.data?.providers ?? []) {
      models[provider.id] = provider.models.map((model) => model.id);
    }
    return models;
  }, [providerCatalogQuery.data]);
  const providerOptions = React.useMemo(() => [MOCK_PROVIDER, ...((providerCatalogQuery.data?.providers ?? []).map((item) => item.id))], [providerCatalogQuery.data]);

  const suitesQuery = useQuery({ queryKey: ["evals", "suites"], queryFn: () => api.evals.suites(), enabled: canView && tenantReady });
  const runsQuery = useQuery({ queryKey: ["evals", "runs"], queryFn: () => api.evals.runs(), enabled: canView && tenantReady });

  const [runOpen, setRunOpen] = React.useState(false);
  const [provider, setProvider] = React.useState(MOCK_PROVIDER);
  const [model, setModel] = React.useState(MOCK_PROVIDER);
  React.useEffect(() => {
    if (!providerModels[provider] || providerModels[provider].length === 0) {
      setProvider(MOCK_PROVIDER);
      setModel(MOCK_PROVIDER);
      return;
    }
    if (!providerModels[provider].includes(model)) {
      setModel(providerModels[provider][0] ?? MOCK_PROVIDER);
    }
  }, [model, provider, providerModels]);

  const runMut = useMutation({
    mutationFn: async () => api.evals.run(provider, model),
    onSuccess: async (res) => {
      setRunOpen(false);
      setSelectedRunId(res.run_id);
      await qc.invalidateQueries({ queryKey: ["evals", "runs"] });
    },
  });

  const [selectedRunId, setSelectedRunId] = React.useState<string | null>(null);
  const runDetailQuery = useQuery({
    queryKey: ["evals", "run", selectedRunId],
    queryFn: () => api.evals.runDetail(selectedRunId!),
    enabled: !!selectedRunId && canView && tenantReady,
    refetchInterval: (q) => {
      const status = (q.state.data as any)?.run?.status;
      return status && status !== "finished" && status !== "failed" ? 1500 : false;
    },
  });

  const previousRunId = React.useMemo(() => {
    const run = runDetailQuery.data?.run;
    if (!run) return null;
    const sorted = [...(runsQuery.data ?? [])].sort((a, b) => b.started_at.localeCompare(a.started_at));
    const idx = sorted.findIndex((r) => r.id === run.id);
    if (idx < 0) return null;
    const prev = sorted.slice(idx + 1).find((r) => r.provider === run.provider && r.model === run.model);
    return prev?.id ?? null;
  }, [runDetailQuery.data?.run, runsQuery.data]);

  const prevDetailQuery = useQuery({
    queryKey: ["evals", "run", "prev", previousRunId],
    queryFn: () => api.evals.runDetail(previousRunId!),
    enabled: !!previousRunId && canView && tenantReady,
  });

  return (
    <main className="space-y-4" data-testid="evaluations">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Safety & Consistency Tests</h1>
        <Dialog open={runOpen} onOpenChange={setRunOpen}>
          <DialogTrigger asChild>
            <Button>Run suite</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Run test suite</DialogTitle>
              <DialogDescription>Executes seeded test cases against the selected provider/model.</DialogDescription>
            </DialogHeader>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <div className="space-y-1">
                <div className="text-xs text-slate-600">Provider</div>
                <Select
                  value={provider}
                  onValueChange={(v) => {
                    setProvider(v);
                    setModel(providerModels[v]?.[0] ?? MOCK_PROVIDER);
                  }}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {providerOptions.map((providerId) => (
                      <SelectItem key={providerId} value={providerId}>
                        {providerId}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <div className="text-xs text-slate-600">Model</div>
                <Select value={model} onValueChange={setModel}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(providerModels[provider] ?? MOCK_MODELS).map((m) => (
                      <SelectItem key={m} value={m}>
                        {m}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setRunOpen(false)}>
                Cancel
              </Button>
              <Button disabled={runMut.isPending} onClick={() => runMut.mutate()}>
                {runMut.isPending ? "Starting…" : "Run"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <RequireRole allow={["super_admin", "org_admin", "operator"]}>
      <RequireTenantScope>
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
          <Card>
            <CardHeader className="p-4">
              <CardTitle className="text-base">Suite</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 p-4 pt-0 text-sm">
              <div className="text-slate-600">Seeded test cases: {suitesQuery.data?.length ?? "—"}</div>
              <div className="max-h-72 overflow-auto rounded border border-slate-200 bg-white">
                <table className="w-full text-xs">
                  <thead className="sticky top-0 bg-white">
                    <tr className="border-b">
                      <th className="px-2 py-2 text-left font-medium text-slate-600">Name</th>
                      <th className="px-2 py-2 text-left font-medium text-slate-600">Category</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(suitesQuery.data ?? []).map((c) => (
                      <tr key={c.id} className="border-b">
                        <td className="px-2 py-2">
                          <Link className="hover:underline" href={`/evaluations/cases/${c.id}`}>
                            {c.name}
                          </Link>
                        </td>
                        <td className="px-2 py-2">{c.category}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          <Card className="lg:col-span-2">
            <CardHeader className="p-4">
              <CardTitle className="text-base">Runs</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-white">
                    <tr className="border-b">
                      <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Started</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Provider</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Model</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Status</th>
                      <th className="px-3 py-2 text-right text-xs font-medium text-slate-600">Summary</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(runsQuery.data ?? []).map((r) => (
                      <tr
                        key={r.id}
                        className="cursor-pointer border-b hover:bg-slate-50"
                        onClick={() => setSelectedRunId(r.id)}
                      >
                        <td className="px-3 py-2">{formatDateTime(r.started_at)}</td>
                        <td className="px-3 py-2">{r.provider}</td>
                        <td className="px-3 py-2">{r.model}</td>
                        <td className="px-3 py-2">{r.status}</td>
                        <td className="px-3 py-2 text-right">
                          {r.summary ? (
                            (() => {
                              const s: any = r.summary;
                              const passed = typeof s?.passed === "number" ? s.passed : null;
                              const total =
                                typeof s?.total === "number"
                                  ? s.total
                                  : passed != null && typeof s?.failed === "number"
                                    ? passed + s.failed
                                    : null;
                              if (passed == null || total == null || total <= 0 || passed < 0 || passed > total) return "—";
                              const failed = typeof s?.failed === "number" ? s.failed : total - passed;
                              const label = `${passed}/${total} passed`;
                              if (passed === total) {
                                return <Badge className="border-emerald-200 bg-emerald-50 text-emerald-800">{label}</Badge>;
                              }
                              if (passed > failed) {
                                return <Badge className="border-amber-200 bg-amber-50 text-amber-900">{label}</Badge>;
                              }
                              return <Badge className="border-red-200 bg-red-50 text-red-800">{label}</Badge>;
                            })()
                          ) : (
                            "—"
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </div>

        <Dialog open={!!selectedRunId} onOpenChange={(o) => (!o ? setSelectedRunId(null) : null)}>
          <DialogContent className="max-w-3xl">
            <DialogHeader>
              <DialogTitle>Run details</DialogTitle>
              <DialogDescription>Pass/fail results by test case.</DialogDescription>
            </DialogHeader>
            {runDetailQuery.isLoading ? (
              <div className="text-sm text-slate-600">Loading…</div>
            ) : runDetailQuery.isError ? (
              <div className="text-sm text-red-700">Failed to load run.</div>
            ) : runDetailQuery.data ? (
              <div className="space-y-2">
                <RunSummary current={runDetailQuery.data} previous={prevDetailQuery.data ?? null} />
                <div className="max-h-[420px] overflow-auto rounded border border-slate-200">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 bg-white">
                      <tr className="border-b">
                        <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Test</th>
                        <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Passed</th>
                        <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Flags</th>
                        <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Confidentiality Exposure</th>
                      </tr>
                    </thead>
                    <tbody>
                      {runDetailQuery.data.results.map((rr) => (
                        <tr key={rr.id} className={["border-b", rr.passed ? "" : "bg-red-50"].join(" ")}>
                          <td className="px-3 py-2">
                            <Link className="font-mono text-xs hover:underline" href={`/evaluations/cases/${rr.test_case_id}`}>
                              {rr.test_case_id.slice(0, 8)}
                            </Link>
                          </td>
                          <td className="px-3 py-2">{rr.passed ? "pass" : "fail"}</td>
                          <td className="px-3 py-2 text-xs">{(rr.observed_flags ?? []).join(", ")}</td>
                          <td className="px-3 py-2">
                            <ExposureBadge level={exposureLevelFromScore(rr.phi_score)} score={rr.phi_score} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null}
          </DialogContent>
        </Dialog>
      </RequireTenantScope>
      </RequireRole>
    </main>
  );
}

function RunSummary({
  current,
  previous,
}: {
  current: { run: { id: string; provider: string; model: string; status: string; started_at: string; finished_at: string | null }; results: Array<{ passed: boolean }> };
  previous: { run: { id: string; started_at: string }; results: Array<{ passed: boolean }> } | null;
}) {
  const total = current.results.length;
  const passed = current.results.filter((r) => r.passed).length;
  const failed = total - passed;
  const prevTotal = previous?.results.length ?? null;
  const prevPassed = previous ? previous.results.filter((r) => r.passed).length : null;
  const prevRate = prevTotal && prevPassed != null ? prevPassed / prevTotal : null;
  const rate = total ? passed / total : 0;
  const delta = prevRate != null ? rate - prevRate : null;

  return (
    <div className="rounded border border-slate-200 bg-white p-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <div className="font-medium">
            {current.run.provider} • {current.run.model} • {current.run.status}
          </div>
          <div className="font-mono text-xs text-slate-600">{current.run.id}</div>
        </div>
        <div className="text-right text-sm">
          <div className="tabular-nums">
            {passed}/{total} pass • {failed} fail
          </div>
          <div className="text-xs text-slate-600">
            Pass rate {(rate * 100).toFixed(1)}%{delta != null ? ` (${delta >= 0 ? "+" : ""}${(delta * 100).toFixed(1)}%)` : ""}
          </div>
        </div>
      </div>
      <div className="mt-2 text-xs text-slate-600">
        Started {formatDateTime(current.run.started_at)}
        {current.run.finished_at ? ` • Finished ${formatDateTime(current.run.finished_at)}` : ""}
        {previous ? ` • Previous ${formatDateTime(previous.run.started_at)} (${previous.run.id.slice(0, 8)})` : ""}
      </div>
    </div>
  );
}
