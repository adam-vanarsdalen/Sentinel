"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import * as React from "react";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { PresetSelector } from "@/components/preset-selector";
import { useAppConfig } from "@/lib/app-config-context";
import { api } from "@/lib/api-client";
import { fetchJson, HttpError } from "@/lib/http";
import { hasAnyRole, isPlatformAdmin } from "@/lib/roles";
import { getActiveTenantId, setActiveTenantId, setTenantOverrideEnabled } from "@/lib/tenant";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [mobileNavOpen, setMobileNavOpen] = React.useState(false);
  const appConfig = useAppConfig();
  const terms = appConfig.terminology;

  const meQuery = useQuery({ queryKey: ["me"], queryFn: () => api.auth.me() });
  const tenantMeQuery = useQuery({
    queryKey: ["tenant_me"],
    queryFn: async () => {
      const controller = new AbortController();
      const t = setTimeout(() => controller.abort(), 1500);
      try {
        return await fetchJson("/api/proxy/admin/tenants/me", { signal: controller.signal });
      } catch {
        return null;
      } finally {
        clearTimeout(t);
      }
    },
    enabled: Boolean(meQuery.data?.tenant_id) && meQuery.data?.role !== "super_admin",
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

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
  const healthQuery = useQuery({
    queryKey: ["healthz"],
    queryFn: async () => {
      const controller = new AbortController();
      const t = setTimeout(() => controller.abort(), 1500);
      try {
        return await fetchJson("/api/proxy/healthz", { signal: controller.signal });
      } catch {
        return null;
      } finally {
        clearTimeout(t);
      }
    },
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const [activeTenantId, setActiveTenant] = React.useState<string | null>(() => getActiveTenantId());

  React.useEffect(() => {
    setActiveTenantId(activeTenantId);
  }, [activeTenantId]);

  React.useEffect(() => {
    if (!meQuery.data) return;
    const role = meQuery.data.role;
    if (isPlatformAdmin(role)) {
      setTenantOverrideEnabled(true);
      return;
    }
    setTenantOverrideEnabled(false);
    if (activeTenantId) setActiveTenant(null);
  }, [meQuery.data, activeTenantId]);

  const tenantsQuery = useQuery({
    queryKey: ["tenants"],
    queryFn: () => api.tenants.list(),
    enabled: isPlatformAdmin(meQuery.data?.role),
  });
  const presetNames = React.useMemo(
    () =>
      Object.fromEntries(appConfig.available_presets.map((preset) => [preset.id, preset.name])),
    [appConfig.available_presets],
  );

  const role = meQuery.data?.role;
  const nav = [
    { href: "/dashboard", label: "Dashboard" },
    { href: "/logs", label: terms.activity_log_label },
    { href: "/policies", label: terms.rules_label },
    { href: "/users", label: "Users & Roles" },
    { href: "/api-keys", label: "API Keys" },
    { href: "/providers", label: "Provider Settings" },
    { href: "/alerts", label: "Alerts" },
    { href: "/settings", label: "Settings" },
    { href: "/evaluations", label: "Evaluations" },
    { href: "/firms", label: terms.organization_plural },
    { href: "/help", label: "Help & Glossary" },
  ].filter((item) => {
    if (!role) return false;
    if (item.href === "/firms") return isPlatformAdmin(role);
    if (item.href === "/users") return hasAnyRole(role, ["org_admin", "super_admin"]);
    if (item.href === "/providers") return hasAnyRole(role, ["org_admin"]);
    if (item.href === "/alerts") return hasAnyRole(role, ["org_admin", "compliance_admin"]);
    if (item.href === "/settings") return hasAnyRole(role, ["org_admin", "compliance_admin", "super_admin"]);
    if (item.href === "/api-keys") return hasAnyRole(role, ["org_admin", "operator", "super_admin"]);
    if (item.href === "/policies") return hasAnyRole(role, ["org_admin", "compliance_admin", "operator", "auditor", "reviewer", "super_admin"]);
    if (item.href === "/evaluations") return hasAnyRole(role, ["org_admin", "operator", "super_admin"]);
    return true;
  });
  const roleLabel = role ? appConfig.roles[role]?.label ?? role : null;

  async function logout() {
    await fetchJson("/api/auth/logout", { method: "POST" });
    router.replace("/login");
  }

  const tenantName =
    isPlatformAdmin(meQuery.data?.role)
      ? tenantsQuery.data?.find((t) => t.id === activeTenantId)?.name ?? null
      : (typeof (tenantMeQuery.data as any)?.name === "string"
          ? ((tenantMeQuery.data as any).name as string)
          : typeof (tenantMeQuery.data as any)?.tenant?.name === "string"
            ? (((tenantMeQuery.data as any).tenant.name as string) ?? null)
            : null);
  const appVersion =
    (typeof (healthQuery.data as any)?.version === "string" ? ((healthQuery.data as any).version as string) : undefined) ||
    process.env.NEXT_PUBLIC_APP_VERSION;
  const sidebarContent = (
    <>
      <div className="px-2 pb-2 text-sm font-semibold">{appConfig.product.name}</div>
      <nav className="space-y-1">
        {nav.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setMobileNavOpen(false)}
              className={[
                "block rounded-md px-2 py-1.5 text-sm",
                active ? "bg-slate-100 text-slate-900" : "text-slate-700 hover:bg-slate-50",
              ].join(" ")}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="mt-4 border-t border-slate-200 pt-3">
        <Button variant="ghost" className="w-full justify-start" onClick={logout}>
          Sign out
        </Button>
      </div>
      <div className="mt-3 px-2 text-xs text-slate-500">{appVersion ? `Version ${appVersion}` : null}</div>
    </>
  );

  return (
    <div className="grid min-h-[calc(100vh-48px)] grid-cols-1 gap-6 md:grid-cols-[240px_1fr]">
      {mobileNavOpen ? (
        <div className="fixed inset-0 z-40 md:hidden">
          <button
            type="button"
            aria-label="Close navigation"
            className="absolute inset-0 bg-slate-950/40"
            onClick={() => setMobileNavOpen(false)}
          />
          <aside className="absolute inset-y-0 left-0 w-[240px] rounded-r-lg border-r border-slate-200 bg-white p-3 shadow-xl">
            {sidebarContent}
          </aside>
        </div>
      ) : null}

      <aside className="hidden rounded-lg border border-slate-200 bg-white p-3 md:block">{sidebarContent}</aside>

      <section className="space-y-4">
        <header className="flex items-center justify-between rounded-lg border border-slate-200 bg-white p-3">
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              className="h-9 w-9 px-0 md:hidden"
              aria-label="Open navigation"
              onClick={() => setMobileNavOpen((open) => !open)}
            >
              <span className="flex flex-col gap-1">
                <span className="block h-0.5 w-4 bg-current" />
                <span className="block h-0.5 w-4 bg-current" />
                <span className="block h-0.5 w-4 bg-current" />
              </span>
            </Button>
            <div className="text-sm font-medium">{appConfig.product.console_name}</div>
            {roleLabel ? <Badge variant="secondary">{roleLabel}</Badge> : null}
          </div>

          <div className="flex items-center gap-3">
            <PresetSelector label="Preset" compact />
            {isPlatformAdmin(meQuery.data?.role) ? (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                  <Button variant="outline" aria-label={`Select ${terms.organization_context}`}>
                    {tenantName ?? "Platform Admin"}
                  </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuLabel>{terms.organization_singular} context</DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onSelect={() => setActiveTenant(null)}>Platform Admin</DropdownMenuItem>
                  <DropdownMenuSeparator />
                  {tenantsQuery.data?.map((t) => (
                    <DropdownMenuItem key={t.id} onSelect={() => setActiveTenant(t.id)}>
                      {t.preset_id ? `${t.name} • ${presetNames[t.preset_id] ?? t.preset_id}` : t.name}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
                </DropdownMenu>
            ) : meQuery.data?.tenant_id ? (
              <Badge>{terms.organization_singular}: {tenantName ?? meQuery.data.tenant_id.slice(0, 8)}</Badge>
            ) : null}
            <div className="text-xs text-slate-600">{meQuery.data?.email ?? "…"}</div>
          </div>
        </header>

        {isPlatformAdmin(meQuery.data?.role) && activeTenantId && tenantName ? (
          <div className="flex items-center justify-between rounded-lg border border-slate-200 bg-white p-3 text-sm">
            <div>
              <span className="text-slate-600">Viewing as:</span> <span className="font-medium">{tenantName}</span>
            </div>
            <Button variant="outline" onClick={() => setActiveTenant(null)}>
              Return to Platform
            </Button>
          </div>
        ) : null}

        {isPlatformAdmin(meQuery.data?.role) && !activeTenantId ? (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            Select {terms.organization_context} context to view scoped dashboards, {terms.activity_log_label.toLowerCase()}, API keys, and {terms.rules_label.toLowerCase()}.
          </div>
        ) : null}

        <div>{children}</div>
      </section>
    </div>
  );
}
