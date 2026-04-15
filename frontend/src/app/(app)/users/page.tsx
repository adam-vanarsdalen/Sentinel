"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import * as SelectPrimitive from "@radix-ui/react-select";

import { RequireTenantScope } from "@/components/layout/require-tenant";
import { RequireRole } from "@/components/layout/require-role";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api-client";
import { useToast } from "@/components/toaster";
import { formatDateTime } from "@/lib/format";
import { useAppConfig } from "@/lib/app-config-context";
import { ASSIGNABLE_ROLES, hasAnyRole, isPlatformAdmin } from "@/lib/roles";
import { useActiveTenantId } from "@/lib/tenant";

const ROLES = ASSIGNABLE_ROLES;
const DEFAULT_ROLE_META: Record<
  (typeof ROLES)[number],
  { label: string; description: string }
> = {
  org_admin: { label: "Org Admin", description: "Full access — can manage users and rules" },
  compliance_admin: { label: "Compliance Admin", description: "Can manage governance settings and review activity" },
  operator: { label: "Operator", description: "Can manage API keys and run tests" },
  reviewer: { label: "Reviewer", description: "Can view dashboard and activity" },
  auditor: { label: "Auditor", description: "Read-only access to logs and reports" },
};

function RoleSelectItem({
  role,
  meta,
}: {
  role: (typeof ROLES)[number];
  meta: { label: string; description: string };
}) {
  return (
    <SelectPrimitive.Item
      value={role}
      className="relative flex w-full cursor-default select-none flex-col gap-0.5 rounded-sm px-2 py-1.5 text-sm outline-none focus:bg-slate-100"
    >
      <SelectPrimitive.ItemText>{meta.label}</SelectPrimitive.ItemText>
      <div className="text-xs text-slate-600">{meta.description}</div>
    </SelectPrimitive.Item>
  );
}

export default function UsersPage() {
  const appConfig = useAppConfig();
  const qc = useQueryClient();
  const toast = useToast();
  const router = useRouter();
  const tenantId = useActiveTenantId();
  const roleMeta = React.useMemo(
    () =>
      Object.fromEntries(
        ROLES.map((role) => [
          role,
          {
            label: appConfig.roles[role]?.label ?? DEFAULT_ROLE_META[role].label,
            description: appConfig.roles[role]?.description ?? DEFAULT_ROLE_META[role].description,
          },
        ]),
      ) as Record<(typeof ROLES)[number], { label: string; description: string }>,
    [appConfig.roles],
  );

  React.useEffect(() => {
    document.title = `Users & Roles — ${appConfig.product.name}`;
  }, [appConfig.product.name]);

  const meQuery = useQuery({ queryKey: ["me"], queryFn: () => api.auth.me() });
  const canView = hasAnyRole(meQuery.data?.role, ["org_admin", "super_admin"]);
  const tenantReady = !!meQuery.data && (!isPlatformAdmin(meQuery.data.role) || !!tenantId);
  const usersQuery = useQuery({ queryKey: ["users"], queryFn: () => api.users.list(), enabled: canView && tenantReady });

  const canManage = hasAnyRole(meQuery.data?.role, ["org_admin", "super_admin"]);

  const [showInactive, setShowInactive] = React.useState(false);
  const [open, setOpen] = React.useState(false);
  const [email, setEmail] = React.useState("");
  const [role, setRole] = React.useState<(typeof ROLES)[number]>("reviewer");
  const [tempPassword, setTempPassword] = React.useState<string | null>(null);
  const [pendingDeleteUserId, setPendingDeleteUserId] = React.useState<string | null>(null);

  const createMut = useMutation({
    mutationFn: async () => api.users.create({ email, role }),
    onSuccess: async (res) => {
      setTempPassword(res.temp_password);
      await qc.invalidateQueries({ queryKey: ["users"] });
      toast.push({ title: "User created", description: "Temp password shown once." });
    },
  });

  const updateRoleMut = useMutation({
    mutationFn: async (payload: { userId: string; role: string }) => api.users.updateRole(payload.userId, payload.role),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["users"] });
      toast.push({ title: "Role updated" });
    },
  });

  const deleteMut = useMutation({
    mutationFn: async (userId: string) => api.users.delete(userId),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["users"] });
      toast.push({ title: "User removed", description: "Access removed. Audit records are preserved." });
    },
  });

  const visibleUsers = React.useMemo(() => {
    const all = usersQuery.data ?? [];
    return showInactive ? all : all.filter((u) => u.is_active);
  }, [usersQuery.data, showInactive]);

  const [selectedUserId, setSelectedUserId] = React.useState<string | null>(null);
  const selectedUser = React.useMemo(
    () => (usersQuery.data ?? []).find((u) => u.id === selectedUserId) ?? null,
    [usersQuery.data, selectedUserId],
  );
  const pendingDeleteUser = React.useMemo(
    () => (usersQuery.data ?? []).find((u) => u.id === pendingDeleteUserId) ?? null,
    [usersQuery.data, pendingDeleteUserId],
  );

  const userActivityQuery = useQuery({
    queryKey: ["audit", "search", "by-user", selectedUserId],
    queryFn: () => api.audit.search({ user_id: selectedUserId!, limit: 50, offset: 0 }),
    enabled: !!selectedUserId && canView && tenantReady,
  });

  return (
    <main className="space-y-4" data-testid="users">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Users & Roles</h1>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => setShowInactive((v) => !v)}>
            {showInactive ? "Hide inactive" : "Show inactive"}
          </Button>
          {canManage ? (
            <Dialog
              open={open}
              onOpenChange={(next) => {
                setOpen(next);
                if (!next) {
                  setEmail("");
                  setRole("reviewer");
                  setTempPassword(null);
                }
              }}
            >
              <DialogTrigger asChild>
                <Button>Create user</Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Create user</DialogTitle>
                  <DialogDescription>Pilot: creates a user with a temporary password.</DialogDescription>
                </DialogHeader>
                {tempPassword ? (
                  <div className="space-y-2">
                    <div className="text-sm font-medium">Temporary password</div>
                    <pre className="overflow-auto rounded bg-slate-100 p-3 text-xs">{tempPassword}</pre>
                    <Button
                      variant="outline"
                      onClick={async () => {
                        await navigator.clipboard.writeText(tempPassword);
                        toast.push({ title: "Copied" });
                      }}
                    >
                      Copy
                    </Button>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                    <div className="space-y-1">
                      <div className="text-xs text-slate-600">Email</div>
                      <Input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="user@example.com" />
                    </div>
                    <div className="space-y-1">
                      <div className="text-xs text-slate-600">Role</div>
                      <Select value={role} onValueChange={(v) => setRole(v as any)}>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {ROLES.map((r) => (
                            <RoleSelectItem key={r} role={r} meta={roleMeta[r]} />
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                )}
                <DialogFooter>
                  <Button
                    variant="outline"
                    onClick={() => {
                      setOpen(false);
                      setEmail("");
                      setRole("reviewer");
                      setTempPassword(null);
                    }}
                  >
                    Close
                  </Button>
                  {!tempPassword ? (
                    <Button disabled={!email || createMut.isPending} onClick={() => createMut.mutate()}>
                      {createMut.isPending ? "Creating…" : "Create"}
                    </Button>
                  ) : null}
                </DialogFooter>
              </DialogContent>
            </Dialog>
          ) : null}
        </div>
      </div>

      <RequireRole allow={["super_admin", "org_admin"]}>
      <RequireTenantScope>
        <Card>
          <CardHeader className="p-4">
            <CardTitle className="text-base">Users</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {usersQuery.isLoading ? (
              <div className="p-4 text-sm text-slate-600">Loading…</div>
            ) : usersQuery.isError ? (
              <div className="p-4 text-sm text-red-700">Failed to load users.</div>
            ) : (
              <div className="overflow-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-white">
                    <tr className="border-b">
                      <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Email</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Role</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Status</th>
                      <th className="px-3 py-2 text-right text-xs font-medium text-slate-600">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleUsers.map((u) => (
                      <tr
                        key={u.id}
                        className="cursor-pointer border-b hover:bg-slate-50"
                        onClick={() => setSelectedUserId(u.id)}
                      >
                        <td className="px-3 py-2">{u.email}</td>
                        <td className="px-3 py-2">
                          <Badge variant="secondary">{appConfig.roles[u.role]?.label ?? roleMeta[u.role as (typeof ROLES)[number]]?.label ?? u.role}</Badge>
                        </td>
                        <td className="px-3 py-2">{u.is_active ? "active" : "inactive"}</td>
                        <td className="px-3 py-2 text-right">
                          {canManage ? (
                            <div className="flex justify-end gap-2">
                              <Select
                                value={u.role}
                                onValueChange={(v) => updateRoleMut.mutate({ userId: u.id, role: v })}
                                disabled={!u.is_active}
                              >
                                <SelectTrigger className="w-[160px]" onClick={(e) => e.stopPropagation()}>
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  {ROLES.map((r) => (
                                    <RoleSelectItem key={r} role={r} meta={roleMeta[r]} />
                                  ))}
                                </SelectContent>
                              </Select>
                              <Button
                                variant="destructive"
                                disabled={
                                  !u.is_active ||
                                  deleteMut.isPending ||
                                  u.id === meQuery.data?.id ||
                                  u.role === "super_admin"
                                }
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setPendingDeleteUserId(u.id);
                                }}
                              >
                                Delete
                              </Button>
                            </div>
                          ) : (
                            "—"
                          )}
                        </td>
                      </tr>
                    ))}
                    {visibleUsers.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="px-3 py-6 text-center text-sm text-slate-600">
                          No users match the current view.
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        <Dialog open={!!pendingDeleteUserId} onOpenChange={(open) => (!open ? setPendingDeleteUserId(null) : null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Delete user?</DialogTitle>
              <DialogDescription>This will revoke access immediately. Audit records are preserved.</DialogDescription>
            </DialogHeader>
            <div className="rounded border border-slate-200 bg-white p-3 text-sm">
              <div className="text-xs text-slate-600">User</div>
              <div className="mt-1 font-medium">{pendingDeleteUser?.email ?? "—"}</div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setPendingDeleteUserId(null)} disabled={deleteMut.isPending}>
                Cancel
              </Button>
              <Button
                variant="destructive"
                disabled={!pendingDeleteUserId || deleteMut.isPending}
                onClick={() => {
                  const id = pendingDeleteUserId;
                  setPendingDeleteUserId(null);
                  if (id) deleteMut.mutate(id);
                }}
              >
                {deleteMut.isPending ? "Deleting…" : "Delete"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        <Dialog open={!!selectedUserId} onOpenChange={(open) => (!open ? setSelectedUserId(null) : null)}>
          <DialogContent className="max-w-4xl">
            <DialogHeader>
              <DialogTitle>User Activity</DialogTitle>
              <DialogDescription>Recent actions for auditing (last 50 events).</DialogDescription>
            </DialogHeader>

            {selectedUser ? (
              <div className="rounded-lg border bg-white p-3 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate font-medium">{selectedUser.email}</div>
                    <div className="text-xs text-slate-600">
                      {appConfig.roles[selectedUser.role]?.label ?? selectedUser.role} • {selectedUser.is_active ? "active" : "inactive"} • Created {formatDateTime(selectedUser.created_at)}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      onClick={() => {
                        router.push(`/logs?user_id=${encodeURIComponent(selectedUser.id)}`);
                        setSelectedUserId(null);
                      }}
                    >
                      View in AI Activity Log
                    </Button>
                  </div>
                </div>
              </div>
            ) : null}

            {userActivityQuery.isLoading ? (
              <div className="text-sm text-slate-600">Loading activity…</div>
            ) : userActivityQuery.isError ? (
              <div className="text-sm text-red-700">Failed to load activity.</div>
            ) : (
              <div className="overflow-auto rounded-lg border">
                <table className="w-full text-sm">
                  <thead className="bg-white">
                    <tr className="border-b">
                      <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Time</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Action</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Outcome</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(userActivityQuery.data?.items ?? []).map((ev) => (
                      <tr key={ev.id} className="border-b">
                        <td className="px-3 py-2 whitespace-nowrap">{formatDateTime(ev.timestamp)}</td>
                        <td className="px-3 py-2 font-mono text-xs">{ev.action_type}</td>
                        <td className="px-3 py-2">
                          <Badge variant="secondary">{ev.outcome}</Badge>
                        </td>
                        <td className="px-3 py-2 text-slate-700">{ev.reason ?? "—"}</td>
                      </tr>
                    ))}
                    {(userActivityQuery.data?.items ?? []).length === 0 ? (
                      <tr>
                        <td colSpan={4} className="px-3 py-6 text-center text-sm text-slate-600">
                          No activity recorded for this user yet.
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </RequireTenantScope>
      </RequireRole>
    </main>
  );
}
