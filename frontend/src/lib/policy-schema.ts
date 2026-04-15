import { z } from "zod";

export const PolicySchema = z.object({
  allowed_models: z.array(z.string()).min(1),
  max_tokens_per_request: z.number().int().min(1).max(8192),
  max_prompt_chars: z.number().int().min(1).max(200000).optional(),
  rate_limits: z
    .object({
      tenant_per_minute: z.number().int().min(1).max(100000).optional(),
      api_key_per_minute: z.number().int().min(1).max(100000).optional(),
    })
    .optional(),
  block_prompt_patterns: z.array(z.string()).optional(),
  require_system_prompt_prefix: z.string().optional(),
  metadata_requirements: z
    .object({
      data_classification: z.array(z.string()).min(1).optional(),
    })
    .optional(),
  output_validation_rules: z
    .array(
      z.object({
        type: z.enum(["regex", "json_schema"]),
        pattern: z.string().optional(),
        schema: z.record(z.any()).optional(),
        action: z.enum(["flag", "block"]).optional(),
        reason: z.string().optional(),
      }),
    )
    .optional(),
  logging: z
    .object({
      store_redacted_snippets: z.boolean().optional(),
      store_raw_content: z.boolean().optional(),
    })
    .optional(),
  security: z
    .object({
      prompt_injection_action: z.enum(["flag", "block_high", "block_med"]).optional(),
    })
    .optional(),
  phi: z
    .object({
      enabled: z.boolean().optional(),
      threshold_score: z.number().int().min(0).max(100).optional(),
      action: z.enum(["flag", "block"]).optional(),
      flag_on_any_match: z.boolean().optional(),
    })
    .optional(),
  legal: z
    .object({
      system_prompt_prefix_base: z.string().optional(),
      allow_document_content: z.boolean().optional(),
      employment_bias_guard: z.boolean().optional(),
    })
    .optional(),
  assistant_profile: z
    .object({
      system_prompt_prefix_base: z.string().optional(),
      allow_document_content: z.boolean().optional(),
      employment_bias_guard: z.boolean().optional(),
    })
    .optional(),
});

export type TenantPolicyConfig = z.infer<typeof PolicySchema>;
