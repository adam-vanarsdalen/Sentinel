"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { RequireRole } from "@/components/layout/require-role";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api } from "@/lib/api-client";
import { useAppConfig } from "@/lib/app-config-context";
import { useToast } from "@/components/toaster";
import { HttpError } from "@/lib/http";
import { isPlatformAdmin } from "@/lib/roles";

function slugify(s: string) {
  return (s || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/-{2,}/g, "-")
    .replace(/^-+|-+$/g, "");
}

export default function FirmsPage() {
  const appConfig = useAppConfig();
  const router = useRouter();
  const qc = useQueryClient();
  const toast = useToast();
  const orgSingular = appConfig.terminology.organization_singular;
  const orgPlural = appConfig.terminology.organization_plural;
  const orgContext = appConfig.terminology.organization_context;
  const presetNames = React.useMemo(
    () => Object.fromEntries(appConfig.available_presets.map((preset) => [preset.id, preset.name])),
    [appConfig.available_presets],
  );

  const meQuery = useQuery({ queryKey: ["me"], queryFn: () => api.auth.me() });
  const canView = isPlatformAdmin(meQuery.data?.role);

  const [query, setQuery] = React.useState("");
  const [showInactive, setShowInactive] = React.useState(false);
  const [statusFilter, setStatusFilter] = React.useState<string>("any");
  const [page, setPage] = React.useState(1);
  const pageSize = 20;
  const [pendingArchiveFirm, setPendingArchiveFirm] = React.useState<any | null>(null);

  const listQuery = useQuery({
    queryKey: ["platformTenants", { query, showInactive, statusFilter, page }],
    queryFn: () =>
      api.platformTenants.list({
        query: query || undefined,
        status: showInactive ? (statusFilter === "any" ? undefined : statusFilter) : "active",
        page,
        page_size: pageSize,
        sort: "created_at_desc",
      }),
    enabled: canView,
  });

  const [createOpen, setCreateOpen] = React.useState(false);
  const [name, setName] = React.useState("");
  const [slug, setSlug] = React.useState("");
  const [createStatus, setCreateStatus] = React.useState("active");
  const [createError, setCreateError] = React.useState<string | null>(null);

  const slugPreview = React.useMemo(() => (slug ? slugify(slug) : slugify(name)), [slug, name]);

  const createMut = useMutation({
    mutationFn: async () => api.platformTenants.create({ name, slug: slug || undefined, status: createStatus }),
    onSuccess: async (res) => {
      setCreateOpen(false);
      setName("");
      setSlug("");
      setCreateStatus("active");
      setCreateError(null);
      await qc.invalidateQueries({ queryKey: ["platformTenants"] });
      toast.push({ title: `${orgSingular} created`, description: res.tenant.name });
      router.push(`/firms/${res.tenant.id}`);
    },
    onError: (e) => {
      if (e instanceof HttpError && e.status === 409) setCreateError(`${orgSingular} already exists (duplicate slug).`);
      else setCreateError(`Failed to create ${orgContext}.`);
    },
  });

  const updateStatusMut = useMutation({
    mutationFn: async (payload: { tenantId: string; status: string }) =>
      api.platformTenants.update(payload.tenantId, { status: payload.status }),
    onSuccess: async (res) => {
      await qc.invalidateQueries({ queryKey: ["platformTenants"] });
      await qc.invalidateQueries({ queryKey: ["platformTenants", "get", res.tenant.id] });
      toast.push({ title: `${orgSingular} updated`, description: `${res.tenant.name} → ${res.tenant.status}` });
    },
    onError: () => toast.push({ title: "Update failed", description: `Unable to update ${orgContext}.` }),
  });

  const total = listQuery.data?.total ?? 0;
  const items = listQuery.data?.items ?? [];
  const maxPage = Math.max(1, Math.ceil(total / pageSize));

  return (
    <RequireRole allow={["super_admin"]}>
      <main className="space-y-4" data-testid="firms">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <h1 className="text-xl font-semibold">{orgPlural}</h1>
          <Button onClick={() => setCreateOpen(true)}>Create {orgContext}</Button>
        </div>

        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create {orgContext}</DialogTitle>
              <DialogDescription>{orgPlural} are isolated tenants. Slugs are URL-safe identifiers.</DialogDescription>
            </DialogHeader>
            <div className="space-y-3">
              <div className="space-y-1">
                <div className="text-xs text-slate-600">{orgSingular} name</div>
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Northwind Operations" />
              </div>
              <div className="space-y-1">
                <div className="text-xs text-slate-600">Slug (optional)</div>
                <Input value={slug} onChange={(e) => setSlug(e.target.value)} placeholder="e.g. anderson-cole" />
                <div className="text-xs text-slate-600">
                  Preview: <span className="font-mono">{slugPreview || "—"}</span>
                </div>
              </div>
              <div className="space-y-1">
                <div className="text-xs text-slate-600">Status</div>
                <Select value={createStatus} onValueChange={setCreateStatus}>
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
              {createError ? <div className="rounded border border-red-200 bg-red-50 p-2 text-xs text-red-900">{createError}</div> : null}
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setCreateOpen(false)}>
                Cancel
              </Button>
              <Button disabled={!name.trim() || createMut.isPending} onClick={() => createMut.mutate()}>
                {createMut.isPending ? "Creating…" : "Create"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        <Dialog open={!!pendingArchiveFirm} onOpenChange={(open) => (!open ? setPendingArchiveFirm(null) : null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Archive {pendingArchiveFirm?.name ?? orgContext}?</DialogTitle>
              <DialogDescription>Archive {pendingArchiveFirm?.name ?? orgContext}? The {orgContext} will be treated as inactive. This is reversible.</DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="outline" onClick={() => setPendingArchiveFirm(null)} disabled={updateStatusMut.isPending}>
                Cancel
              </Button>
              <Button
                variant="outline"
                disabled={!pendingArchiveFirm || updateStatusMut.isPending}
                onClick={() => {
                  const firm = pendingArchiveFirm;
                  setPendingArchiveFirm(null);
                  if (!firm?.id) return;
                  updateStatusMut.mutate({ tenantId: firm.id, status: "archived" });
                }}
              >
                Archive
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        <Card>
          <CardHeader className="p-4">
            <CardTitle className="text-base">Search</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-3 p-4 pt-0 md:grid-cols-6">
            <div className="space-y-1 md:col-span-4">
              <div className="text-xs text-slate-600">Name or slug</div>
              <Input
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setPage(1);
                }}
                placeholder="Search…"
              />
            </div>
            <div className="space-y-1 md:col-span-2">
              <div className="text-xs text-slate-600">Status</div>
              <Select
                value={statusFilter}
                onValueChange={(v) => {
                  setStatusFilter(v);
                  setPage(1);
                }}
                disabled={!showInactive}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="any">Any</SelectItem>
                  <SelectItem value="active">active</SelectItem>
                  <SelectItem value="suspended">suspended</SelectItem>
                  <SelectItem value="archived">archived</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="md:col-span-6">
              <Button
                variant="outline"
                onClick={() => {
                  setShowInactive((v) => !v);
                  setPage(1);
                }}
              >
                {showInactive ? "Hide inactive" : "Show inactive"}
              </Button>
              <span className="ml-2 text-xs text-slate-600">
                {showInactive ? (
                  <>
                    Inactive {orgPlural.toLowerCase()} are <span className="font-medium">suspended</span> or{" "}
                    <span className="font-medium">archived</span>.
                  </>
                ) : (
                  <>Showing active {orgPlural.toLowerCase()} only.</>
                )}
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="p-4">
            <CardTitle className="text-base">{showInactive ? `All ${orgPlural.toLowerCase()}` : `Active ${orgPlural.toLowerCase()}`}</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {listQuery.isLoading ? (
              <div className="p-4 text-sm text-slate-600">Loading…</div>
            ) : listQuery.isError ? (
              <div className="p-4 text-sm text-red-700">Failed to load {orgPlural.toLowerCase()}.</div>
            ) : (
              <>
                <div className="overflow-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 text-xs text-slate-600">
                      <tr className="border-b">
                        <th className="px-3 py-2 text-left">Name</th>
                        <th className="px-3 py-2 text-left">Preset</th>
                        <th className="px-3 py-2 text-left">Slug</th>
                        <th className="px-3 py-2 text-left">Status</th>
                        <th className="px-3 py-2 text-left">Created</th>
                        <th className="px-3 py-2 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((t) => (
                        <tr key={t.id} className="border-b hover:bg-slate-50">
                          <td className="px-3 py-2 font-medium">
                            <Link className="hover:underline" href={`/firms/${t.id}`}>
                              {t.name}
                            </Link>
                            {t.demo_summary ? <div className="mt-1 text-xs font-normal text-slate-600">{t.demo_summary}</div> : null}
                          </td>
                          <td className="px-3 py-2">
                            <div className="flex flex-wrap gap-2">
                              {t.preset_id ? <Badge variant="secondary">{presetNames[t.preset_id] ?? t.preset_id}</Badge> : null}
                              {t.demo_profile ? <Badge variant="secondary">{t.demo_profile}</Badge> : null}
                            </div>
                          </td>
                          <td className="px-3 py-2 font-mono text-xs">{t.slug}</td>
                          <td className="px-3 py-2">{t.status}</td>
                          <td className="px-3 py-2">{new Date(t.created_at).toLocaleString()}</td>
                          <td className="px-3 py-2 text-right">
                            <div className="flex justify-end gap-2">
                              {t.status === "archived" ? (
                                <Button
                                  variant="outline"
                                  disabled={updateStatusMut.isPending}
                                  onClick={() => updateStatusMut.mutate({ tenantId: t.id, status: "active" })}
                                >
                                  Unarchive
                                </Button>
                              ) : (
                                <Button
                                  variant="outline"
                                  disabled={updateStatusMut.isPending}
                                  onClick={() => {
                                    setPendingArchiveFirm(t);
                                  }}
                                >
                                  Archive
                                </Button>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                      {items.length === 0 ? (
                        <tr>
                          <td colSpan={6} className="px-3 py-6 text-center text-sm text-slate-600">
                            No {orgPlural.toLowerCase()} found.
                          </td>
                        </tr>
                      ) : null}
                    </tbody>
                  </table>
                </div>

                <div className="flex items-center justify-between p-3 text-sm">
                  <div className="text-slate-600">
                    Page {page} of {maxPage} • {total} total
                  </div>
                  <div className="flex items-center gap-2">
                    <Button variant="outline" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
                      Prev
                    </Button>
                    <Button
                      variant="outline"
                      disabled={page >= maxPage}
                      onClick={() => setPage((p) => Math.min(maxPage, p + 1))}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </main>
    </RequireRole>
  );
}
