"use client";

import Link from "next/link";
import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { RequireTenantScope } from "@/components/layout/require-tenant";
import { RequireRole } from "@/components/layout/require-role";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription as DialogDesc, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api } from "@/lib/api-client";
import { useAppConfig } from "@/lib/app-config-context";
import { hasAnyRole, isPlatformAdmin } from "@/lib/roles";
import { useToast } from "@/components/toaster";
import { useActiveTenantId } from "@/lib/tenant";

type StorageMode = "off" | "redacted" | "full";

export default function SettingsPage() {
  const appConfig = useAppConfig();
  const qc = useQueryClient();
  const toast = useToast();
  const tenantId = useActiveTenantId();

  React.useEffect(() => {
    document.title = `Settings — ${appConfig.product.name}`;
  }, [appConfig.product.name]);

  const meQuery = useQuery({ queryKey: ["me"], queryFn: () => api.auth.me() });
  const canView = hasAnyRole(meQuery.data?.role, ["org_admin", "compliance_admin", "super_admin"]);
  const tenantReady = !!meQuery.data && (!isPlatformAdmin(meQuery.data.role) || !!tenantId);

  const settingsQuery = useQuery({
    queryKey: ["settings", "current"],
    queryFn: () => api.settings.getCurrent(),
    enabled: canView && tenantReady,
  });

  const canWrite = hasAnyRole(meQuery.data?.role, ["org_admin", "compliance_admin", "super_admin"]);

  const [storageMode, setStorageMode] = React.useState<StorageMode>("off");
  const [retentionDays, setRetentionDays] = React.useState<string>("");
  const [confirmFullOpen, setConfirmFullOpen] = React.useState(false);
  const [pendingMode, setPendingMode] = React.useState<StorageMode | null>(null);

  React.useEffect(() => {
    const s = settingsQuery.data?.settings_json ?? null;
    if (!s) return;
    setStorageMode((s.storage_mode as StorageMode) ?? "off");
    setRetentionDays(s.retention_days != null ? String(s.retention_days) : "");
  }, [settingsQuery.data]);

  const saveMut = useMutation({
    mutationFn: async () =>
      api.settings.updateCurrent({
        storage_mode: storageMode,
        retention_days: retentionDays ? Number(retentionDays) : null,
      }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["settings", "current"] });
      toast.push({ title: "Settings saved" });
    },
  });

  return (
    <main className="space-y-4" data-testid="settings">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Settings</h1>
        <Button disabled={!canWrite || saveMut.isPending} onClick={() => saveMut.mutate()}>
          {saveMut.isPending ? "Saving…" : "Save"}
        </Button>
      </div>

      <RequireRole allow={["super_admin", "org_admin", "compliance_admin"]}>
        <RequireTenantScope>
          <Dialog open={confirmFullOpen} onOpenChange={setConfirmFullOpen}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Enable full content storage?</DialogTitle>
                <DialogDesc>
                  This may store raw prompts/responses in the audit database. Treat as high risk because it can contain
                  sensitive data.
                </DialogDesc>
              </DialogHeader>
              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() => {
                    setConfirmFullOpen(false);
                    setPendingMode(null);
                  }}
                >
                  Cancel
                </Button>
                <Button
                  onClick={() => {
                    if (pendingMode) setStorageMode(pendingMode);
                    setConfirmFullOpen(false);
                    setPendingMode(null);
                    toast.push({ title: "Storage mode updated", description: "Remember to set retention appropriately." });
                  }}
                >
                  I understand
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          <Card>
            <CardHeader className="p-4">
              <CardTitle className="text-base">Content Storage</CardTitle>
              <CardDescription>
                Default recommendation: keep raw prompt/response storage <strong>OFF</strong>. If enabled, treat audit
                data as sensitive.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-1 gap-3 p-4 pt-0 md:grid-cols-3">
              <div className="space-y-1">
                <div className="text-xs text-slate-600">Storage mode</div>
                <Select
                  value={storageMode}
                  onValueChange={(v) => {
                    const next = v as StorageMode;
                    if (next === "full" && storageMode !== "full") {
                      setPendingMode(next);
                      setConfirmFullOpen(true);
                      return;
                    }
                    setStorageMode(next);
                  }}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="off">OFF (hash only)</SelectItem>
                    <SelectItem value="redacted">Store redacted snippet</SelectItem>
                    <SelectItem value="full">Store full content (high risk)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <div className="text-xs text-slate-600">Retention days</div>
                <Input
                  value={retentionDays}
                  onChange={(e) => setRetentionDays(e.target.value)}
                  placeholder="e.g. 30"
                  inputMode="numeric"
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="p-4">
              <CardTitle className="text-base">Governance Alerts</CardTitle>
              <CardDescription>Alert recipients, throttling, and delivery channels are managed on the dedicated Alerts page.</CardDescription>
            </CardHeader>
            <CardContent className="flex items-center justify-between gap-3 p-4 pt-0 text-sm">
              <div className="text-slate-600">
                Use Alerts to manage notification recipients, webhook delivery, trigger events, and recent alert history.
              </div>
              <Link
                href="/alerts"
                className="inline-flex h-10 items-center justify-center rounded-md border border-slate-200 px-4 py-2 text-sm font-medium text-slate-900 hover:bg-slate-50"
              >
                Open Alerts
              </Link>
            </CardContent>
          </Card>
        </RequireTenantScope>
      </RequireRole>
    </main>
  );
}
