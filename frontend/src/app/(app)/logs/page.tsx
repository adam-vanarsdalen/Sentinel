"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ColumnDef,
  SortingState,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  VisibilityState,
} from "@tanstack/react-table";

import { RequireTenantScope } from "@/components/layout/require-tenant";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { api } from "@/lib/api-client";
import { useAppConfig } from "@/lib/app-config-context";
import { formatDateTime, formatUsd, shortId } from "@/lib/format";
import { useToast } from "@/components/toaster";
import { hasAnyRole, isPlatformAdmin } from "@/lib/roles";
import { getActiveTenantId, useActiveTenantId } from "@/lib/tenant";
import type { AuditEvent } from "@/lib/schemas";
import { ExposureBadge } from "@/components/exposure-badge";
import { InfoTip } from "@/components/info-tip";

type LogFilters = {
  start?: string; // datetime-local
  end?: string; // datetime-local
  action_type?: string;
  outcome?: string;
  severity?: string;
  flag?: string;
  api_key_id?: string;
  user_id?: string;
  matter_query?: string;
  practice_group?: string;
};

type SavedView = { id: string; name: string; filters: LogFilters };

const ANY = "__any__";

function loadViews(): SavedView[] {
  try {
    const raw = window.localStorage.getItem("sentinel_logs_views");
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as SavedView[]) : [];
  } catch {
    return [];
  }
}

function saveViews(views: SavedView[]) {
  try {
    window.localStorage.setItem("sentinel_logs_views", JSON.stringify(views));
  } catch {
    // ignore
  }
}

function toIso(dtLocal: string | undefined): string | undefined {
  if (!dtLocal) return undefined;
  const d = new Date(dtLocal);
  if (Number.isNaN(d.getTime())) return undefined;
  return d.toISOString();
}

export default function LogsPage() {
  const appConfig = useAppConfig();
  const toast = useToast();
  const tenantId = useActiveTenantId();
  const meQuery = useQuery({ queryKey: ["me"], queryFn: () => api.auth.me() });
  const role = meQuery.data?.role;
  const tenantReady = !!meQuery.data && (!isPlatformAdmin(meQuery.data.role) || !!tenantId);
  const canExport = hasAnyRole(role, ["org_admin", "compliance_admin", "auditor", "super_admin"]);
  const activityLogLabel = appConfig.terminology.activity_log_label;
  const reportLabel = appConfig.terminology.report_label;
  const primaryEntityLabel = appConfig.terminology.workflow.primary_entity_label;
  const secondaryEntityLabel = appConfig.terminology.workflow.secondary_entity_label;
  const externalPartyLabel = appConfig.terminology.workflow.external_party_label;
  const productName = appConfig.product.name;

  React.useEffect(() => {
    document.title = `${activityLogLabel} — ${productName}`;
  }, [activityLogLabel, productName]);

  const [filters, setFilters] = React.useState<LogFilters>({});
  const [page, setPage] = React.useState(0);
  const [sorting, setSorting] = React.useState<SortingState>([{ id: "timestamp", desc: true }]);
  const [columnVisibility, setColumnVisibility] = React.useState<VisibilityState>({});
  const [views, setViews] = React.useState<SavedView[]>([]);
  const [saveViewName, setSaveViewName] = React.useState("");
  const [saveOpen, setSaveOpen] = React.useState(false);
  const [reportOpen, setReportOpen] = React.useState(false);
  const [reportStart, setReportStart] = React.useState<string>("");
  const [reportEnd, setReportEnd] = React.useState<string>("");
  const [reportMatter, setReportMatter] = React.useState<string>("");
  const [reportPracticeGroup, setReportPracticeGroup] = React.useState<string>("");
  const [reportIncludeSummary, setReportIncludeSummary] = React.useState(true);
  const [reportFormat, setReportFormat] = React.useState<"html" | "pdf" | "csv" | "json">("pdf");

  const limit = 50;
  const offset = page * limit;

  React.useEffect(() => {
    setViews(loadViews());
  }, []);

  React.useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      const userId = params.get("user_id");
      if (userId) setFilters((f) => ({ ...f, user_id: userId }));
      const matter = params.get("matter");
      if (matter) setFilters((f) => ({ ...f, matter_query: matter }));
    } catch {
      // ignore
    }
  }, []);

  React.useEffect(() => {
    setPage(0);
  }, [
    filters.start,
    filters.end,
    filters.action_type,
    filters.outcome,
    filters.severity,
    filters.flag,
    filters.api_key_id,
    filters.user_id,
    filters.practice_group,
    filters.matter_query,
  ]);

  const searchQuery = useQuery({
    queryKey: ["audit", "search", { ...filters, offset, limit }],
    queryFn: () =>
      api.audit.search({
        start: toIso(filters.start),
        end: toIso(filters.end),
        action_type: filters.action_type || undefined,
        outcome: filters.outcome || undefined,
        severity: filters.severity || undefined,
      api_key_id: filters.api_key_id || undefined,
      user_id: filters.user_id || undefined,
      practice_group: filters.practice_group || undefined,
      matter_query: filters.matter_query || undefined,
      flag: filters.flag || undefined,
      limit,
      offset,
    }),
    enabled: tenantReady,
  });

  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const detailQuery = useQuery({
    queryKey: ["audit", "event", selectedId],
    queryFn: () => api.audit.get(selectedId!),
    enabled: !!selectedId && tenantReady,
  });

  const apiKeysQuery = useQuery({
    queryKey: ["apiKeys"],
    queryFn: () => api.apiKeys.list(),
    enabled: tenantReady && hasAnyRole(role, ["org_admin", "operator", "super_admin"]),
  });
  const apiKeyNameById = React.useMemo(() => {
    const map = new Map<string, string>();
    for (const k of apiKeysQuery.data ?? []) map.set(k.id, k.name);
    return map;
  }, [apiKeysQuery.data]);

  const usersQuery = useQuery({ queryKey: ["users"], queryFn: () => api.users.list(), enabled: tenantReady && hasAnyRole(role, ["org_admin", "super_admin"]) });
  const userEmailById = React.useMemo(() => {
    const map = new Map<string, string>();
    for (const u of usersQuery.data ?? []) map.set(u.id, u.email);
    return map;
  }, [usersQuery.data]);

  const relatedQuery = useQuery({
    queryKey: ["audit", "related", selectedId],
    queryFn: async () => {
      const ev = await api.audit.get(selectedId!);
      if (!ev.api_key_id) return [];
      const t = new Date(ev.timestamp).getTime();
      const start = new Date(t - 5 * 60 * 1000).toISOString();
      const end = new Date(t + 5 * 60 * 1000).toISOString();
      const res = await api.audit.search({ api_key_id: ev.api_key_id, start, end, limit: 10, offset: 0 });
      return res.items.filter((x) => x.id !== ev.id);
    },
    enabled: !!selectedId && tenantReady,
  });

  const exportCsvHref = `/api/proxy/admin/audit-events/export.csv?${new URLSearchParams({
    ...(getActiveTenantId() ? { tenant_id: getActiveTenantId()! } : {}),
    ...(toIso(filters.start) ? { start: toIso(filters.start)! } : {}),
    ...(toIso(filters.end) ? { end: toIso(filters.end)! } : {}),
    ...(filters.action_type ? { action_type: filters.action_type } : {}),
    ...(filters.outcome ? { outcome: filters.outcome } : {}),
    ...(filters.severity ? { severity: filters.severity } : {}),
    ...(filters.api_key_id ? { api_key_id: filters.api_key_id } : {}),
    ...(filters.user_id ? { user_id: filters.user_id } : {}),
    ...(filters.practice_group ? { practice_group: filters.practice_group } : {}),
    ...(filters.matter_query ? { matter_query: filters.matter_query } : {}),
    ...(filters.flag ? { flag: filters.flag } : {}),
  }).toString()}`;

  const exportJsonHref = `/api/proxy/admin/audit-events/export.json?${new URLSearchParams({
    format: "sentinel",
    ...(getActiveTenantId() ? { tenant_id: getActiveTenantId()! } : {}),
    ...(toIso(filters.start) ? { start: toIso(filters.start)! } : {}),
    ...(toIso(filters.end) ? { end: toIso(filters.end)! } : {}),
    ...(filters.action_type ? { action_type: filters.action_type } : {}),
    ...(filters.outcome ? { outcome: filters.outcome } : {}),
    ...(filters.severity ? { severity: filters.severity } : {}),
    ...(filters.api_key_id ? { api_key_id: filters.api_key_id } : {}),
    ...(filters.user_id ? { user_id: filters.user_id } : {}),
    ...(filters.practice_group ? { practice_group: filters.practice_group } : {}),
    ...(filters.matter_query ? { matter_query: filters.matter_query } : {}),
    ...(filters.flag ? { flag: filters.flag } : {}),
  }).toString()}`;

  const exportPdfHref = `/api/proxy/admin/audit-events/export.pdf?${new URLSearchParams({
    ...(getActiveTenantId() ? { tenant_id: getActiveTenantId()! } : {}),
    ...(toIso(filters.start) ? { start: toIso(filters.start)! } : {}),
    ...(toIso(filters.end) ? { end: toIso(filters.end)! } : {}),
    ...(filters.action_type ? { action_type: filters.action_type } : {}),
    ...(filters.outcome ? { outcome: filters.outcome } : {}),
    ...(filters.severity ? { severity: filters.severity } : {}),
    ...(filters.api_key_id ? { api_key_id: filters.api_key_id } : {}),
    ...(filters.user_id ? { user_id: filters.user_id } : {}),
    ...(filters.practice_group ? { practice_group: filters.practice_group } : {}),
    ...(filters.matter_query ? { matter_query: filters.matter_query } : {}),
    ...(filters.flag ? { flag: filters.flag } : {}),
  }).toString()}`;

  function buildReportHref() {
    const qs = new URLSearchParams({
      ...(getActiveTenantId() ? { tenant_id: getActiveTenantId()! } : {}),
      ...(toIso(reportStart) ? { start: toIso(reportStart)! } : {}),
      ...(toIso(reportEnd) ? { end: toIso(reportEnd)! } : {}),
      ...(reportMatter.trim() ? { matter_query: reportMatter.trim() } : {}),
      ...(reportPracticeGroup.trim() ? { practice_group: reportPracticeGroup.trim() } : {}),
      include_summary: reportIncludeSummary ? "true" : "false",
    });
    if (reportFormat === "html") return `/api/proxy/admin/audit-events/report.html?${qs.toString()}`;
    if (reportFormat === "pdf") return `/api/proxy/admin/audit-events/report.pdf?${qs.toString()}`;
    if (reportFormat === "csv") return `/api/proxy/admin/audit-events/export.csv?${qs.toString()}`;
    return `/api/proxy/admin/audit-events/export.json?${new URLSearchParams({ format: "sentinel", ...Object.fromEntries(qs) }).toString()}`;
  }

  async function downloadHref(href: string, filename: string) {
    try {
      toast.push({ title: "Export started", description: "Preparing download…" });
      const res = await fetch(href, { method: "GET" });
      if (!res.ok) throw new Error(`Export failed (${res.status})`);
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.push({ title: "Export ready", description: filename });
    } catch (e: any) {
      toast.push({ title: "Export failed", description: "Unable to generate export." });
    }
  }

  function downloadBlob(blob: Blob, filename: string) {
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  }

  function flagHelp(flag: string): string | null {
    if (flag === "PROMPT_INJECTION_SUSPECTED") {
      return "A document may contain instructions intended to manipulate the AI’s behavior.";
    }
    if (flag === "SYSTEM_PROMPT_EXPOSURE") {
      return "The response may be exposing hidden system/developer instructions.";
    }
    return null;
  }

  const columns = React.useMemo<ColumnDef<AuditEvent>[]>(
    () => [
      {
        id: "timestamp",
        accessorKey: "timestamp",
        header: "Time",
        cell: ({ row }) => formatDateTime(row.original.timestamp),
      },
      {
        id: "action_type",
        accessorKey: "action_type",
        header: "Action",
        cell: ({ row }) => row.original.action_type,
      },
      {
        id: "matter_id",
        accessorKey: "matter_id",
        header: primaryEntityLabel,
        cell: ({ row }) => {
          const mid = row.original.matter_id;
          if (!mid) return <span className="text-slate-600">—</span>;
          return (
            <div className="min-w-0">
              <div className="truncate font-mono text-xs">{mid}</div>
              {row.original.practice_group ? <div className="text-[11px] text-slate-600">{row.original.practice_group}</div> : null}
            </div>
          );
        },
      },
      {
        id: "outcome",
        accessorKey: "outcome",
        header: "Outcome",
        cell: ({ row }) => <Badge variant="secondary">{row.original.outcome}</Badge>,
      },
      {
        id: "api_key_id",
        accessorKey: "api_key_id",
        header: "App / Key",
        cell: ({ row }) => {
          const id = row.original.api_key_id ?? null;
          if (!id) return <span className="text-slate-600">—</span>;
          const name = row.original.api_key_name ?? apiKeyNameById.get(id);
          return (
            <div className="min-w-0">
              <div className="truncate">{name ?? `Key ${id.slice(0, 8)}`}</div>
              <div className="font-mono text-[11px] text-slate-600">{id.slice(0, 12)}</div>
            </div>
          );
        },
      },
      {
        id: "user_id",
        accessorKey: "user_id",
        header: "User",
        cell: ({ row }) => {
          const id = row.original.user_id ?? null;
          if (!id) return <span className="text-slate-600">—</span>;
          const email = row.original.user_email ?? userEmailById.get(id);
          return (
            <div className="min-w-0">
              <div className="truncate">{email ?? `User ${id.slice(0, 8)}`}</div>
              {row.original.user_role ? <div className="text-[11px] text-slate-600">{row.original.user_role}</div> : null}
            </div>
          );
        },
      },
      {
        id: "severity",
        accessorKey: "severity",
        header: "Severity",
        cell: ({ row }) => row.original.severity ?? "—",
      },
      {
        id: "flags",
        accessorKey: "risk_flags",
        header: "Flags",
        cell: ({ row }) => (
          <div className="flex flex-wrap gap-1">
            {(row.original.risk_flags ?? []).slice(0, 3).map((f) => (
              <Badge key={f} title={flagHelp(f) ?? undefined}>
                {f}
              </Badge>
            ))}
            {(row.original.risk_flags ?? []).length > 3 ? (
              <Badge variant="secondary">+{(row.original.risk_flags ?? []).length - 3}</Badge>
            ) : null}
          </div>
        ),
      },
      {
        id: "phi_score",
        accessorKey: "phi_score",
        header: "Exposure Level",
        cell: ({ row }) => <ExposureBadge level={row.original.confidentiality_exposure_level} score={row.original.phi_score} />,
      },
      {
        id: "cost_usd",
        accessorKey: "cost_usd",
        header: "Cost",
        cell: ({ row }) => (row.original.cost_usd != null ? formatUsd(row.original.cost_usd) : "—"),
      },
      {
        id: "id",
        accessorKey: "id",
        header: "Request",
        cell: ({ row }) => (
          <span className="font-mono text-xs">{shortId(row.original.request_id ?? row.original.id)}</span>
        ),
      },
    ],
    [apiKeyNameById, primaryEntityLabel, userEmailById],
  );

  const tableData = React.useMemo(() => searchQuery.data?.items ?? [], [searchQuery.data?.items]);

  const table = useReactTable({
    data: tableData,
    columns,
    state: { sorting, columnVisibility },
    onSortingChange: setSorting,
    onColumnVisibilityChange: setColumnVisibility,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    manualPagination: true,
    enableSorting: true,
  });

  return (
    <main className="space-y-4" data-testid="logs">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">{activityLogLabel}</h1>
        <div className="flex items-center gap-2">
          {canExport && tenantReady ? (
            <>
              <Button
                onClick={() => {
                  setReportStart(filters.start ?? "");
                  setReportEnd(filters.end ?? "");
                  setReportMatter(filters.matter_query ?? "");
                  setReportPracticeGroup(filters.practice_group ?? "");
                  setReportIncludeSummary(true);
                  setReportFormat("pdf");
                  setReportOpen(true);
                }}
                title="Download an audit trail for internal review or stakeholder defensibility."
              >
                Generate {reportLabel}
              </Button>
              <Button variant="outline" onClick={() => downloadHref(exportCsvHref, "sentinel-audit.csv")}>
                Export CSV
              </Button>
              <Button variant="outline" onClick={() => downloadHref(exportJsonHref, "sentinel-audit.json")}>
                Export JSON
              </Button>
              <Button variant="outline" onClick={() => downloadHref(exportPdfHref, "sentinel-audit.pdf")}>
                Export PDF
              </Button>
            </>
          ) : null}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline">Columns</Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel>Show/Hide</DropdownMenuLabel>
              <DropdownMenuSeparator />
              {table.getAllLeafColumns().map((col) => (
                <DropdownMenuCheckboxItem
                  key={col.id}
                  checked={col.getIsVisible()}
                  onCheckedChange={(v) => col.toggleVisibility(!!v)}
                >
                  {col.columnDef.header as string}
                </DropdownMenuCheckboxItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {canExport && tenantReady ? (
        <Dialog open={reportOpen} onOpenChange={setReportOpen}>
          <DialogContent className="max-w-xl">
            <DialogHeader>
              <DialogTitle>Generate {reportLabel}</DialogTitle>
              <DialogDescription>Build a polished {productName} report or download the raw audit export for the same scope.</DialogDescription>
            </DialogHeader>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <div className="space-y-1">
                <div className="text-xs text-slate-600">Start</div>
                <Input type="datetime-local" value={reportStart} onChange={(e) => setReportStart(e.target.value)} />
              </div>
              <div className="space-y-1">
                <div className="text-xs text-slate-600">End</div>
                <Input type="datetime-local" value={reportEnd} onChange={(e) => setReportEnd(e.target.value)} />
              </div>
              <div className="space-y-1 md:col-span-2">
                <div className="text-xs text-slate-600">{primaryEntityLabel} (optional)</div>
                <Input value={reportMatter} onChange={(e) => setReportMatter(e.target.value)} placeholder="e.g. MAT-2026-0142" />
              </div>
              <div className="space-y-1 md:col-span-2">
                <div className="text-xs text-slate-600">{secondaryEntityLabel} (optional)</div>
                <Input value={reportPracticeGroup} onChange={(e) => setReportPracticeGroup(e.target.value)} placeholder="e.g. Corporate" />
              </div>
              <div className="space-y-1 md:col-span-2">
                <div className="text-xs text-slate-600">Format</div>
                <Select value={reportFormat} onValueChange={(v) => setReportFormat(v as any)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="html">HTML report</SelectItem>
                    <SelectItem value="pdf">PDF report</SelectItem>
                    <SelectItem value="csv">CSV</SelectItem>
                    <SelectItem value="json">JSON</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1 md:col-span-2">
                <label className="flex items-center gap-2 rounded border border-slate-200 bg-slate-50 px-3 py-3 text-sm">
                  <input
                    type="checkbox"
                    checked={reportIncludeSummary}
                    onChange={(e) => setReportIncludeSummary(e.target.checked)}
                    disabled={reportFormat === "csv" || reportFormat === "json"}
                  />
                  <span>Include executive summary sections (metrics, flagged events, blocked requests, top {primaryEntityLabel.toLowerCase()}s, and top {secondaryEntityLabel.toLowerCase()}s)</span>
                </label>
                <div className="text-xs text-slate-500">
                  HTML and PDF use the formatted report layout. CSV and JSON remain raw exports for spreadsheet or downstream processing.
                </div>
              </div>
            </div>
            <div className="flex items-center justify-end gap-2">
              <Button variant="outline" onClick={() => setReportOpen(false)}>
                Cancel
              </Button>
              <Button
                onClick={async () => {
                  const href = buildReportHref();
                  const filename =
                    reportFormat === "html"
                      ? "sentinel-audit-report.html"
                      : reportFormat === "pdf"
                        ? "sentinel-audit-report.pdf"
                        : reportFormat === "csv"
                          ? "sentinel-audit-report.csv"
                          : "sentinel-audit-report.json";
                  setReportOpen(false);
                  await downloadHref(href, filename);
                }}
              >
                Generate
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      ) : null}

      <RequireTenantScope>
        <Card>
          <CardHeader className="p-4">
            <CardTitle className="text-base">Filters</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-3 p-4 pt-0 md:grid-cols-6">
            <div className="space-y-1 md:col-span-2">
              <div className="text-xs text-slate-600">Start</div>
              <Input
                type="datetime-local"
                value={filters.start ?? ""}
                onChange={(e) => setFilters((f) => ({ ...f, start: e.target.value || undefined }))}
              />
            </div>
            <div className="space-y-1 md:col-span-2">
              <div className="text-xs text-slate-600">End</div>
              <Input
                type="datetime-local"
                value={filters.end ?? ""}
                onChange={(e) => setFilters((f) => ({ ...f, end: e.target.value || undefined }))}
              />
            </div>

            <div className="space-y-1">
              <div className="text-xs text-slate-600">Action</div>
              <Select
                value={filters.action_type ?? ANY}
                onValueChange={(v) => setFilters((f) => ({ ...f, action_type: v === ANY ? undefined : v }))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Any" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ANY}>Any</SelectItem>
                  <SelectItem value="LLM_REQUEST">LLM_REQUEST</SelectItem>
                  <SelectItem value="POLICY_BLOCK">POLICY_BLOCK</SelectItem>
                    <SelectItem value="PHI_FLAG">Confidential data</SelectItem>
                  <SelectItem value="ADMIN_CHANGE">ADMIN_CHANGE</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1">
              <div className="text-xs text-slate-600">Outcome</div>
              <Select value={filters.outcome ?? ANY} onValueChange={(v) => setFilters((f) => ({ ...f, outcome: v === ANY ? undefined : v }))}>
                <SelectTrigger>
                  <SelectValue placeholder="Any" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ANY}>Any</SelectItem>
                  <SelectItem value="success">success</SelectItem>
                  <SelectItem value="fail">fail</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1">
              <div className="text-xs text-slate-600">Severity</div>
              <Select value={filters.severity ?? ANY} onValueChange={(v) => setFilters((f) => ({ ...f, severity: v === ANY ? undefined : v }))}>
                <SelectTrigger>
                  <SelectValue placeholder="Any" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ANY}>Any</SelectItem>
                  <SelectItem value="low">low</SelectItem>
                  <SelectItem value="med">med</SelectItem>
                  <SelectItem value="high">high</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1">
              <div className="text-xs text-slate-600">API Key</div>
              <Select
                value={filters.api_key_id ?? ANY}
                onValueChange={(v) => setFilters((f) => ({ ...f, api_key_id: v === ANY ? undefined : v }))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Any" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ANY}>Any</SelectItem>
                  {(apiKeysQuery.data ?? []).map((k) => (
                    <SelectItem key={k.id} value={k.id}>
                      {k.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <div className="text-xs text-slate-600">User</div>
              <Select
                value={filters.user_id ?? ANY}
                onValueChange={(v) => setFilters((f) => ({ ...f, user_id: v === ANY ? undefined : v }))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Any" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ANY}>Any</SelectItem>
                  {(usersQuery.data ?? []).map((u) => (
                    <SelectItem key={u.id} value={u.id}>
                      {u.email} {u.is_active ? "" : "(inactive)"}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1 md:col-span-2">
              <div className="text-xs text-slate-600">{primaryEntityLabel}</div>
              <Input
                value={filters.matter_query ?? ""}
                onChange={(e) => setFilters((f) => ({ ...f, matter_query: e.target.value || undefined }))}
                placeholder="e.g. MAT-2026-0142"
              />
            </div>
            <div className="space-y-1 md:col-span-2">
              <div className="text-xs text-slate-600">
                {secondaryEntityLabel}
                <InfoTip text={`Optional tag used by teams to group ${primaryEntityLabel.toLowerCase()}s.`} />
              </div>
              <Input
                value={filters.practice_group ?? ""}
                onChange={(e) => setFilters((f) => ({ ...f, practice_group: e.target.value || undefined }))}
                placeholder="e.g. Corporate"
              />
            </div>
            <div className="space-y-1 md:col-span-2">
              <div className="text-xs text-slate-600">
                Flag (exact)
                <InfoTip text="Prompt injection flags indicate a document may be trying to override instructions." />
              </div>
              <Select
                value={filters.flag ?? ANY}
                onValueChange={(v) => setFilters((f) => ({ ...f, flag: v === ANY ? undefined : v }))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Any" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ANY}>Any</SelectItem>
                  <SelectItem value="PROMPT_INJECTION_SUSPECTED">Prompt Injection</SelectItem>
                  <SelectItem value="EMBEDDED_INJECTION_SUSPECTED">Embedded Injection</SelectItem>
                  <SelectItem value="SENSITIVE_REQUEST">Sensitive Request</SelectItem>
                  <SelectItem value="DOS_RISK">DoS Risk</SelectItem>
                  <SelectItem value="SYSTEM_PROMPT_EXPOSURE">System Prompt Exposure</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-end gap-2 md:col-span-2">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" className="w-full">
                    Views
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="w-64">
                  <DropdownMenuLabel>Saved Filters</DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  {views.length === 0 ? <DropdownMenuItem disabled>No saved views</DropdownMenuItem> : null}
                  {views.map((v) => (
                    <DropdownMenuItem
                      key={v.id}
                      onSelect={() => {
                        setFilters(v.filters);
                        toast.push({ title: "View loaded", description: v.name });
                      }}
                    >
                      {v.name}
                    </DropdownMenuItem>
                  ))}
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onSelect={() => setSaveOpen(true)}>Save current…</DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
              <Button variant="outline" className="w-full" onClick={() => setFilters({})}>
                Clear
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="p-4">
            <CardTitle className="text-base">Events</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {searchQuery.isLoading ? (
              <div className="p-4 text-sm text-slate-600">Loading…</div>
            ) : searchQuery.isError ? (
              <div className="p-4 text-sm text-red-700">Failed to load audit events.</div>
            ) : (
              <>
                <div className="overflow-auto">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 bg-white">
                      {table.getHeaderGroups().map((hg) => (
                        <tr key={hg.id} className="border-b">
                          {hg.headers.map((h) => (
                            <th
                              key={h.id}
                              className="px-3 py-2 text-left text-xs font-medium text-slate-600"
                              onClick={h.column.getCanSort() ? h.column.getToggleSortingHandler() : undefined}
                              role={h.column.getCanSort() ? "button" : undefined}
                              aria-label={h.column.getCanSort() ? `Sort ${String(h.column.columnDef.header)}` : undefined}
                            >
                              <div className={h.column.getCanSort() ? "flex cursor-pointer items-center gap-1" : ""}>
                                {flexRender(h.column.columnDef.header, h.getContext())}
                                {h.column.getIsSorted() === "asc" ? <span>↑</span> : null}
                                {h.column.getIsSorted() === "desc" ? <span>↓</span> : null}
                              </div>
                            </th>
                          ))}
                        </tr>
                      ))}
                    </thead>
                    <tbody>
                      {table.getRowModel().rows.map((r) => (
                        <tr
                          key={r.id}
                          className="cursor-pointer border-b hover:bg-slate-50"
                          onClick={() => setSelectedId(r.original.id)}
                        >
                          {r.getVisibleCells().map((c) => (
                            <td key={c.id} className="px-3 py-2 align-top">
                              {flexRender(c.column.columnDef.cell, c.getContext())}
                            </td>
                          ))}
                        </tr>
                      ))}
                      {table.getRowModel().rows.length === 0 ? (
                        <tr>
                          <td colSpan={table.getVisibleLeafColumns().length} className="px-3 py-6 text-center text-sm text-slate-600">
                            No AI activity matches the current filters. If this is a new organization, create an API key and route a test
                            request through {productName}.
                          </td>
                        </tr>
                      ) : null}
                    </tbody>
                  </table>
                </div>

                <div className="flex items-center justify-between p-3 text-sm">
                  <div className="text-slate-600">
                    {offset + 1}–{Math.min(offset + limit, searchQuery.data?.total ?? 0)} of {searchQuery.data?.total ?? 0}
                  </div>
                  <div className="flex items-center gap-2">
                    <Button variant="outline" disabled={page === 0} onClick={() => setPage((p) => Math.max(0, p - 1))}>
                      Prev
                    </Button>
                    <Button
                      variant="outline"
                      disabled={offset + limit >= (searchQuery.data?.total ?? 0)}
                      onClick={() => setPage((p) => p + 1)}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        <Dialog open={saveOpen} onOpenChange={setSaveOpen}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>Save View</DialogTitle>
              <DialogDescription>Save the current filter set locally in this browser.</DialogDescription>
            </DialogHeader>
            <div className="space-y-2">
              <div className="text-xs text-slate-600">Name</div>
              <Input value={saveViewName} onChange={(e) => setSaveViewName(e.target.value)} placeholder="e.g. High severity blocks" />
              <div className="flex items-center justify-end gap-2 pt-2">
                <Button variant="outline" onClick={() => setSaveOpen(false)}>
                  Cancel
                </Button>
                <Button
                  onClick={() => {
                    const name = saveViewName.trim();
                    if (!name) return;
                    const next: SavedView[] = [{ id: crypto.randomUUID(), name, filters }, ...views].slice(0, 20);
                    setViews(next);
                    saveViews(next);
                    setSaveViewName("");
                    setSaveOpen(false);
                    toast.push({ title: "Saved", description: name });
                  }}
                >
                  Save
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        <Dialog open={!!selectedId} onOpenChange={(open) => (!open ? setSelectedId(null) : null)}>
          <DialogContent className="max-w-3xl">
            <DialogHeader>
              <DialogTitle>Event Details</DialogTitle>
              <DialogDescription>Metadata and risk signals (pilot)</DialogDescription>
            </DialogHeader>
            {detailQuery.isLoading ? (
              <div className="text-sm text-slate-600">Loading…</div>
            ) : detailQuery.isError ? (
              <div className="text-sm text-red-700">Failed to load event.</div>
            ) : detailQuery.data ? (
              <div className="space-y-3">
                {detailQuery.data.outcome === "fail" &&
                (detailQuery.data.action_type === "POLICY_BLOCK" || detailQuery.data.action_type === "PHI_FLAG") ? (
                  <div className="rounded-lg border border-red-200 bg-red-50 p-4">
                    <div className="text-sm font-semibold text-red-900">{appConfig.terminology.messages.blocked_by_rules}</div>
                    <div className="mt-1 text-sm text-red-900">
                      <span className="font-medium">Reason:</span> {detailQuery.data.reason ?? "Blocked"}
                    </div>
                    <div className="mt-1 text-xs text-red-800">
                      This request was not sent to the AI model because it violated your organization’s governance rules.
                    </div>
                  </div>
                ) : null}
                <div className="flex items-center justify-between">
                  <div className="text-xs text-slate-600">
                    {detailQuery.data.action_type} • {formatDateTime(detailQuery.data.timestamp)}
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      onClick={async () => {
                        const rid = detailQuery.data!.request_id ?? detailQuery.data!.id;
                        await navigator.clipboard.writeText(rid);
                        toast.push({ title: "Copied", description: "Request ID copied to clipboard." });
                      }}
                    >
                      Copy request_id
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() =>
                        downloadBlob(
                          new Blob([JSON.stringify(detailQuery.data, null, 2)], { type: "application/json" }),
                          `audit-event-${detailQuery.data!.id}.json`,
                        )
                      }
                    >
                      Export JSON
                    </Button>
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <Card>
                    <CardHeader className="p-4">
                      <CardTitle className="text-sm">Summary</CardTitle>
                    </CardHeader>
                  <CardContent className="space-y-1 p-4 pt-0 text-sm">
                      <KV k="Request ID" v={detailQuery.data.request_id ?? detailQuery.data.id} />
                      <KV
                        k="Actor"
                        v={
                          detailQuery.data.user_email
                            ? `${detailQuery.data.user_email}${detailQuery.data.user_role ? ` (${detailQuery.data.user_role})` : ""}`
                            : detailQuery.data.api_key_name
                              ? `${detailQuery.data.api_key_name} (API key)`
                              : detailQuery.data.api_key_id
                                ? `API key ${detailQuery.data.api_key_id.slice(0, 8)}`
                                : "—"
                        }
                      />
                      <KV k="Action" v={detailQuery.data.action_type} />
                      <KV k="Outcome" v={detailQuery.data.outcome} />
                      <KV k="Reason" v={detailQuery.data.reason ?? "—"} />
                      <KV k="Provider" v={detailQuery.data.provider ?? "—"} />
                      <KV k="Model" v={detailQuery.data.model ?? "—"} />
                      <KV k="Cost" v={detailQuery.data.cost_usd != null ? formatUsd(detailQuery.data.cost_usd) : "—"} />
                    </CardContent>
                  </Card>
                  <Card>
                    <CardHeader className="p-4">
                      <CardTitle className="text-sm">Risk Signals</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2 p-4 pt-0 text-sm">
                      <div className="flex items-center justify-between gap-3">
                        <div className="text-xs text-slate-600">Confidentiality Exposure Level</div>
                        <ExposureBadge
                          level={detailQuery.data.confidentiality_exposure_level}
                          score={detailQuery.data.phi_score}
                        />
                      </div>
                      <KV k="Severity" v={detailQuery.data.severity ?? "—"} />
                      <div className="text-xs text-slate-600">Flags</div>
                      <div className="flex flex-wrap gap-1">
                        {(detailQuery.data.risk_flags ?? []).length ? (
                          (detailQuery.data.risk_flags ?? []).map((f) => <Badge key={f}>{f}</Badge>)
                        ) : (
                          <span className="text-sm text-slate-600">—</span>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                </div>

                <Card>
                  <CardHeader className="p-4">
                    <CardTitle className="text-sm">Context</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-1 p-4 pt-0 text-sm">
                    <KV k={primaryEntityLabel} v={detailQuery.data.matter_id ?? "—"} />
                    <KV k={secondaryEntityLabel} v={detailQuery.data.practice_group ?? "—"} />
                    <KV k={externalPartyLabel} v={detailQuery.data.client_name ?? "—"} />
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="p-4">
                    <CardTitle className="text-sm">Redaction & Hashes</CardTitle>
                  </CardHeader>
                  <CardContent className="grid grid-cols-1 gap-3 p-4 pt-0 md:grid-cols-2">
                    <div className="space-y-1">
                      <div className="text-xs text-slate-600">Prompt hash</div>
                      <div className="font-mono text-xs">{detailQuery.data.prompt_hash ?? "—"}</div>
                      <div className="text-xs text-slate-600">Redacted prompt</div>
                      <div className="rounded border bg-white p-2 font-mono text-xs text-slate-800">
                        {detailQuery.data.redacted_prompt ?? "—"}
                      </div>
                    </div>
                    <div className="space-y-1">
                      <div className="text-xs text-slate-600">Response hash</div>
                      <div className="font-mono text-xs">{detailQuery.data.response_hash ?? "—"}</div>
                      <div className="text-xs text-slate-600">Redacted response</div>
                      <div className="rounded border bg-white p-2 font-mono text-xs text-slate-800">
                        {detailQuery.data.redacted_response ?? "—"}
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="p-4">
                    <CardTitle className="text-sm">Raw JSON</CardTitle>
                  </CardHeader>
                  <CardContent className="p-4 pt-0">
                    <pre className="max-h-[260px] overflow-auto rounded bg-slate-100 p-3 text-xs">
                      {JSON.stringify(detailQuery.data, null, 2)}
                    </pre>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="p-4">
                    <CardTitle className="text-sm">Related Events</CardTitle>
                  </CardHeader>
                  <CardContent className="p-4 pt-0">
                    {relatedQuery.isLoading ? (
                      <div className="text-sm text-slate-600">Loading…</div>
                    ) : relatedQuery.isError ? (
                      <div className="text-sm text-red-700">Failed to load related events.</div>
                    ) : (relatedQuery.data ?? []).length === 0 ? (
                      <div className="text-sm text-slate-600">No related events (same API key ±5 minutes).</div>
                    ) : (
                      <div className="space-y-1">
                        {(relatedQuery.data ?? []).map((ev) => (
                          <button
                            key={ev.id}
                            className="flex w-full items-center justify-between gap-2 rounded border border-slate-200 bg-white px-2 py-2 text-left text-xs hover:bg-slate-50"
                            onClick={() => setSelectedId(ev.id)}
                          >
                            <div className="min-w-0">
                              <div className="truncate">
                                {ev.action_type} • {ev.outcome}
                              </div>
                              <div className="text-slate-600">{formatDateTime(ev.timestamp)}</div>
                            </div>
                            <div className="font-mono text-[11px] text-slate-700">{shortId(ev.id)}</div>
                          </button>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>
            ) : null}
          </DialogContent>
        </Dialog>
      </RequireTenantScope>
    </main>
  );
}

function KV({ k, v }: { k: string; v: any }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <div className="text-xs text-slate-600">{k}</div>
      <div className="min-w-0 text-right text-sm text-slate-900">{String(v)}</div>
    </div>
  );
}
