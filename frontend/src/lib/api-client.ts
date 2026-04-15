import { z } from "zod";

import { fetchJson, HttpError } from "./http";
import { getActiveTenantId, isTenantOverrideEnabled, setActiveTenantId, setTenantOverrideEnabled } from "./tenant";
import {
  ApiKeyCreateResponseSchema,
  ApiKeySchema,
  AuditEventSchema,
  AuditSearchResponseSchema,
  CreateUserResponseSchema,
  EvalRunSchema,
  EvalRunDetailSchema,
  EvalSuiteCaseSchema,
  MeSchema,
  MetricsOverviewSchema,
  CostSummarySchema,
  RiskSummarySchema,
  PolicyResponseSchema,
  PolicyVersionSchema,
  ProviderConfigSchema,
  ProviderCatalogSchema,
  ProviderPolicySchema,
  AlertHistoryItemSchema,
  AlertSettingsSchema,
  AlertTestResponseSchema,
  SettingsSchema,
  TenantSchema,
  TokenResponseSchema,
  UserListItemSchema,
  type ApiKeyCreateResponse,
  type AuditEvent,
  type AuditSearchResponse,
  type CreateUserResponse,
  type EvalRun,
  type EvalRunDetail,
  type EvalSuiteCase,
  type Me,
  type MetricsOverview,
  type CostSummary,
  type RiskSummary,
  type PolicyResponse,
  type PolicyVersion,
  type ProviderConfig,
  type ProviderCatalog,
  type ProviderPolicy,
  type AlertHistoryItem,
  type AlertSettings,
  type AlertTestResponse,
  type TenantSettings,
  type Tenant,
  type TokenResponse,
  type UserListItem,
} from "./schemas";

type RequestOptions = {
  tenantId?: string | null;
};

function withTenant(headers: HeadersInit | undefined, tenantId?: string | null): HeadersInit {
  if (tenantId === null) return headers ?? {};
  const effectiveTenantId =
    tenantId ??
    (typeof window !== "undefined" && isTenantOverrideEnabled() ? getActiveTenantId() ?? undefined : undefined);
  if (!effectiveTenantId) return headers ?? {};
  return { ...(headers ?? {}), "X-Tenant-Id": effectiveTenantId };
}

async function getWithSchema<S extends z.ZodTypeAny>(
  path: string,
  schema: S,
  opts: RequestOptions = {},
): Promise<z.output<S>> {
  const data = await fetchJson<unknown>(`/api/proxy${path}`, {
    method: "GET",
    headers: withTenant(undefined, opts.tenantId),
  });
  return schema.parse(data);
}

async function postWithSchema<S extends z.ZodTypeAny>(
  path: string,
  body: unknown,
  schema: S,
  opts: RequestOptions = {},
): Promise<z.output<S>> {
  const data = await fetchJson<unknown>(`/api/proxy${path}`, {
    method: "POST",
    body: JSON.stringify(body),
    headers: withTenant(undefined, opts.tenantId),
  });
  return schema.parse(data);
}

async function putWithSchema<S extends z.ZodTypeAny>(
  path: string,
  body: unknown,
  schema: S,
  opts: RequestOptions = {},
): Promise<z.output<S>> {
  const data = await fetchJson<unknown>(`/api/proxy${path}`, {
    method: "PUT",
    body: JSON.stringify(body),
    headers: withTenant(undefined, opts.tenantId),
  });
  return schema.parse(data);
}

async function patchWithSchema<S extends z.ZodTypeAny>(
  path: string,
  body: unknown,
  schema: S,
  opts: RequestOptions = {},
): Promise<z.output<S>> {
  const data = await fetchJson<unknown>(`/api/proxy${path}`, {
    method: "PATCH",
    body: JSON.stringify(body),
    headers: withTenant(undefined, opts.tenantId),
  });
  return schema.parse(data);
}

async function deleteWithSchema<S extends z.ZodTypeAny>(
  path: string,
  schema: S,
  opts: RequestOptions = {},
): Promise<z.output<S>> {
  const data = await fetchJson<unknown>(`/api/proxy${path}`, {
    method: "DELETE",
    headers: withTenant(undefined, opts.tenantId),
  });
  return schema.parse(data);
}

export const api = {
  auth: {
    login: (email: string, password: string): Promise<TokenResponse> =>
      postWithSchema("/auth/login", { email, password }, TokenResponseSchema),
    me: async (opts?: RequestOptions): Promise<Me> => {
      try {
        return await getWithSchema("/auth/me", MeSchema, opts);
      } catch (e) {
        if (e instanceof HttpError && e.status === 400) {
          const detail =
            e.detail ??
            (e.body && typeof e.body === "object" && "detail" in (e.body as any) ? (e.body as any).detail : null);
          if (typeof detail === "string" && detail.includes("Invalid X-Tenant-Id")) {
            setActiveTenantId(null);
            return await getWithSchema("/auth/me", MeSchema, { ...(opts ?? {}), tenantId: null });
          }
        }
        if (e instanceof HttpError && e.status === 403) {
          const detail =
            e.detail ??
            (e.body && typeof e.body === "object" && "detail" in (e.body as any) ? (e.body as any).detail : null);
          if (e.code === "TENANT_SCOPE_ERROR" || (typeof detail === "string" && detail.includes("Tenant override not permitted"))) {
            setTenantOverrideEnabled(false);
            setActiveTenantId(null);
            return await getWithSchema("/auth/me", MeSchema, { ...(opts ?? {}), tenantId: null });
          }
        }
        throw e;
      }
    },
  },
  tenants: {
    list: (opts?: RequestOptions): Promise<Tenant[]> =>
      getWithSchema("/admin/tenants", z.array(TenantSchema), opts),
  },
  platformTenants: {
    list: (
      params: { query?: string; status?: string; page?: number; page_size?: number; sort?: string } = {},
      opts?: RequestOptions,
    ) => {
      const qs = new URLSearchParams();
      for (const [k, v] of Object.entries(params)) {
        if (v === undefined || v === null || v === "") continue;
        qs.set(k, String(v));
      }
      return getWithSchema(
        `/platform/tenants?${qs.toString()}`,
        z.object({
          items: z.array(TenantSchema),
          total: z.number().int(),
          page: z.number().int(),
          page_size: z.number().int(),
        }),
        opts,
      );
    },
    create: (payload: { name: string; slug?: string; status?: string }, opts?: RequestOptions) =>
      postWithSchema(
        "/platform/tenants",
        payload,
        z.object({ tenant: TenantSchema }),
        opts,
      ),
    get: (tenantId: string, opts?: RequestOptions) =>
      getWithSchema(
        `/platform/tenants/${tenantId}`,
        z.object({
          tenant: z.object({
            ...TenantSchema.shape,
            settings_json: z.record(z.any()),
          }),
        }),
        opts,
      ),
    update: (tenantId: string, payload: { name?: string; slug?: string; status?: string }, opts?: RequestOptions) =>
      patchWithSchema(
        `/platform/tenants/${tenantId}`,
        payload,
        z.object({ tenant: TenantSchema }),
        opts,
      ),
    switch: (tenantId: string, opts?: RequestOptions) =>
      postWithSchema(
        `/platform/tenants/${tenantId}/switch`,
        {},
        z.object({ current_tenant: TenantSchema }),
        opts,
      ),
    summary: (tenantId: string, range: "24h" | "7d" | "30d" = "7d", opts?: RequestOptions) =>
      getWithSchema(
        `/platform/tenants/${tenantId}/summary?range=${range}`,
        z.object({ tenant: z.record(z.any()), summary: z.record(z.any()) }),
        opts,
      ),
  },
  apiKeys: {
    list: (opts?: RequestOptions) => getWithSchema("/admin/api-keys", z.array(ApiKeySchema), opts),
    create: (name: string, opts?: RequestOptions): Promise<ApiKeyCreateResponse> =>
      postWithSchema("/admin/api-keys", { name }, ApiKeyCreateResponseSchema, opts),
    revoke: (id: string, opts?: RequestOptions) =>
      postWithSchema(`/admin/api-keys/${id}/revoke`, {}, ApiKeySchema, opts),
  },
  providerConfigs: {
    catalog: (opts?: RequestOptions): Promise<ProviderCatalog> =>
      getWithSchema("/admin/provider-configs/catalog", ProviderCatalogSchema, opts),
    list: (opts?: RequestOptions): Promise<ProviderConfig[]> =>
      getWithSchema("/admin/provider-configs", z.array(ProviderConfigSchema), opts),
    create: (
      payload: {
        provider_type: string;
        display_name: string;
        is_enabled?: boolean;
        is_default?: boolean;
        model_allowlist?: string[];
        config_json?: Record<string, unknown> | null;
        secret_json?: Record<string, unknown> | null;
      },
      opts?: RequestOptions,
    ): Promise<ProviderConfig> => postWithSchema("/admin/provider-configs", payload, ProviderConfigSchema, opts),
    update: (
      id: string,
      payload: {
        display_name?: string;
        is_enabled?: boolean;
        is_default?: boolean;
        model_allowlist?: string[];
        config_json?: Record<string, unknown> | null;
        secret_json?: Record<string, unknown> | null;
        clear_secret?: boolean;
      },
      opts?: RequestOptions,
    ): Promise<ProviderConfig> => patchWithSchema(`/admin/provider-configs/${id}`, payload, ProviderConfigSchema, opts),
    delete: (id: string, opts?: RequestOptions) =>
      deleteWithSchema(`/admin/provider-configs/${id}`, z.object({ ok: z.boolean() }), opts),
    setDefault: (id: string, opts?: RequestOptions): Promise<ProviderConfig> =>
      postWithSchema(`/admin/provider-configs/${id}/set-default`, {}, ProviderConfigSchema, opts),
    testConnection: (id: string, opts?: RequestOptions) =>
      postWithSchema(
        `/admin/provider-configs/${id}/test-connection`,
        {},
        z.object({ ok: z.boolean(), provider_type: z.string(), model: z.string() }),
        opts,
      ),
  },
  providerPolicy: {
    get: (opts?: RequestOptions): Promise<ProviderPolicy> =>
      getWithSchema("/admin/provider-configs/policy", ProviderPolicySchema, opts),
    update: (
      payload: {
        default_provider?: string | null;
        providers: Array<{
          provider_type: string;
          is_enabled: boolean;
          allowed_models?: string[];
          default_model?: string | null;
        }>;
      },
      opts?: RequestOptions,
    ): Promise<ProviderPolicy> => putWithSchema("/admin/provider-configs/policy", payload, ProviderPolicySchema, opts),
  },
  policy: {
    getCurrent: (opts?: RequestOptions): Promise<PolicyResponse> =>
      getWithSchema("/admin/policy/current", PolicyResponseSchema, opts),
    updateCurrent: (
      payload: {
        policy_json: Record<string, unknown>;
        change_note?: string | null;
        source_template_id?: string | null;
      },
      opts?: RequestOptions,
    ): Promise<PolicyResponse> => putWithSchema("/admin/policy/current", payload, PolicyResponseSchema, opts),
    test: (policy_json: Record<string, unknown>, opts?: RequestOptions) =>
      postWithSchema("/admin/policy/test", { policy_json }, z.object({ ok: z.boolean() }), opts),
    dryRun: (
      payload: {
        policy_json: Record<string, unknown>;
        model: string;
        messages: Array<Record<string, any>>;
        response_text?: string | null;
        metadata?: Record<string, any> | null;
      },
      opts?: RequestOptions,
    ) => postWithSchema("/admin/policy/dry-run", payload, z.record(z.any()), opts),
    versions: (opts?: RequestOptions): Promise<PolicyVersion[]> =>
      getWithSchema("/admin/policy/versions", z.array(PolicyVersionSchema), opts),
    history: (opts?: RequestOptions): Promise<PolicyVersion[]> =>
      getWithSchema("/admin/policy/history", z.array(PolicyVersionSchema), opts),
    historyItem: (versionId: string, opts?: RequestOptions): Promise<PolicyVersion> =>
      getWithSchema(`/admin/policy/history/${versionId}`, PolicyVersionSchema, opts),
    rollback: (versionId: string, opts?: RequestOptions): Promise<PolicyResponse> =>
      postWithSchema(`/admin/policy/rollback/${versionId}`, {}, PolicyResponseSchema, opts),
    templates: (opts?: RequestOptions) =>
      getWithSchema(
        "/admin/policy/templates",
        z.array(z.object({ id: z.string(), name: z.string(), description: z.string() })),
        opts,
      ),
    template: (templateId: string, opts?: RequestOptions) =>
      getWithSchema(
        `/admin/policy/templates/${templateId}`,
        z.object({ id: z.string(), name: z.string(), description: z.string(), policy_json: z.record(z.any()) }),
        opts,
      ),
  },
  audit: {
    list: (params: { start?: string; end?: string; action_type?: string }, opts?: RequestOptions): Promise<AuditEvent[]> => {
      const qs = new URLSearchParams();
      if (params.start) qs.set("start", params.start);
      if (params.end) qs.set("end", params.end);
      if (params.action_type) qs.set("action_type", params.action_type);
      return getWithSchema(`/admin/audit-events?${qs.toString()}`, z.array(AuditEventSchema), opts);
    },
    search: (
      params: {
        start?: string;
        end?: string;
        action_type?: string;
        outcome?: string;
        severity?: string;
        api_key_id?: string;
        user_id?: string;
        practice_group?: string;
        matter_id?: string;
        matter_query?: string;
        flag?: string;
        limit?: number;
        offset?: number;
      },
      opts?: RequestOptions,
    ): Promise<AuditSearchResponse> => {
      const qs = new URLSearchParams();
      for (const [k, v] of Object.entries(params)) {
        if (v === undefined || v === null || v === "") continue;
        qs.set(k, String(v));
      }
      return getWithSchema(`/admin/audit-events/search?${qs.toString()}`, AuditSearchResponseSchema, opts);
    },
    get: (id: string, opts?: RequestOptions): Promise<AuditEvent> =>
      getWithSchema(`/admin/audit-events/${id}`, AuditEventSchema, opts),
  },
  evals: {
    run: (provider: string, model: string, opts?: RequestOptions) =>
      postWithSchema("/admin/evals/run", { provider, model }, z.object({ run_id: z.string(), status: z.string() }), opts),
    runs: (opts?: RequestOptions): Promise<EvalRun[]> =>
      getWithSchema("/admin/evals/runs", z.array(EvalRunSchema), opts),
    suites: (opts?: RequestOptions): Promise<EvalSuiteCase[]> =>
      getWithSchema("/admin/evals/suites", z.array(EvalSuiteCaseSchema), opts),
    runDetail: (runId: string, opts?: RequestOptions): Promise<EvalRunDetail> =>
      getWithSchema(`/admin/evals/runs/${runId}`, EvalRunDetailSchema, opts),
  },
  metrics: {
    overview: (range: "24h" | "7d" | "30d", opts?: RequestOptions): Promise<MetricsOverview> =>
      getWithSchema(`/admin/metrics/overview?range=${range}`, MetricsOverviewSchema, opts),
    riskSummary: (range: "24h" | "7d" | "30d" = "7d", opts?: RequestOptions): Promise<RiskSummary> =>
      getWithSchema(`/admin/metrics/risk-summary?range=${range}`, RiskSummarySchema, opts),
    costSummary: (opts?: RequestOptions): Promise<CostSummary> =>
      getWithSchema("/admin/metrics/cost-summary", CostSummarySchema, opts),
  },
  settings: {
    getCurrent: (opts?: RequestOptions): Promise<TenantSettings> =>
      getWithSchema("/admin/settings/current", SettingsSchema, opts),
    updateCurrent: (settings_json: Record<string, unknown>, opts?: RequestOptions): Promise<TenantSettings> =>
      putWithSchema("/admin/settings/current", { settings_json }, SettingsSchema, opts),
  },
  alerts: {
    getCurrent: (opts?: RequestOptions): Promise<AlertSettings> =>
      getWithSchema("/admin/alerts/current", AlertSettingsSchema, opts),
    updateCurrent: (
      payload: {
        phi_threshold: number;
        severity_threshold: "low" | "med" | "high";
        email_recipients: string[];
        webhook_url?: string | null;
        clear_webhook?: boolean;
        webhook_format?: "generic" | "slack" | "teams";
        triggers: {
          high_confidentiality_exposure: boolean;
          prompt_injection_detected: boolean;
          policy_blocked: boolean;
          repeated_provider_failures: boolean;
          blocked_request_spike: boolean;
        };
        throttle_window_minutes: number;
        provider_failure_threshold: number;
      },
      opts?: RequestOptions,
    ): Promise<AlertSettings> => putWithSchema("/admin/alerts/current", payload, AlertSettingsSchema, opts),
    history: (limit = 20, opts?: RequestOptions): Promise<AlertHistoryItem[]> =>
      getWithSchema(`/admin/alerts/history?limit=${limit}`, z.array(AlertHistoryItemSchema), opts),
    sendTest: (opts?: RequestOptions): Promise<AlertTestResponse> =>
      postWithSchema("/admin/alerts/test", {}, AlertTestResponseSchema, opts),
  },
  users: {
    list: (opts?: RequestOptions): Promise<UserListItem[]> =>
      getWithSchema("/admin/users", z.array(UserListItemSchema), opts),
    create: (
      payload: { email: string; role: string; tenant_id?: string | null },
      opts?: RequestOptions,
    ): Promise<CreateUserResponse> => postWithSchema("/admin/users", payload, CreateUserResponseSchema, opts),
    updateRole: (userId: string, role: string, opts?: RequestOptions): Promise<UserListItem> =>
      putWithSchema(`/admin/users/${userId}/role`, { role }, UserListItemSchema, opts),
    delete: (userId: string, opts?: RequestOptions): Promise<UserListItem> =>
      deleteWithSchema(`/admin/users/${userId}`, UserListItemSchema, opts),
  },
};
