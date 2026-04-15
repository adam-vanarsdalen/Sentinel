export type RolePresentation = {
  label: string;
  description: string;
};

export type AppConfig = {
  preset_id: string;
  available_presets: Array<{
    id: string;
    name: string;
    industry: string;
    product_name: string;
  }>;
  manifest: {
    id: string;
    name: string;
    industry: string;
    product_name: string;
    console_name: string;
    default_policy_template_id: string;
    support_email?: string | null;
    demo?: Record<string, unknown>;
  };
  product: {
    name: string;
    console_name: string;
    support_email?: string | null;
  };
  terminology: {
    organization_singular: string;
    organization_plural: string;
    organization_context: string;
    rules_label: string;
    report_label: string;
    activity_log_label: string;
    workflow: {
      primary_entity_label: string;
      secondary_entity_label: string;
      external_party_label: string;
    };
    messages: {
      blocked_by_rules: string;
      organization_context_required: string;
    };
  };
  copy: {
    landing_eyebrow: string;
    landing_title: string;
    landing_description: string;
    landing_highlights: string[];
    login_description: string;
    trial_title: string;
    trial_description: string;
  };
  roles: Record<string, RolePresentation>;
  risk_taxonomy: {
    shared_categories: Array<{ id: string; label: string; description: string }>;
    preset_categories: Array<{ id: string; label: string; description: string }>;
  };
};

export const DEFAULT_APP_CONFIG: AppConfig = {
  preset_id: "general",
  available_presets: [{ id: "general", name: "General", industry: "general", product_name: "Sentinel" }],
  manifest: {
    id: "general",
    name: "General",
    industry: "general",
    product_name: "Sentinel",
    console_name: "Sentinel Console",
    default_policy_template_id: "general_default_policy_v1",
    support_email: "support@sentinel.local",
  },
  product: {
    name: "Sentinel",
    console_name: "Sentinel Console",
    support_email: "support@sentinel.local",
  },
  terminology: {
    organization_singular: "Organization",
    organization_plural: "Organizations",
    organization_context: "organization",
    rules_label: "Organization AI Rules",
    report_label: "Audit Report",
    activity_log_label: "AI Activity Log",
    workflow: {
      primary_entity_label: "Work Item",
      secondary_entity_label: "Workstream",
      external_party_label: "Customer",
    },
    messages: {
      blocked_by_rules: "Blocked by AI Rules.",
      organization_context_required: "Organization context is required.",
    },
  },
  copy: {
    landing_eyebrow: "Sentinel",
    landing_title: "AI governance between your users and model providers",
    landing_description: "Sentinel is an AI governance layer that sits between users and model providers, enforces organizational rules, flags risky usage, and creates an audit trail.",
    landing_highlights: [
      "Enforce organization AI rules across tools and teams before requests reach a model.",
      "Monitor confidential data exposure, policy violations, and prompt manipulation signals.",
      "Maintain an exportable audit trail for every AI interaction.",
    ],
    login_description: "Sentinel admin console",
    trial_title: "Request a Demo",
    trial_description: "Send your details and we will follow up to set up a demo workspace.",
  },
  roles: {
    super_admin: { label: "Platform Admin", description: "Manages the full Sentinel platform across organizations." },
    org_admin: { label: "Org Admin", description: "Full administrative control within one organization." },
    compliance_admin: { label: "Compliance Admin", description: "Manages governance rules, alerts, and oversight settings." },
    operator: { label: "Operator", description: "Manages integrations, API keys, and operational testing." },
    reviewer: { label: "Reviewer", description: "Views dashboards and activity relevant to daily oversight." },
    auditor: { label: "Auditor", description: "Reviews logs, reports, and audit evidence." },
  },
  risk_taxonomy: {
    shared_categories: [],
    preset_categories: [],
  },
};
