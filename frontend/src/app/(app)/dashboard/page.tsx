"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api-client";
import { useAppConfig } from "@/lib/app-config-context";
import { RequireTenantScope } from "@/components/layout/require-tenant";
import { formatUsd } from "@/lib/format";
import { isPlatformAdmin } from "@/lib/roles";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useActiveTenantId } from "@/lib/tenant";
import { Button } from "@/components/ui/button";

export default function DashboardPage() {
  const appConfig = useAppConfig();
  const meQuery = useQuery({ queryKey: ["me"], queryFn: () => api.auth.me() });
  const tenantId = useActiveTenantId();
  const [range, setRange] = React.useState<"24h" | "7d" | "30d">("7d");
  const rulesLabel = appConfig.terminology.rules_label;
  const primaryEntityLabel = appConfig.terminology.workflow.primary_entity_label;
  const organizationLabel = appConfig.terminology.organization_context;

  React.useEffect(() => {
    document.title = `Dashboard — ${appConfig.product.name}`;
  }, [appConfig.product.name]);

  React.useEffect(() => {
    try {
      const saved = window.localStorage.getItem("sentinel_dashboard_range");
      if (saved === "24h" || saved === "7d" || saved === "30d") setRange(saved);
    } catch {
      // ignore
    }
  }, []);

  React.useEffect(() => {
    try {
      window.localStorage.setItem("sentinel_dashboard_range", range);
    } catch {
      // ignore
    }
  }, [range]);

  const metricsQuery = useQuery({
    queryKey: ["metrics", "overview", range],
    queryFn: () => api.metrics.overview(range),
    enabled: !!meQuery.data && (!isPlatformAdmin(meQuery.data.role) || !!tenantId),
  });
  const costSummaryQuery = useQuery({
    queryKey: ["metrics", "costSummary"],
    queryFn: () => api.metrics.costSummary(),
    enabled: !!meQuery.data && (!isPlatformAdmin(meQuery.data.role) || !!tenantId),
    staleTime: 60 * 1000,
  });
  const apiKeysQuery = useQuery({
    queryKey: ["apiKeys"],
    queryFn: () => api.apiKeys.list(),
    enabled: !!meQuery.data && (!isPlatformAdmin(meQuery.data.role) || !!tenantId),
  });
  const policyQuery = useQuery({
    queryKey: ["policy", "current"],
    queryFn: () => api.policy.getCurrent(),
    enabled: !!meQuery.data && (!isPlatformAdmin(meQuery.data.role) || !!tenantId),
  });
  const settingsQuery = useQuery({
    queryKey: ["settings", "current"],
    queryFn: () => api.settings.getCurrent(),
    enabled: !!meQuery.data && (!isPlatformAdmin(meQuery.data.role) || !!tenantId),
  });
  const riskSummaryQuery = useQuery({
    queryKey: ["metrics", "riskSummary", range],
    queryFn: () => api.metrics.riskSummary(range),
    enabled: !!meQuery.data && (!isPlatformAdmin(meQuery.data.role) || !!tenantId),
  });

  const apiKeyNameById = React.useMemo(() => {
    const map = new Map<string, string>();
    for (const k of apiKeysQuery.data ?? []) map.set(k.id, k.name);
    return map;
  }, [apiKeysQuery.data]);

  const governance = React.useMemo(() => {
    const policy = policyQuery.data?.policy_json ?? null;
    const settings = settingsQuery.data?.settings_json ?? null;
    if (!policy) return null;

    const injectionEnabled = Array.isArray((policy as any).block_prompt_patterns) && (policy as any).block_prompt_patterns.length > 0;
    const confidentialityEnabled = ((policy as any).phi?.enabled ?? true) === true;
    const allowedModels = (policy as any).allowed_models;
    const modelRestrictions = Array.isArray(allowedModels) && allowedModels.length > 0;
    const storeMode = (settings as any)?.storage_mode ?? "OFF";

    return {
      rulesStatus: "Active",
      injectionEnabled,
      confidentialityEnabled,
      modelRestrictions,
      storeMode,
      updatedAt: policyQuery.data?.updated_at ?? null,
    };
  }, [policyQuery.data, settingsQuery.data]);

  return (
    <main className="space-y-4" data-testid="dashboard">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-xl font-semibold">Dashboard</h1>
        <div className="w-full sm:w-[200px]">
          <Select value={range} onValueChange={(v) => setRange(v as any)}>
            <SelectTrigger aria-label="Time range">
              <SelectValue placeholder="Range" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="24h">Last 24 hours</SelectItem>
              <SelectItem value="7d">Last 7 days</SelectItem>
              <SelectItem value="30d">Last 30 days</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
      <RequireTenantScope>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-6">
          <MetricCard title="Total Requests" value={metricsQuery.data?.cards.total_requests} />
          <MetricCard
            title="Policy Blocks"
            value={metricsQuery.data?.cards.policy_blocks}
            variant={metricsQuery.data && metricsQuery.data.cards.policy_blocks > 0 ? "danger" : "default"}
          />
          <MetricCard
            title="Confidentiality Exposure Flagged"
            value={metricsQuery.data?.cards.phi_flagged}
            variant={metricsQuery.data && metricsQuery.data.cards.phi_flagged > 0 ? "danger" : "default"}
          />
          <MetricCard
            title="Avg Exposure Score"
            value={metricsQuery.data ? metricsQuery.data.cards.avg_phi_score.toFixed(1) : undefined}
            subtitle={metricsQuery.data ? "out of 100 — lower is safer" : undefined}
            variant={
              metricsQuery.data
                ? metricsQuery.data.cards.avg_phi_score >= 70
                  ? "danger"
                  : metricsQuery.data.cards.avg_phi_score >= 40
                    ? "warning"
                    : "default"
                : "default"
            }
          />
          <MetricCard title="Est. Cost" value={metricsQuery.data ? formatUsd(metricsQuery.data.cards.estimated_cost_usd) : undefined} />
          <MetricCard title="Cost This Month" value={costSummaryQuery.data ? formatUsd(costSummaryQuery.data.this_month.total_usd) : undefined} />
        </div>

        {metricsQuery.data && metricsQuery.data.cards.total_requests === 0 ? (
          <Card>
            <CardHeader>
              <CardTitle>Welcome to {appConfig.product.name}</CardTitle>
              <CardDescription>
                No AI activity has been routed through {appConfig.product.name} yet. Connect your first AI tool to start seeing
                governance data, audit logs, and risk signals here.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              <Button onClick={() => (window.location.href = "/api-keys")}>Create API Key</Button>
              <Button variant="outline" onClick={() => (window.location.href = "/help")}>
                View Setup Guide
              </Button>
            </CardContent>
          </Card>
        ) : (
          <>
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>AI Governance Status</CardTitle>
                  <CardDescription>High-level controls currently enforced for this {organizationLabel}.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  {governance ? (
                    <>
                      <StatusRow label={rulesLabel} value={governance.rulesStatus} />
                      <StatusRow label="Injection protection" value={governance.injectionEnabled ? "Enabled" : "Disabled"} />
                      <StatusRow label="Confidentiality monitoring" value={governance.confidentialityEnabled ? "Enabled" : "Disabled"} />
                      <StatusRow label="Model restrictions" value={governance.modelRestrictions ? "Enforced" : "Not enforced"} />
                      <StatusRow label="Content storage" value={String(governance.storeMode)} />
                      <div className="pt-2">
                        <Button onClick={() => (window.location.href = "/policies")}>Go to {rulesLabel}</Button>
                      </div>
                    </>
                  ) : (
                    <div className="text-sm text-slate-600">Loading…</div>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>AI Risk Summary (Last 7 Days)</CardTitle>
                  <CardDescription>
                    Signals to support quick review and defensibility (
                    {range === "24h" ? "last 24 hours" : range === "7d" ? "last 7 days" : "last 30 days"}).
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-sm">
                  {riskSummaryQuery.isLoading ? (
                    <div className="text-sm text-slate-600">Loading…</div>
                  ) : riskSummaryQuery.isError ? (
                    <div className="text-sm text-red-700">Failed to load summary.</div>
                  ) : riskSummaryQuery.data ? (
                    <>
                      <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
                        <MiniMetric title="Total AI requests" value={riskSummaryQuery.data.total_ai_requests} />
                        <MiniMetric title="Injection flagged" value={riskSummaryQuery.data.injection_attempts_flagged} />
                        <MiniMetric title="Blocked requests" value={riskSummaryQuery.data.blocked_requests} />
                        <MiniMetric title="High exposure" value={riskSummaryQuery.data.high_confidentiality_exposure} />
                      </div>
                      <div>
                        <div className="text-xs font-medium text-slate-600">Top {primaryEntityLabel.toLowerCase()}s</div>
                        <div className="mt-1 space-y-1">
                          {(riskSummaryQuery.data.top_matters ?? []).length ? (
                            riskSummaryQuery.data.top_matters.map((m) => (
                              <div key={m.matter_id ?? "unknown"} className="flex items-center justify-between gap-2">
                                <div className="min-w-0 truncate font-mono text-xs">{m.matter_id ?? "—"}</div>
                                <div className="tabular-nums text-slate-700">{m.count}</div>
                              </div>
                            ))
                          ) : (
                            <div className="text-sm text-slate-600">No {primaryEntityLabel.toLowerCase()}-tagged activity yet.</div>
                          )}
                        </div>
                      </div>
                    </>
                  ) : null}
                </CardContent>
              </Card>
            </div>

            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>Requests Over Time</CardTitle>
                  <CardDescription>LLM request volume ({range})</CardDescription>
                </CardHeader>
                <CardContent className="h-64">
                  <ChartLine data={metricsQuery.data?.requests_over_time ?? []} />
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>Cost Over Time</CardTitle>
                  <CardDescription>Estimated USD ({range})</CardDescription>
                </CardHeader>
                <CardContent className="h-64">
                  <ChartLine data={metricsQuery.data?.cost_over_time ?? []} />
                </CardContent>
              </Card>
            </div>

            <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
              <Card className="lg:col-span-1">
                <CardHeader>
                  <CardTitle>Top API Keys</CardTitle>
                  <CardDescription>By request volume ({range})</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {(metricsQuery.data?.top_api_keys ?? []).slice(0, 8).map((row) => {
                      const name = row.api_key_id ? apiKeyNameById.get(row.api_key_id) : null;
                      return (
                        <div key={row.api_key_id ?? "unknown"} className="flex items-center justify-between gap-2 text-sm">
                          <div className="min-w-0">
                            <div className="truncate font-medium">{name ?? (row.api_key_id ? `Key ${row.api_key_id.slice(0, 8)}` : "Unknown key")}</div>
                            {row.api_key_id ? <div className="font-mono text-xs text-slate-600">{row.api_key_id.slice(0, 12)}</div> : null}
                          </div>
                          <div className="tabular-nums text-slate-700">{row.count}</div>
                        </div>
                      );
                    })}
                    {metricsQuery.data && metricsQuery.data.top_api_keys.length === 0 ? (
                      <div className="text-sm text-slate-600">
                        No AI activity in range yet. Create an API key and route a tool through {appConfig.product.name}.
                      </div>
                    ) : null}
                  </div>
                </CardContent>
              </Card>

              <Card className="lg:col-span-1">
                <CardHeader>
                  <CardTitle>Risk Flags</CardTitle>
                  <CardDescription>Counts by flag ({range})</CardDescription>
                </CardHeader>
                <CardContent className="h-64">
                  <ChartBars
                    data={Object.entries(metricsQuery.data?.flags_counts ?? {}).map(([k, v]) => ({
                      name:
                        /^[A-Z0-9_]+$/.test(k)
                          ? k
                              .toLowerCase()
                              .split("_")
                              .filter(Boolean)
                              .map((w) => w.slice(0, 1).toUpperCase() + w.slice(1))
                              .join(" ")
                          : k,
                      value: v,
                    }))}
                  />
                </CardContent>
              </Card>

              <Card className="lg:col-span-1">
                <CardHeader>
                  <CardTitle>Severity</CardTitle>
                  <CardDescription>Counts by severity ({range})</CardDescription>
                </CardHeader>
                <CardContent className="h-64">
                  <ChartPie
                    data={Object.entries(metricsQuery.data?.severity_counts ?? {}).map(([k, v]) => ({
                      name: k === "low" ? "Low" : k === "med" ? "Medium" : k === "high" ? "High" : k,
                      value: v,
                    }))}
                  />
                </CardContent>
              </Card>
            </div>
          </>
        )}
      </RequireTenantScope>
    </main>
  );
}

function MetricCard({
  title,
  value,
  subtitle,
  variant = "default",
}: {
  title: string;
  value: string | number | undefined;
  subtitle?: string;
  variant?: "default" | "warning" | "danger";
}) {
  const tint = variant === "warning" ? "border-amber-200 bg-amber-50" : variant === "danger" ? "border-red-200 bg-red-50" : "";
  return (
    <Card className={tint}>
      <CardHeader className="p-4">
        <CardDescription>{title}</CardDescription>
        <CardTitle className="text-2xl">{value ?? "—"}</CardTitle>
        {subtitle ? <CardDescription className="text-xs text-slate-500">{subtitle}</CardDescription> : null}
      </CardHeader>
    </Card>
  );
}

function StatusRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <div className="text-slate-600">{label}</div>
      <div className="font-medium text-slate-900">{value}</div>
    </div>
  );
}

function MiniMetric({ title, value }: { title: string; value: string | number }) {
  return (
    <div className="rounded border border-slate-200 bg-white p-3">
      <div className="text-xs text-slate-600">{title}</div>
      <div className="mt-1 text-lg font-semibold tabular-nums">{value}</div>
    </div>
  );
}

function ChartLine({ data }: { data: Array<{ t: string; value: number }> }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data}>
        <XAxis dataKey="t" tickFormatter={(v) => String(v).slice(5, 10)} />
        <YAxis />
        <Tooltip />
        <Line type="monotone" dataKey="value" stroke="#0f172a" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

function ChartBars({ data }: { data: Array<{ name: string; value: number }> }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data}>
        <XAxis dataKey="name" hide />
        <YAxis />
        <Tooltip />
        <Bar dataKey="value" fill="#0f172a" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function ChartPie({ data }: { data: Array<{ name: string; value: number }> }) {
  const colors = ["#0f172a", "#334155", "#64748b", "#94a3b8", "#cbd5e1"];
  const filtered = data.filter((d) => d.value > 0);
  if (filtered.length === 0) return <div className="text-sm text-slate-600">No data.</div>;
  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Tooltip />
        <Pie data={filtered} dataKey="value" nameKey="name" innerRadius={45} outerRadius={70} paddingAngle={2}>
          {filtered.map((_, idx) => (
            <Cell key={idx} fill={colors[idx % colors.length]} />
          ))}
        </Pie>
      </PieChart>
    </ResponsiveContainer>
  );
}
