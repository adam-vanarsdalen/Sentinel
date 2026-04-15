import { z } from "zod";

function canonicalRole(value: unknown) {
  const raw = typeof value === "string" ? value.trim().toLowerCase() : value;
  if (raw === "tenant_admin") return "org_admin";
  if (raw === "developer") return "operator";
  if (raw === "viewer") return "reviewer";
  return raw;
}

export const RoleSchema = z.preprocess(
  canonicalRole,
  z.enum(["super_admin", "org_admin", "compliance_admin", "operator", "reviewer", "auditor"]),
);
export type Role = z.infer<typeof RoleSchema>;

export const TokenResponseSchema = z.object({
  access_token: z.string().min(10),
  token_type: z.string().optional(),
});
export type TokenResponse = z.infer<typeof TokenResponseSchema>;

export const MeSchema = z.object({
  id: z.string(),
  // Validated on write; keep response tolerant of legacy/demo data.
  email: z.string(),
  role: RoleSchema,
  tenant_id: z.string().nullable(),
});
export type Me = z.infer<typeof MeSchema>;

export const TenantSchema = z.object({
  id: z.string(),
  name: z.string(),
  slug: z.string().optional(),
  status: z.string().optional(),
  created_at: z.string(),
  updated_at: z.string().optional(),
  preset_id: z.string().nullable().optional(),
  demo_profile: z.string().nullable().optional(),
  demo_summary: z.string().nullable().optional(),
  is_demo: z.boolean().optional(),
});
export type Tenant = z.infer<typeof TenantSchema>;

export const ApiKeySchema = z.object({
  id: z.string(),
  name: z.string(),
  key_prefix: z.string(),
  is_active: z.boolean(),
  created_at: z.string(),
  revoked_at: z.string().nullable(),
  last_used_at: z.string().nullable().optional(),
});
export type ApiKey = z.infer<typeof ApiKeySchema>;

export const ApiKeyCreateResponseSchema = z.object({
  api_key: ApiKeySchema,
  token: z.string(),
});
export type ApiKeyCreateResponse = z.infer<typeof ApiKeyCreateResponseSchema>;

export const ProviderTypeSchema = z.enum(["openai", "anthropic", "azure_openai", "ollama"]);
export type ProviderType = z.infer<typeof ProviderTypeSchema>;

export const ProviderConfigSchema = z.object({
  id: z.string(),
  tenant_id: z.string(),
  provider_type: ProviderTypeSchema,
  display_name: z.string(),
  is_enabled: z.boolean(),
  is_default: z.boolean(),
  model_allowlist: z.array(z.string()).default([]),
  config_json: z.record(z.any()).default({}),
  secret_configured: z.boolean(),
  secret_status: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
});
export type ProviderConfig = z.infer<typeof ProviderConfigSchema>;

export const ProviderPolicyProviderSchema = z.object({
  provider_type: ProviderTypeSchema,
  provider_config_id: z.string().nullable(),
  display_name: z.string().nullable(),
  is_configured: z.boolean(),
  secret_configured: z.boolean(),
  is_enabled: z.boolean(),
  is_default: z.boolean(),
  allowed_models: z.array(z.string()).default([]),
  default_model: z.string().nullable(),
});
export type ProviderPolicyProvider = z.infer<typeof ProviderPolicyProviderSchema>;

export const ProviderPolicySchema = z.object({
  tenant_id: z.string(),
  default_provider: ProviderTypeSchema.nullable(),
  providers: z.array(ProviderPolicyProviderSchema),
  warnings: z.array(z.string()).default([]),
});
export type ProviderPolicy = z.infer<typeof ProviderPolicySchema>;

export const ProviderCatalogModelSchema = z.object({
  id: z.string(),
  display_name: z.string(),
  status: z.string(),
  aliases: z.array(z.string()).default([]),
  capabilities: z.array(z.string()).default([]),
});
export type ProviderCatalogModel = z.infer<typeof ProviderCatalogModelSchema>;

export const ProviderCatalogItemSchema = z.object({
  id: ProviderTypeSchema,
  display_name: z.string(),
  default_model_field: z.string().nullable(),
  supports_custom_models: z.boolean(),
  enabled_by_default: z.boolean(),
  notes: z.string().nullable().optional(),
  models: z.array(ProviderCatalogModelSchema),
});
export type ProviderCatalogItem = z.infer<typeof ProviderCatalogItemSchema>;

export const ProviderCatalogSchema = z.object({
  providers: z.array(ProviderCatalogItemSchema),
});
export type ProviderCatalog = z.infer<typeof ProviderCatalogSchema>;

export const PolicyResponseSchema = z.object({
  tenant_id: z.string(),
  policy_json: z.record(z.any()),
  updated_at: z.string(),
  updated_by_user_id: z.string().nullable(),
  active_version_id: z.string().nullable().optional(),
});
export type PolicyResponse = z.infer<typeof PolicyResponseSchema>;

export const PolicyVersionSchema = z.object({
  id: z.string(),
  tenant_id: z.string(),
  created_at: z.string(),
  created_by_user_id: z.string().nullable(),
  created_by_email: z.string().nullable().optional(),
  change_note: z.string().nullable().optional(),
  summary: z.string(),
  active: z.boolean(),
  source_template_id: z.string().nullable().optional(),
  source_version_id: z.string().nullable().optional(),
  policy_json: z.record(z.any()),
});
export type PolicyVersion = z.infer<typeof PolicyVersionSchema>;

export const AuditEventSchema = z.object({
  id: z.string(),
  tenant_id: z.string(),
  api_key_id: z.string().nullable().optional(),
  api_key_name: z.string().nullable().optional(),
  user_id: z.string().nullable().optional(),
  user_email: z.string().nullable().optional(),
  user_role: z.preprocess((v) => (v == null ? null : canonicalRole(v)), RoleSchema.nullable()).optional(),
  matter_id: z.string().nullable().optional(),
  practice_group: z.string().nullable().optional(),
  client_name: z.string().nullable().optional(),
  actor: z
    .object({
      type: z.enum(["user", "api_key", "system"]),
      user_id: z.string().optional(),
      email: z.string().optional(),
      role: RoleSchema.optional(),
      api_key_id: z.string().optional(),
      name: z.string().optional(),
    })
    .optional(),
  request_id: z.string().nullable().optional(),
  timestamp: z.string(),
  action_type: z.string(),
  outcome: z.string(),
  reason: z.string().nullable().optional(),
  provider: z.string().nullable().optional(),
  model: z.string().nullable().optional(),
  prompt_hash: z.string().nullable().optional(),
  response_hash: z.string().nullable().optional(),
  redacted_prompt: z.string().nullable().optional(),
  redacted_response: z.string().nullable().optional(),
  phi_score: z.number().int().nullable().optional(),
  confidentiality_exposure_level: z.enum(["LOW", "MEDIUM", "HIGH"]).nullable().optional(),
  risk_flags: z.preprocess((v) => v ?? [], z.array(z.string())) as z.ZodType<string[]>,
  severity: z.string().nullable().optional(),
  tokens_prompt: z.number().int().nullable().optional(),
  tokens_completion: z.number().int().nullable().optional(),
  cost_usd: z.number().nullable().optional(),
  event_data: z.preprocess((v) => v ?? {}, z.record(z.any())) as z.ZodType<Record<string, any>>,
});
export type AuditEvent = z.infer<typeof AuditEventSchema>;

export const EvalRunSchema = z.object({
  id: z.string(),
  tenant_id: z.string(),
  provider: z.string(),
  model: z.string(),
  status: z.string(),
  started_at: z.string(),
  finished_at: z.string().nullable(),
  summary: z.preprocess((v) => v ?? {}, z.record(z.any())) as z.ZodType<Record<string, any>>,
});
export type EvalRun = z.infer<typeof EvalRunSchema>;

export const EvalSuiteCaseSchema = z.object({
  id: z.string(),
  name: z.string(),
  category: z.string(),
  input_messages: z.array(z.record(z.any())),
  expected_flags: z.array(z.string()).default([]),
  created_at: z.string(),
});
export type EvalSuiteCase = z.infer<typeof EvalSuiteCaseSchema>;

export const EvalRunDetailSchema = z.object({
  run: EvalRunSchema,
  results: z.array(
    z.object({
      id: z.string(),
      test_case_id: z.string(),
      passed: z.boolean(),
      observed_flags: z.array(z.string()).default([]),
      phi_score: z.number().int().nullable().optional(),
      risk_severity: z.string().nullable().optional(),
      details: z.record(z.any()).default({}),
    }),
  ),
});
export type EvalRunDetail = z.infer<typeof EvalRunDetailSchema>;

export const SettingsSchema = z.object({
  tenant_id: z.string(),
  settings_json: z.record(z.any()),
  updated_at: z.string(),
  updated_by_user_id: z.string().nullable(),
});
export type TenantSettings = z.infer<typeof SettingsSchema>;

export const AlertTriggersSchema = z.object({
  high_confidentiality_exposure: z.boolean(),
  prompt_injection_detected: z.boolean(),
  policy_blocked: z.boolean(),
  repeated_provider_failures: z.boolean(),
  blocked_request_spike: z.boolean(),
});
export type AlertTriggers = z.infer<typeof AlertTriggersSchema>;

export const AlertSettingsDataSchema = z.object({
  phi_threshold: z.number().int(),
  severity_threshold: z.enum(["low", "med", "high"]),
  email_recipients: z.array(z.string()).default([]),
  webhook_format: z.enum(["generic", "slack", "teams"]).default("generic"),
  webhook_configured: z.boolean(),
  webhook_status: z.string(),
  webhook_destination_hint: z.string().nullable().optional(),
  triggers: AlertTriggersSchema,
  throttle_window_minutes: z.number().int(),
  provider_failure_threshold: z.number().int(),
});
export type AlertSettingsData = z.infer<typeof AlertSettingsDataSchema>;

export const AlertSettingsSchema = z.object({
  tenant_id: z.string(),
  alerts: AlertSettingsDataSchema,
  updated_at: z.string(),
  updated_by_user_id: z.string().nullable(),
});
export type AlertSettings = z.infer<typeof AlertSettingsSchema>;

export const AlertHistoryItemSchema = z.object({
  id: z.string(),
  timestamp: z.string(),
  status: z.enum(["sent", "failed"]),
  trigger_type: z.string().nullable().optional(),
  severity: z.string().nullable().optional(),
  channel: z.string().nullable().optional(),
  destination: z.string().nullable().optional(),
  request_id: z.string().nullable().optional(),
  reason: z.string().nullable().optional(),
});
export type AlertHistoryItem = z.infer<typeof AlertHistoryItemSchema>;

export const AlertTestResponseSchema = z.object({
  ok: z.boolean(),
  results: z.array(
    z.object({
      channel: z.string(),
      destination: z.string(),
      status: z.enum(["sent", "failed"]),
      error: z.string().optional(),
    }),
  ),
});
export type AlertTestResponse = z.infer<typeof AlertTestResponseSchema>;

export const UserListItemSchema = z.object({
  id: z.string(),
  // Validated on write; keep response tolerant of legacy/demo data.
  email: z.string(),
  role: RoleSchema,
  tenant_id: z.string().nullable(),
  is_active: z.boolean(),
  created_at: z.string(),
});
export type UserListItem = z.infer<typeof UserListItemSchema>;

export const CreateUserResponseSchema = z.object({
  user: UserListItemSchema,
  temp_password: z.string(),
});
export type CreateUserResponse = z.infer<typeof CreateUserResponseSchema>;

export const AuditSearchResponseSchema = z.object({
  items: z.array(AuditEventSchema),
  total: z.number().int(),
  limit: z.number().int(),
  offset: z.number().int(),
});
export type AuditSearchResponse = z.infer<typeof AuditSearchResponseSchema>;

export const MetricsOverviewSchema = z.object({
  range: z.string(),
  start: z.string(),
  end: z.string(),
  cards: z.object({
    total_requests: z.number().int(),
    policy_blocks: z.number().int(),
    phi_flagged: z.number().int(),
    avg_phi_score: z.number(),
    estimated_cost_usd: z.number(),
  }),
  top_api_keys: z.array(z.object({ api_key_id: z.string().nullable(), count: z.number().int() })),
  flags_counts: z.record(z.number().int()),
  severity_counts: z.record(z.number().int()),
  requests_over_time: z.array(z.object({ t: z.string(), value: z.number().int() })),
  cost_over_time: z.array(z.object({ t: z.string(), value: z.number() })),
});
export type MetricsOverview = z.infer<typeof MetricsOverviewSchema>;

export const CostSummarySchema = z.object({
  as_of: z.string(),
  today: z.object({ start: z.string(), total_usd: z.number() }),
  this_week: z.object({ start: z.string(), total_usd: z.number() }),
  this_month: z.object({ start: z.string(), total_usd: z.number() }),
  by_model_this_month: z.array(z.object({ model: z.string(), total_usd: z.number(), requests: z.number().int() })),
});
export type CostSummary = z.infer<typeof CostSummarySchema>;

export const RiskSummarySchema = z.object({
  range: z.string(),
  start: z.string(),
  end: z.string(),
  total_ai_requests: z.number().int(),
  injection_attempts_flagged: z.number().int(),
  blocked_requests: z.number().int(),
  high_confidentiality_exposure: z.number().int(),
  top_matters: z.array(z.object({ matter_id: z.string().nullable(), count: z.number().int() })).default([]),
});
export type RiskSummary = z.infer<typeof RiskSummarySchema>;
