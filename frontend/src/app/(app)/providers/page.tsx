"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { RequireRole } from "@/components/layout/require-role";
import { RequireTenantScope } from "@/components/layout/require-tenant";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api-client";
import { useAppConfig } from "@/lib/app-config-context";
import { formatDateTime } from "@/lib/format";
import { HttpError } from "@/lib/http";
import { hasAnyRole } from "@/lib/roles";
import type { ProviderCatalog, ProviderConfig, ProviderType } from "@/lib/schemas";

type ProviderFormState = {
  display_name: string;
  is_enabled: boolean;
  model_allowlist_text: string;
  base_url: string;
  default_model: string;
  endpoint: string;
  api_version: string;
  default_deployment: string;
  auth_mode: "api_key" | "managed_identity";
  managed_identity_client_id: string;
  api_key: string;
  clear_secret: boolean;
  connect_timeout_seconds: string;
  read_timeout_seconds: string;
  retry_count: string;
  fallback_enabled: boolean;
  fallback_provider: "" | ProviderType;
  fallback_model: string;
};

type ProviderMessage = {
  tone: "success" | "error" | "warning";
  title: string;
  detail?: string;
};

type ProviderDescriptor = {
  title: string;
  summary: string;
  help: string;
  defaultModelLabel: string;
};

const PROVIDER_ORDER: ProviderType[] = ["openai", "anthropic", "azure_openai"];

const PROVIDER_DETAILS: Record<ProviderType, ProviderDescriptor> = {
  openai: {
    title: "OpenAI",
    summary: "Use your organization's OpenAI account for GPT models.",
    help: "Best for teams already standardizing on OpenAI. Store the API key once and keep model access limited to the models your organization approves.",
    defaultModelLabel: "Default model",
  },
  anthropic: {
    title: "Anthropic",
    summary: "Use your organization's Anthropic account for Claude models.",
    help: "Useful if your team prefers Anthropic for longer-form review or drafting. Leave the API key blank after the first save to keep the existing key.",
    defaultModelLabel: "Default model",
  },
  azure_openai: {
    title: "Azure OpenAI",
    summary: "Use your organization's Azure-hosted OpenAI deployments.",
    help: "Recommended when your organization needs Azure tenancy controls. Add the Azure endpoint, API version, and the deployment name your applications should use.",
    defaultModelLabel: "Default deployment",
  },
};

const FALLBACK_DEFAULTS: Record<ProviderType, string[]> = {
  openai: ["gpt-4.1-mini", "gpt-4.1"],
  anthropic: ["claude-sonnet-4-6", "claude-opus-4-6"],
  azure_openai: ["gpt-4o-prod", "gpt-4.1-review"],
};

function catalogModels(catalog: ProviderCatalog | undefined, providerType: ProviderType): string[] {
  const fromApi = catalog?.providers.find((item) => item.id === providerType)?.models.map((model) => model.id) ?? [];
  if (fromApi.length > 0) return fromApi;
  return FALLBACK_DEFAULTS[providerType];
}

function parseAllowlist(text: string): string[] {
  return text
    .split(/[\n,]/g)
    .map((item) => item.trim())
    .filter(Boolean);
}

function joinAllowlist(models: string[] | undefined): string {
  return (models ?? []).join("\n");
}

function emptyForm(providerType: ProviderType): ProviderFormState {
  return {
    display_name: PROVIDER_DETAILS[providerType].title,
    is_enabled: false,
    model_allowlist_text: "",
    base_url: "",
    default_model: "",
    endpoint: "",
    api_version: "",
    default_deployment: "",
    auth_mode: "api_key",
    managed_identity_client_id: "",
    api_key: "",
    clear_secret: false,
    connect_timeout_seconds: "5",
    read_timeout_seconds: "60",
    retry_count: "0",
    fallback_enabled: false,
    fallback_provider: "",
    fallback_model: "",
  };
}

function formFromConfig(config: ProviderConfig | undefined, providerType: ProviderType): ProviderFormState {
  if (!config) return emptyForm(providerType);
  const cfg = config.config_json ?? {};
  const resilience = (cfg.resilience as Record<string, unknown> | undefined) ?? {};
  return {
    display_name: config.display_name,
    is_enabled: config.is_enabled,
    model_allowlist_text: joinAllowlist(config.model_allowlist),
    base_url: String(cfg.base_url ?? ""),
    default_model: String(cfg.default_model ?? ""),
    endpoint: String(cfg.endpoint ?? ""),
    api_version: String(cfg.api_version ?? ""),
    default_deployment: String(cfg.default_deployment ?? ""),
    auth_mode: cfg.auth_mode === "managed_identity" ? "managed_identity" : "api_key",
    managed_identity_client_id: String(cfg.managed_identity_client_id ?? ""),
    api_key: "",
    clear_secret: false,
    connect_timeout_seconds: String(resilience.connect_timeout_seconds ?? 5),
    read_timeout_seconds: String(resilience.read_timeout_seconds ?? 60),
    retry_count: String(resilience.retry_count ?? 0),
    fallback_enabled: Boolean(resilience.fallback_enabled),
    fallback_provider: (typeof resilience.fallback_provider === "string" ? resilience.fallback_provider : "") as "" | ProviderType,
    fallback_model: String(resilience.fallback_model ?? ""),
  };
}

function buildForms(configs: ProviderConfig[] | undefined): Record<ProviderType, ProviderFormState> {
  const byProvider = new Map((configs ?? []).map((config) => [config.provider_type, config]));
  return {
    openai: formFromConfig(byProvider.get("openai"), "openai"),
    anthropic: formFromConfig(byProvider.get("anthropic"), "anthropic"),
    azure_openai: formFromConfig(byProvider.get("azure_openai"), "azure_openai"),
  };
}

function emptyErrors(): Record<ProviderType, Record<string, string>> {
  return { openai: {}, anthropic: {}, azure_openai: {} };
}

function emptyMessages(): Record<ProviderType, ProviderMessage | null> {
  return { openai: null, anthropic: null, azure_openai: null };
}

function configLooksConfigured(providerType: ProviderType, config: ProviderConfig | undefined): boolean {
  if (!config) return false;
  if (providerType === "azure_openai" && String(config.config_json.auth_mode ?? "api_key") === "managed_identity") {
    return true;
  }
  return config.secret_configured;
}

function validateForm(
  providerType: ProviderType,
  form: ProviderFormState,
  config: ProviderConfig | undefined,
): Record<string, string> {
  const errors: Record<string, string> = {};
  const allowlist = parseAllowlist(form.model_allowlist_text);

  if (!form.display_name.trim()) {
    errors.display_name = "Enter a name your team will recognize.";
  }

  if ((providerType === "openai" || providerType === "anthropic") && !form.api_key.trim() && !config?.secret_configured) {
    errors.api_key = "An API key is required the first time you connect this provider.";
  }

  if (providerType === "openai" || providerType === "anthropic") {
    if (form.default_model.trim() && allowlist.length > 0 && !allowlist.includes(form.default_model.trim())) {
      errors.default_model = "The default model must also appear in the approved model list.";
    }
  }

  if (providerType === "azure_openai") {
    if (!form.endpoint.trim()) errors.endpoint = "Enter the Azure OpenAI endpoint.";
    if (!form.api_version.trim()) errors.api_version = "Enter the Azure API version.";
    if (form.auth_mode === "api_key" && !form.api_key.trim() && !config?.secret_configured) {
      errors.api_key = "An API key is required when Azure is using API-key authentication.";
    }
    if (!form.default_deployment.trim() && allowlist.length === 0) {
      errors.default_deployment = "Add a default deployment or at least one approved deployment.";
    }
    if (form.default_deployment.trim() && allowlist.length > 0 && !allowlist.includes(form.default_deployment.trim())) {
      errors.default_deployment = "The default deployment must also appear in the approved deployment list.";
    }
  }

  const connectTimeout = Number(form.connect_timeout_seconds);
  if (!Number.isFinite(connectTimeout) || connectTimeout < 0.5 || connectTimeout > 120) {
    errors.connect_timeout_seconds = "Use a connection timeout between 0.5 and 120 seconds.";
  }
  const readTimeout = Number(form.read_timeout_seconds);
  if (!Number.isFinite(readTimeout) || readTimeout < 1 || readTimeout > 600) {
    errors.read_timeout_seconds = "Use a response timeout between 1 and 600 seconds.";
  }
  const retryCount = Number(form.retry_count);
  if (!Number.isInteger(retryCount) || retryCount < 0 || retryCount > 3) {
    errors.retry_count = "Retry count must be a whole number from 0 to 3.";
  }
  if (form.fallback_enabled) {
    if (!form.fallback_provider) {
      errors.fallback_provider = "Choose a fallback provider.";
    }
    if (!form.fallback_model.trim()) {
      errors.fallback_model = "Enter the fallback model or deployment.";
    }
    if (
      form.fallback_provider === providerType &&
      form.fallback_model.trim() &&
      ((providerType === "azure_openai" ? form.default_deployment : form.default_model).trim() === form.fallback_model.trim())
    ) {
      errors.fallback_model = "Fallback target must differ from the primary default provider/model.";
    }
  }

  return errors;
}

function buildPayload(providerType: ProviderType, form: ProviderFormState) {
  const model_allowlist = parseAllowlist(form.model_allowlist_text);

  if (providerType === "openai" || providerType === "anthropic") {
    return {
      display_name: form.display_name.trim(),
      is_enabled: form.is_enabled,
      is_default: false,
      model_allowlist,
      config_json: {
        ...(form.base_url.trim() ? { base_url: form.base_url.trim() } : {}),
        ...(form.default_model.trim() ? { default_model: form.default_model.trim() } : {}),
        resilience: {
          connect_timeout_seconds: Number(form.connect_timeout_seconds),
          read_timeout_seconds: Number(form.read_timeout_seconds),
          retry_count: Number(form.retry_count),
          fallback_enabled: form.fallback_enabled,
          ...(form.fallback_enabled && form.fallback_provider ? { fallback_provider: form.fallback_provider } : {}),
          ...(form.fallback_enabled && form.fallback_model.trim() ? { fallback_model: form.fallback_model.trim() } : {}),
        },
      },
      secret_json: form.api_key.trim() ? { api_key: form.api_key.trim() } : null,
      clear_secret: false,
    };
  }

  return {
    display_name: form.display_name.trim(),
    is_enabled: form.is_enabled,
    is_default: false,
    model_allowlist,
    config_json: {
      endpoint: form.endpoint.trim(),
      api_version: form.api_version.trim(),
      auth_mode: form.auth_mode,
      ...(form.default_deployment.trim() ? { default_deployment: form.default_deployment.trim() } : {}),
      ...(form.managed_identity_client_id.trim() ? { managed_identity_client_id: form.managed_identity_client_id.trim() } : {}),
      resilience: {
        connect_timeout_seconds: Number(form.connect_timeout_seconds),
        read_timeout_seconds: Number(form.read_timeout_seconds),
        retry_count: Number(form.retry_count),
        fallback_enabled: form.fallback_enabled,
        ...(form.fallback_enabled && form.fallback_provider ? { fallback_provider: form.fallback_provider } : {}),
        ...(form.fallback_enabled && form.fallback_model.trim() ? { fallback_model: form.fallback_model.trim() } : {}),
      },
    },
    secret_json: form.api_key.trim() ? { api_key: form.api_key.trim() } : null,
    clear_secret: form.auth_mode === "managed_identity" ? form.clear_secret : false,
  };
}

function warningMessages(configs: Record<ProviderType, ProviderConfig | undefined>): string[] {
  const enabled = PROVIDER_ORDER.map((providerType) => configs[providerType]).filter(
    (config): config is ProviderConfig => Boolean(config?.is_enabled),
  );
  const defaultConfig = enabled.find((config) => config.is_default) ?? null;
  const warnings: string[] = [];

  if (enabled.length === 0) {
    warnings.push("No provider is enabled. Saved credentials will not be used until at least one provider is enabled.");
  }
  if (enabled.length > 1 && !defaultConfig) {
    warnings.push("More than one provider is enabled, but no default provider is selected yet.");
  }
  if (defaultConfig && !String(defaultConfig.config_json.default_model ?? defaultConfig.config_json.default_deployment ?? "").trim()) {
    warnings.push(`The default provider (${PROVIDER_DETAILS[defaultConfig.provider_type].title}) does not have a default model or deployment yet.`);
  }

  return warnings;
}

function MessageBanner({
  message,
  providerType,
}: {
  message: ProviderMessage | null;
  providerType: ProviderType;
}) {
  if (!message) return null;
  const toneClass =
    message.tone === "success"
      ? "border-emerald-200 bg-emerald-50 text-emerald-900"
      : message.tone === "warning"
        ? "border-amber-200 bg-amber-50 text-amber-900"
        : "border-red-200 bg-red-50 text-red-900";

  return (
    <div className={`rounded border p-3 text-sm ${toneClass}`} data-testid={`provider-message-${providerType}`}>
      <div className="font-medium">{message.title}</div>
      {message.detail ? <div className="mt-1 text-xs">{message.detail}</div> : null}
    </div>
  );
}

function FieldError({ error }: { error?: string }) {
  if (!error) return null;
  return <div className="text-xs text-red-700">{error}</div>;
}

export default function ProvidersPage() {
  const appConfig = useAppConfig();
  const qc = useQueryClient();
  const organizationLabel = appConfig.terminology.organization_context;

  React.useEffect(() => {
    document.title = `Provider Settings — ${appConfig.product.name}`;
  }, [appConfig.product.name]);

  const meQuery = useQuery({ queryKey: ["me"], queryFn: () => api.auth.me() });
  const canManage = hasAnyRole(meQuery.data?.role, ["org_admin"]);

  const providerConfigsQuery = useQuery({
    queryKey: ["providerConfigs"],
    queryFn: () => api.providerConfigs.list(),
    enabled: canManage,
  });
  const providerCatalogQuery = useQuery({
    queryKey: ["providerCatalog"],
    queryFn: () => api.providerConfigs.catalog(),
    enabled: canManage,
  });

  const configsByProvider = React.useMemo(() => {
    const rows = providerConfigsQuery.data ?? [];
    return {
      openai: rows.find((row) => row.provider_type === "openai"),
      anthropic: rows.find((row) => row.provider_type === "anthropic"),
      azure_openai: rows.find((row) => row.provider_type === "azure_openai"),
    } as Record<ProviderType, ProviderConfig | undefined>;
  }, [providerConfigsQuery.data]);

  const [forms, setForms] = React.useState<Record<ProviderType, ProviderFormState>>(() => buildForms(undefined));
  const [errorsByProvider, setErrorsByProvider] = React.useState<Record<ProviderType, Record<string, string>>>(() => emptyErrors());
  const [messagesByProvider, setMessagesByProvider] = React.useState<Record<ProviderType, ProviderMessage | null>>(() => emptyMessages());

  React.useEffect(() => {
    if (!providerConfigsQuery.data) return;
    setForms(buildForms(providerConfigsQuery.data));
    setErrorsByProvider(emptyErrors());
  }, [providerConfigsQuery.data]);

  const refresh = React.useCallback(async () => {
    await qc.invalidateQueries({ queryKey: ["providerConfigs"] });
  }, [qc]);

  const saveMut = useMutation({
    mutationFn: async ({ providerType, saveAndTest }: { providerType: ProviderType; saveAndTest: boolean }) => {
      const current = configsByProvider[providerType];
      const payload = buildPayload(providerType, forms[providerType]);
      const saved = current
        ? await api.providerConfigs.update(current.id, payload)
        : await api.providerConfigs.create({ provider_type: providerType, ...payload });
      let testResult: { ok: boolean; provider_type: string; model: string } | null = null;
      let testError: unknown = null;
      if (saveAndTest) {
        try {
          testResult = await api.providerConfigs.testConnection(saved.id);
        } catch (error) {
          testError = error;
        }
      }
      return { providerType, saved, testResult, testError };
    },
    onSuccess: async ({ providerType, testResult, testError }) => {
      await refresh();
      setErrorsByProvider((curr) => ({ ...curr, [providerType]: {} }));
      setMessagesByProvider((curr) => ({
        ...curr,
        [providerType]: testError
          ? {
              tone: "warning",
              title: "Settings saved, but the connection test failed.",
              detail:
                testError instanceof HttpError && testError.retryable
                  ? "The provider appears to be temporarily unavailable. Try testing again in a few minutes."
                  : testError instanceof Error
                    ? testError.message
                    : "Review the settings and try the connection test again.",
            }
          : testResult
            ? {
                tone: "success",
                title: "Saved and connected successfully.",
                detail: `${appConfig.product.name} reached ${PROVIDER_DETAILS[providerType].title} using ${testResult.model}.`,
              }
            : {
                tone: "success",
                title: "Provider settings saved.",
                detail: "Stored secrets remain hidden after save.",
              },
      }));
    },
    onError: (error: unknown, variables) => {
      const message =
        error instanceof HttpError
          ? error.message
          : error instanceof Error
            ? error.message
            : "Unable to save this provider configuration.";
      setMessagesByProvider((curr) => ({
        ...curr,
        [variables.providerType]: {
          tone: "error",
          title: "Save failed.",
          detail: message,
        },
      }));
    },
  });

  const testMut = useMutation({
    mutationFn: async ({ providerType, id }: { providerType: ProviderType; id: string }) => ({
      providerType,
      result: await api.providerConfigs.testConnection(id),
    }),
    onSuccess: ({ providerType, result }) => {
      setMessagesByProvider((curr) => ({
        ...curr,
        [providerType]: {
          tone: "success",
          title: "Connection successful.",
          detail: `${appConfig.product.name} reached ${PROVIDER_DETAILS[providerType].title} using ${result.model}.`,
        },
      }));
    },
    onError: (error: unknown, variables) => {
      const detail =
        error instanceof HttpError && error.retryable
          ? "The provider did not respond in time. Please try again in a few minutes."
          : error instanceof Error
            ? error.message
            : "Unable to verify this provider right now.";
      setMessagesByProvider((curr) => ({
        ...curr,
        [variables.providerType]: {
          tone: "error",
          title: "Connection test failed.",
          detail,
        },
      }));
    },
  });

  const setDefaultMut = useMutation({
    mutationFn: async ({ providerType, id }: { providerType: ProviderType; id: string }) => ({
      providerType,
      config: await api.providerConfigs.setDefault(id),
    }),
    onSuccess: async ({ providerType }) => {
      await refresh();
      setMessagesByProvider((curr) => ({
        ...curr,
        [providerType]: {
          tone: "success",
          title: "Default provider updated.",
          detail: `${PROVIDER_DETAILS[providerType].title} is now the default provider for this ${organizationLabel}.`,
        },
      }));
    },
  });

  const deleteMut = useMutation({
    mutationFn: async ({ providerType, id }: { providerType: ProviderType; id: string }) => {
      await api.providerConfigs.delete(id);
      return providerType;
    },
    onSuccess: async (providerType) => {
      await refresh();
      setMessagesByProvider((curr) => ({
        ...curr,
        [providerType]: {
          tone: "warning",
          title: "Connection removed.",
          detail: `${PROVIDER_DETAILS[providerType].title} is no longer configured for this ${organizationLabel}.`,
        },
      }));
    },
  });

  const updateForm = React.useCallback(
    (providerType: ProviderType, patch: Partial<ProviderFormState>) => {
      setForms((curr) => ({ ...curr, [providerType]: { ...curr[providerType], ...patch } }));
      setErrorsByProvider((curr) => ({ ...curr, [providerType]: {} }));
      setMessagesByProvider((curr) => ({ ...curr, [providerType]: null }));
    },
    [],
  );

  function saveProvider(providerType: ProviderType, saveAndTest: boolean) {
    const nextErrors = validateForm(providerType, forms[providerType], configsByProvider[providerType]);
    setErrorsByProvider((curr) => ({ ...curr, [providerType]: nextErrors }));
    if (Object.keys(nextErrors).length > 0) {
      setMessagesByProvider((curr) => ({
        ...curr,
        [providerType]: {
          tone: "error",
          title: "Please fix the highlighted fields.",
        },
      }));
      return;
    }
    saveMut.mutate({ providerType, saveAndTest });
  }

  function setDefault(providerType: ProviderType) {
    const config = configsByProvider[providerType];
    if (!config) return;
    const currentDefault = PROVIDER_ORDER.map((key) => configsByProvider[key]).find((row) => row?.is_default);
    if (
      currentDefault &&
      currentDefault.id !== config.id &&
      !window.confirm(
        `${PROVIDER_DETAILS[providerType].title} will replace ${PROVIDER_DETAILS[currentDefault.provider_type].title} as the default provider. Continue?`,
      )
    ) {
      return;
    }
    setDefaultMut.mutate({ providerType, id: config.id });
  }

  const warnings = React.useMemo(() => warningMessages(configsByProvider), [configsByProvider]);

  return (
    <main className="space-y-4" data-testid="provider-settings">
      <div className="space-y-1">
        <h1 className="text-xl font-semibold">Provider Settings</h1>
        <p className="text-sm text-slate-600">
          Manage your organization&apos;s OpenAI, Anthropic, and Azure OpenAI connections here. No CLI access or environment-file edits are needed.
        </p>
      </div>

      <RequireRole allow={["org_admin"]}>
        <RequireTenantScope>
          {!providerConfigsQuery.isLoading && !providerConfigsQuery.isError && warnings.length ? (
            <Card className="border-amber-200 bg-amber-50">
              <CardHeader className="p-4 pb-0">
                <CardTitle className="text-base text-amber-900">Action recommended</CardTitle>
                <CardDescription className="text-amber-900">
                  Review the items below before routing production traffic through {appConfig.product.name}.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-1 p-4 text-sm text-amber-900">
                {warnings.map((warning) => (
                  <div key={warning}>{warning}</div>
                ))}
              </CardContent>
            </Card>
          ) : null}

          {providerConfigsQuery.isLoading ? (
            <Card>
              <CardContent className="p-4 text-sm text-slate-600">Loading provider settings…</CardContent>
            </Card>
          ) : providerConfigsQuery.isError ? (
            <Card>
              <CardContent className="p-4 text-sm text-red-700">Failed to load provider settings.</CardContent>
            </Card>
          ) : (
            <div className="grid grid-cols-1 gap-4">
              {PROVIDER_ORDER.map((providerType) => {
                const descriptor = PROVIDER_DETAILS[providerType];
                const config = configsByProvider[providerType];
                const form = forms[providerType];
                const errors = errorsByProvider[providerType];
                const message = messagesByProvider[providerType];
                const suggestedModels = catalogModels(providerCatalogQuery.data, providerType);
                const defaultModelPlaceholder = suggestedModels[0] ?? "";
                const allowlistPlaceholder = suggestedModels.join("\n");
                const configured = configLooksConfigured(providerType, config);
                const isBusy =
                  (saveMut.isPending && saveMut.variables?.providerType === providerType) ||
                  (testMut.isPending && testMut.variables?.providerType === providerType) ||
                  (setDefaultMut.isPending && setDefaultMut.variables?.providerType === providerType) ||
                  (deleteMut.isPending && deleteMut.variables?.providerType === providerType);

                return (
                  <Card key={providerType} data-testid={`provider-card-${providerType}`}>
                    <CardHeader className="p-4">
                      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                        <div className="space-y-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <CardTitle className="text-base">{descriptor.title}</CardTitle>
                            <Badge variant="secondary">{configured ? "Configured" : "Not configured"}</Badge>
                            {config?.is_enabled ? <Badge variant="secondary">Enabled</Badge> : <Badge>Disabled</Badge>}
                            {config?.is_default ? <Badge>Default provider</Badge> : null}
                          </div>
                          <CardDescription>{descriptor.summary}</CardDescription>
                          <div className="text-sm text-slate-600">{descriptor.help}</div>
                          {config ? (
                            <div className="text-xs text-slate-500">
                              Last updated {formatDateTime(config.updated_at)}.
                            </div>
                          ) : (
                            <div className="text-xs text-slate-500">This provider has not been connected for the organization yet.</div>
                          )}
                        </div>
                        <div className="rounded border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700">
                          {configured ? "Stored credentials remain hidden after save." : "No stored secret yet."}
                        </div>
                      </div>
                    </CardHeader>

                    <CardContent className="space-y-4 p-4 pt-0">
                      <MessageBanner message={message} providerType={providerType} />

                      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                        <div className="space-y-1">
                          <div className="text-xs text-slate-600">Connection name</div>
                          <Input
                            value={form.display_name}
                            onChange={(e) => updateForm(providerType, { display_name: e.target.value })}
                            placeholder={descriptor.title}
                            data-testid={`provider-display-name-${providerType}`}
                          />
                          <FieldError error={errors.display_name} />
                        </div>
                        <div className="rounded border border-slate-200 bg-slate-50 p-3 text-sm">
                          <label className="flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={form.is_enabled}
                              onChange={(e) => updateForm(providerType, { is_enabled: e.target.checked })}
                            />
                            <span>Enable this provider for organization traffic</span>
                          </label>
                        </div>
                      </div>

                      {providerType === "openai" || providerType === "anthropic" ? (
                        <>
                          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                            <div className="space-y-1">
                              <div className="text-xs text-slate-600">API key</div>
                              <Input
                                type="password"
                                value={form.api_key}
                                onChange={(e) => updateForm(providerType, { api_key: e.target.value })}
                                placeholder={config?.secret_configured ? "Leave blank to keep the current key" : "Paste API key"}
                                data-testid={`provider-api-key-${providerType}`}
                              />
                              <div className="text-xs text-slate-500">
                                {config?.secret_configured ? "A key is already stored securely. Leave this blank to keep it." : `${appConfig.product.name} stores the key securely after save.`}
                              </div>
                              <FieldError error={errors.api_key} />
                            </div>
                            <div className="space-y-1">
                              <div className="text-xs text-slate-600">Custom base URL (optional)</div>
                              <Input
                                value={form.base_url}
                                onChange={(e) => updateForm(providerType, { base_url: e.target.value })}
                                placeholder={providerType === "openai" ? "https://api.openai.com/v1" : "https://api.anthropic.com"}
                                data-testid={`provider-base-url-${providerType}`}
                              />
                            </div>
                          </div>

                          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                            <div className="space-y-1">
                              <div className="text-xs text-slate-600">{descriptor.defaultModelLabel}</div>
                              <Input
                                value={form.default_model}
                                onChange={(e) => updateForm(providerType, { default_model: e.target.value })}
                                placeholder={defaultModelPlaceholder}
                                data-testid={`provider-default-model-${providerType}`}
                              />
                              <FieldError error={errors.default_model} />
                            </div>
                            <div className="space-y-1">
                              <div className="text-xs text-slate-600">Approved models</div>
                              <Textarea
                                rows={4}
                                value={form.model_allowlist_text}
                                onChange={(e) => updateForm(providerType, { model_allowlist_text: e.target.value })}
                                placeholder={allowlistPlaceholder}
                                data-testid={`provider-allowlist-${providerType}`}
                              />
                              <div className="text-xs text-slate-500">One model per line. Requests outside this list will be blocked.</div>
                            </div>
                          </div>
                        </>
                      ) : (
                        <>
                          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                            <div className="space-y-1">
                              <div className="text-xs text-slate-600">Azure endpoint</div>
                              <Input
                                value={form.endpoint}
                                onChange={(e) => updateForm(providerType, { endpoint: e.target.value })}
                                placeholder="https://your-resource.openai.azure.com/"
                                data-testid={`provider-endpoint-${providerType}`}
                              />
                              <FieldError error={errors.endpoint} />
                            </div>
                            <div className="space-y-1">
                              <div className="text-xs text-slate-600">API version</div>
                              <Input
                                value={form.api_version}
                                onChange={(e) => updateForm(providerType, { api_version: e.target.value })}
                                placeholder="2024-10-21"
                                data-testid={`provider-api-version-${providerType}`}
                              />
                              <FieldError error={errors.api_version} />
                            </div>
                          </div>

                          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                            <div className="space-y-1">
                              <div className="text-xs text-slate-600">Authentication</div>
                              <Select
                                value={form.auth_mode}
                                onValueChange={(value) =>
                                  updateForm(providerType, { auth_mode: value as "api_key" | "managed_identity", clear_secret: false })
                                }
                              >
                                <SelectTrigger>
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="api_key">API key</SelectItem>
                                  <SelectItem value="managed_identity">Managed identity</SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                            <div className="space-y-1">
                              <div className="text-xs text-slate-600">{descriptor.defaultModelLabel}</div>
                              <Input
                                value={form.default_deployment}
                                onChange={(e) => updateForm(providerType, { default_deployment: e.target.value })}
                                placeholder={defaultModelPlaceholder}
                                data-testid={`provider-default-deployment-${providerType}`}
                              />
                              <FieldError error={errors.default_deployment} />
                            </div>
                          </div>

                          {form.auth_mode === "api_key" ? (
                            <div className="space-y-1">
                              <div className="text-xs text-slate-600">Azure API key</div>
                              <Input
                                type="password"
                                value={form.api_key}
                                onChange={(e) => updateForm(providerType, { api_key: e.target.value })}
                                placeholder={config?.secret_configured ? "Leave blank to keep the current key" : "Paste API key"}
                                data-testid={`provider-api-key-${providerType}`}
                              />
                              <div className="text-xs text-slate-500">
                                {config?.secret_configured ? "A key is already stored securely. Leave this blank to keep it." : `${appConfig.product.name} stores the key securely after save.`}
                              </div>
                              <FieldError error={errors.api_key} />
                            </div>
                          ) : (
                            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                              <div className="space-y-1">
                                <div className="text-xs text-slate-600">Managed identity client ID (optional)</div>
                                <Input
                                  value={form.managed_identity_client_id}
                                  onChange={(e) => updateForm(providerType, { managed_identity_client_id: e.target.value })}
                                  placeholder="GUID"
                                  data-testid={`provider-managed-identity-client-id-${providerType}`}
                                />
                              </div>
                              <div className="rounded border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                                <div>Managed identity mode does not require an API key.</div>
                                {config?.secret_configured ? (
                                  <label className="mt-2 flex items-center gap-2">
                                    <input
                                      type="checkbox"
                                      checked={form.clear_secret}
                                      onChange={(e) => updateForm(providerType, { clear_secret: e.target.checked })}
                                    />
                                    <span>Remove the stored Azure API key on save</span>
                                  </label>
                                ) : null}
                              </div>
                            </div>
                          )}

                          <div className="space-y-1">
                            <div className="text-xs text-slate-600">Approved deployments</div>
                            <Textarea
                              rows={4}
                              value={form.model_allowlist_text}
                              onChange={(e) => updateForm(providerType, { model_allowlist_text: e.target.value })}
                              placeholder={allowlistPlaceholder}
                              data-testid={`provider-allowlist-${providerType}`}
                            />
                            <div className="text-xs text-slate-500">One deployment per line. Requests outside this list will be blocked.</div>
                          </div>
                        </>
                      )}

                      <div className="rounded border border-slate-200 bg-slate-50 p-4">
                        <div className="space-y-1">
                          <div className="text-sm font-medium text-slate-900">Resilience</div>
                          <div className="text-sm text-slate-600">
                            Configure how long {appConfig.product.name} should wait, whether to retry transient failures, and whether this {organizationLabel} explicitly allows a fallback provider or model.
                          </div>
                        </div>

                        <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
                          <div className="space-y-1">
                            <div className="text-xs text-slate-600">Connect timeout (seconds)</div>
                            <Input
                              value={form.connect_timeout_seconds}
                              onChange={(e) => updateForm(providerType, { connect_timeout_seconds: e.target.value })}
                              inputMode="decimal"
                              data-testid={`provider-connect-timeout-${providerType}`}
                            />
                            <FieldError error={errors.connect_timeout_seconds} />
                          </div>
                          <div className="space-y-1">
                            <div className="text-xs text-slate-600">Read timeout (seconds)</div>
                            <Input
                              value={form.read_timeout_seconds}
                              onChange={(e) => updateForm(providerType, { read_timeout_seconds: e.target.value })}
                              inputMode="decimal"
                              data-testid={`provider-read-timeout-${providerType}`}
                            />
                            <FieldError error={errors.read_timeout_seconds} />
                          </div>
                          <div className="space-y-1">
                            <div className="text-xs text-slate-600">Retry count</div>
                            <Input
                              value={form.retry_count}
                              onChange={(e) => updateForm(providerType, { retry_count: e.target.value })}
                              inputMode="numeric"
                              data-testid={`provider-retry-count-${providerType}`}
                            />
                            <div className="text-xs text-slate-500">Use a low value to avoid long delays.</div>
                            <FieldError error={errors.retry_count} />
                          </div>
                        </div>

                        <div className="mt-4 rounded border border-slate-200 bg-white p-3">
                          <label className="flex items-center gap-2 text-sm">
                            <input
                              type="checkbox"
                              checked={form.fallback_enabled}
                              onChange={(e) =>
                                updateForm(providerType, {
                                  fallback_enabled: e.target.checked,
                                  fallback_provider: e.target.checked ? form.fallback_provider : "",
                                  fallback_model: e.target.checked ? form.fallback_model : "",
                                })
                              }
                            />
                            <span>Allow fallback if this provider is unavailable</span>
                          </label>
                          <div className="mt-2 text-xs text-slate-500">
                            {appConfig.product.name} will never switch providers unless this setting is enabled and the fallback target is explicitly approved for the {organizationLabel}.
                          </div>

                          {form.fallback_enabled ? (
                            <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
                              <div className="space-y-1">
                                <div className="text-xs text-slate-600">Fallback provider</div>
                                <Select
                                  value={form.fallback_provider || "__none__"}
                                  onValueChange={(value) =>
                                    updateForm(providerType, {
                                      fallback_provider: value === "__none__" ? "" : (value as ProviderType),
                                    })
                                  }
                                >
                                  <SelectTrigger>
                                    <SelectValue />
                                  </SelectTrigger>
                                  <SelectContent>
                                    <SelectItem value="__none__">Select provider</SelectItem>
                                    {PROVIDER_ORDER.map((candidate) => (
                                      <SelectItem key={candidate} value={candidate}>
                                        {PROVIDER_DETAILS[candidate].title}
                                      </SelectItem>
                                    ))}
                                  </SelectContent>
                                </Select>
                                <FieldError error={errors.fallback_provider} />
                              </div>
                              <div className="space-y-1">
                                <div className="text-xs text-slate-600">
                                  Fallback {providerType === "azure_openai" ? "deployment" : "model"}
                                </div>
                                <Input
                                  value={form.fallback_model}
                                  onChange={(e) => updateForm(providerType, { fallback_model: e.target.value })}
                                  placeholder={catalogModels(providerCatalogQuery.data, form.fallback_provider || providerType)[0] ?? defaultModelPlaceholder}
                                  data-testid={`provider-fallback-model-${providerType}`}
                                />
                                <FieldError error={errors.fallback_model} />
                              </div>
                            </div>
                          ) : null}
                        </div>
                      </div>

                      {config && !config.is_default && form.is_enabled ? (
                        <div className="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                          Setting this as the default provider will redirect new requests here unless an application explicitly selects another approved provider.
                        </div>
                      ) : null}

                      {form.fallback_enabled && form.fallback_provider && form.fallback_provider !== providerType ? (
                        <div className="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                          Fallback may route traffic to {PROVIDER_DETAILS[form.fallback_provider].title} instead of {descriptor.title}. Confirm this matches your organization’s confidentiality and vendor-approval requirements.
                        </div>
                      ) : null}

                      <div className="flex flex-wrap gap-2">
                        <Button
                          disabled={isBusy}
                          onClick={() => saveProvider(providerType, false)}
                          data-testid={`provider-save-${providerType}`}
                        >
                          {saveMut.isPending && saveMut.variables?.providerType === providerType && !saveMut.variables?.saveAndTest
                            ? "Saving…"
                            : "Save"}
                        </Button>
                        <Button
                          variant="outline"
                          disabled={isBusy}
                          onClick={() => saveProvider(providerType, true)}
                          data-testid={`provider-save-test-${providerType}`}
                        >
                          {saveMut.isPending && saveMut.variables?.providerType === providerType && saveMut.variables?.saveAndTest
                            ? "Saving…"
                            : "Save and Test"}
                        </Button>
                        {config ? (
                          <>
                            <Button
                              variant="outline"
                              disabled={isBusy}
                              onClick={() => testMut.mutate({ providerType, id: config.id })}
                              data-testid={`provider-test-${providerType}`}
                            >
                              {testMut.isPending && testMut.variables?.providerType === providerType ? "Testing…" : "Test Connection"}
                            </Button>
                            {!config.is_default ? (
                              <Button
                                variant="outline"
                                disabled={isBusy || !form.is_enabled}
                                onClick={() => setDefault(providerType)}
                                data-testid={`provider-default-${providerType}`}
                              >
                                {setDefaultMut.isPending && setDefaultMut.variables?.providerType === providerType ? "Updating…" : "Set as Default"}
                              </Button>
                            ) : null}
                            <Button
                              variant="destructive"
                              disabled={isBusy}
                              onClick={() => {
                                if (!window.confirm(`Remove the ${descriptor.title} connection for this ${organizationLabel}?`)) return;
                                deleteMut.mutate({ providerType, id: config.id });
                              }}
                            >
                              Remove Connection
                            </Button>
                          </>
                        ) : null}
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </RequireTenantScope>
      </RequireRole>
    </main>
  );
}
