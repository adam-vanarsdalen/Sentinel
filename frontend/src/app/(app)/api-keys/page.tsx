"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { RequireTenantScope } from "@/components/layout/require-tenant";
import { RequireRole } from "@/components/layout/require-role";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api-client";
import { useAppConfig } from "@/lib/app-config-context";
import { formatDateTime } from "@/lib/format";
import { hasAnyRole, isPlatformAdmin } from "@/lib/roles";
import { useToast } from "@/components/toaster";
import { useActiveTenantId } from "@/lib/tenant";

export default function ApiKeysPage() {
  const appConfig = useAppConfig();
  const qc = useQueryClient();
  const toast = useToast();
  const tenantId = useActiveTenantId();
  const gatewayUrl = process.env.NEXT_PUBLIC_GATEWAY_URL ?? "https://your-domain.com";

  React.useEffect(() => {
    document.title = `API Keys — ${appConfig.product.name}`;
  }, [appConfig.product.name]);

  const meQuery = useQuery({ queryKey: ["me"], queryFn: () => api.auth.me() });
  const canManage = hasAnyRole(meQuery.data?.role, ["org_admin", "super_admin"]);
  const canView = hasAnyRole(meQuery.data?.role, ["super_admin", "org_admin", "operator"]);
  const tenantReady = !!meQuery.data && (!isPlatformAdmin(meQuery.data.role) || !!tenantId);

  const keysQuery = useQuery({
    queryKey: ["apiKeys"],
    queryFn: () => api.apiKeys.list(),
    enabled: canView && tenantReady,
  });

  const [createOpen, setCreateOpen] = React.useState(false);
  const [name, setName] = React.useState("");
  const [createdToken, setCreatedToken] = React.useState<string | null>(null);
  const [pendingRevokeId, setPendingRevokeId] = React.useState<string | null>(null);

  const createMut = useMutation({
    mutationFn: async () => api.apiKeys.create(name),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["apiKeys"] });
      setCreatedToken(res.token);
      toast.push({ title: "API key created", description: "Secret shown once—copy now." });
    },
  });

  const revokeMut = useMutation({
    mutationFn: async (id: string) => api.apiKeys.revoke(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["apiKeys"] });
      toast.push({ title: "API key revoked" });
    },
  });

  const pendingRevokeKey = React.useMemo(
    () => (keysQuery.data ?? []).find((k) => k.id === pendingRevokeId) ?? null,
    [keysQuery.data, pendingRevokeId],
  );

  return (
    <main className="space-y-4" data-testid="api-keys">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">API Keys</h1>
        {canManage ? (
          <Dialog
            open={createOpen}
            onOpenChange={(open) => {
              setCreateOpen(open);
              if (!open) {
                setName("");
                setCreatedToken(null);
              }
            }}
          >
            <DialogTrigger asChild>
              <Button>Create key</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create API key</DialogTitle>
                <DialogDescription>Secret shown once. Store in a secure vault.</DialogDescription>
              </DialogHeader>
              {createdToken ? (
                <div className="space-y-2">
                  <div className="text-sm font-medium">Secret (copy now)</div>
                  <pre className="overflow-auto rounded bg-slate-100 p-3 text-xs">{createdToken}</pre>
                  <Button
                    variant="outline"
                    onClick={async () => {
                      await navigator.clipboard.writeText(createdToken);
                      toast.push({ title: "Copied", description: "API key copied to clipboard." });
                    }}
                  >
                    Copy
                  </Button>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="text-xs text-slate-600">Name</div>
                  <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. contract-review-tool" />
                </div>
              )}
              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() => {
                    setCreateOpen(false);
                    setName("");
                    setCreatedToken(null);
                  }}
                >
                  Close
                </Button>
                {!createdToken ? (
                  <Button disabled={!name || createMut.isPending} onClick={() => createMut.mutate()}>
                    {createMut.isPending ? "Creating…" : "Create"}
                  </Button>
                ) : null}
              </DialogFooter>
            </DialogContent>
          </Dialog>
        ) : null}
      </div>

      <RequireRole allow={["super_admin", "org_admin", "operator"]}>
      <RequireTenantScope>
        <Dialog open={!!pendingRevokeId} onOpenChange={(open) => (!open ? setPendingRevokeId(null) : null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Revoke {pendingRevokeKey?.name ?? "key"}?</DialogTitle>
              <DialogDescription>
                Any integration using this key will stop working immediately. This cannot be undone.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="outline" onClick={() => setPendingRevokeId(null)} disabled={revokeMut.isPending}>
                Cancel
              </Button>
              <Button
                variant="destructive"
                disabled={!pendingRevokeId || revokeMut.isPending}
                onClick={() => {
                  const id = pendingRevokeId;
                  setPendingRevokeId(null);
                  if (id) revokeMut.mutate(id);
                }}
              >
                {revokeMut.isPending ? "Revoking…" : "Revoke"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        <Card>
          <CardHeader className="p-4">
            <CardTitle className="text-base">Keys</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {keysQuery.isLoading ? (
              <div className="p-4 text-sm text-slate-600">Loading…</div>
            ) : keysQuery.isError ? (
              <div className="p-4 text-sm text-red-700">Failed to load API keys.</div>
            ) : (
              <div className="overflow-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-white">
                    <tr className="border-b">
                      <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Name</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Prefix</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Created</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Last used</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Status</th>
                      <th className="px-3 py-2 text-right text-xs font-medium text-slate-600">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(keysQuery.data ?? []).map((k) => (
                      <tr key={k.id} className="border-b">
                        <td className="px-3 py-2">{k.name}</td>
                        <td className="px-3 py-2 font-mono text-xs">{k.key_prefix}</td>
                        <td className="px-3 py-2">{formatDateTime(k.created_at)}</td>
                        <td className="px-3 py-2">{k.last_used_at ? formatDateTime(k.last_used_at) : "—"}</td>
                        <td className="px-3 py-2">
                          {k.is_active ? <Badge variant="secondary">active</Badge> : <Badge>revoked</Badge>}
                        </td>
                        <td className="px-3 py-2 text-right">
                          <Button
                            variant="destructive"
                            size="sm"
                            disabled={!canManage || !k.is_active || revokeMut.isPending}
                            onClick={() => setPendingRevokeId(k.id)}
                          >
                            Revoke
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="p-4">
            <CardTitle className="text-base">How to use an API key</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 p-4 pt-0 text-sm">
            <div className="text-slate-700">
              Route your AI tool through {appConfig.product.name} by replacing the provider base URL with your {appConfig.product.name} gateway
              endpoint.
            </div>
            <div className="rounded border border-slate-200 bg-slate-50 p-3 text-sm">
              <span className="text-xs text-slate-600">Your gateway URL:</span>
              <div className="mt-1 font-mono text-sm font-medium text-slate-900">{gatewayUrl}</div>
            </div>
            <pre className="overflow-auto rounded bg-slate-100 p-3 font-mono text-xs">{`curl ${gatewayUrl}/v1/chat/completions \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"model": "gpt-4.1", "messages": [{"role": "user", \\
       "content": "Draft a non-disclosure clause"}]}'`}</pre>
            <div className="text-slate-700">
              Replace YOUR_API_KEY with the token shown when you created your key. The gateway is OpenAI-compatible —
              any tool that supports a custom base URL will work.
            </div>
            <div>
              <a className="underline underline-offset-2" href="/help">
                See Help &amp; Glossary for more setup guidance.
              </a>
            </div>
          </CardContent>
        </Card>
      </RequireTenantScope>
      </RequireRole>
    </main>
  );
}
