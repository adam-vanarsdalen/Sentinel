import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { loadAppConfig } from "@/lib/app-config-server";

export async function generateMetadata() {
  const appConfig = await loadAppConfig();
  return {
    title: `Help — ${appConfig.product.name}`,
  };
}

export default async function HelpPage() {
  const appConfig = await loadAppConfig();
  const productName = appConfig.product.name;
  const supportEmail = appConfig.product.support_email || process.env.SUPPORT_EMAIL || "support@sentinel.local";
  const orgLabel = appConfig.terminology.organization_singular;
  const orgLabelPlural = appConfig.terminology.organization_plural;
  const rulesLabel = appConfig.terminology.rules_label;
  const activityLogLabel = appConfig.terminology.activity_log_label;
  const primaryEntityLabel = appConfig.terminology.workflow.primary_entity_label;
  const secondaryEntityLabel = appConfig.terminology.workflow.secondary_entity_label;
  const externalPartyLabel = appConfig.terminology.workflow.external_party_label;

  const terms: Array<{ term: string; definition: string }> = [
    { term: orgLabel, definition: `A tenant (${orgLabel.toLowerCase()}) in ${productName}. Each ${orgLabel.toLowerCase()}'s data and settings are isolated.` },
    { term: "API key", definition: `A secret token used by your application or workflow tool to send requests through ${productName}.` },
    { term: activityLogLabel, definition: "A searchable record of AI requests, outcomes, risk signals, and policy blocks." },
    { term: "Confidentiality Exposure Level", definition: `A Low/Medium/High indicator for how likely text includes sensitive data such as PII or ${primaryEntityLabel.toLowerCase()} identifiers.` },
    { term: rulesLabel, definition: `Your ${orgLabel.toLowerCase()}'s policy JSON: allowed models, limits, injection blocks, and output validation.` },
    { term: "Safety & Consistency Tests", definition: "Seeded test cases you can run to spot regressions and validate rule behavior over time." },
    { term: primaryEntityLabel, definition: `An optional identifier used to group audit activity around a specific workflow item.` },
    { term: secondaryEntityLabel, definition: `An optional grouping label used to cluster related ${primaryEntityLabel.toLowerCase()}s.` },
    { term: externalPartyLabel, definition: "An optional external stakeholder or counterpart name attached to the request context." },
  ];

  const roles: Array<{ role: string; summary: string; can: string[]; cannot: string[] }> = [
    {
      role: appConfig.roles.org_admin?.label ?? "Org Admin",
      summary: appConfig.roles.org_admin?.description ?? `Full administrative control within a single ${orgLabel.toLowerCase()}.`,
      can: ["Manage API keys", `Manage ${rulesLabel}`, "Manage users and roles", "Update organization settings", `View and export ${activityLogLabel}`],
      cannot: [`Manage other ${orgLabelPlural.toLowerCase()}`],
    },
    {
      role: appConfig.roles.compliance_admin?.label ?? "Compliance Admin",
      summary: appConfig.roles.compliance_admin?.description ?? "Governance role focused on review and defensibility.",
      can: [`View and export ${activityLogLabel}`, "View dashboards and metrics", "Update governance settings"],
      cannot: ["Manage platform-wide settings"],
    },
    {
      role: appConfig.roles.operator?.label ?? "Operator",
      summary: appConfig.roles.operator?.description ?? "Operational role for integrations and testing.",
      can: ["Create and revoke API keys", "Run Safety & Consistency Tests", "View logs and metrics"],
      cannot: ["Manage users and roles", "Change governance settings"],
    },
    {
      role: appConfig.roles.reviewer?.label ?? "Reviewer",
      summary: appConfig.roles.reviewer?.description ?? `Basic visibility into ${orgLabel.toLowerCase()} activity.`,
      can: ["View dashboards", `View ${activityLogLabel}`],
      cannot: ["Export data", "Change configuration"],
    },
    {
      role: appConfig.roles.auditor?.label ?? "Auditor",
      summary: appConfig.roles.auditor?.description ?? "Read-only access to logs and audit reports.",
      can: [`Review ${activityLogLabel}`, "Download reports and exports"],
      cannot: ["Change configuration", "Manage integrations"],
    },
  ];

  return (
    <main className="space-y-4" data-testid="help">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Help & Glossary</h1>
      </div>

      <Card>
        <CardHeader className="p-4">
          <CardTitle className="text-base">Getting started</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 p-4 pt-0 text-sm">
          <div className="space-y-1">
            <div className="font-medium text-slate-900">1. Create an API key</div>
            <div className="text-slate-700">
              Go to API Keys and create a key for each AI tool your {orgLabel.toLowerCase()} uses. Copy the token because it is only shown once.
            </div>
            <div>
              <a className="underline underline-offset-2" href="/api-keys">
                Go to API Keys →
              </a>
            </div>
          </div>

          <div className="space-y-1">
            <div className="font-medium text-slate-900">2. Point your tool at {productName}</div>
            <div className="text-slate-700">
              Replace your AI provider&apos;s base URL with your {productName} gateway URL. The gateway is OpenAI-compatible. See the API Keys page for a code example.
            </div>
          </div>

          <div className="space-y-1">
            <div className="font-medium text-slate-900">3. Watch the audit log</div>
            <div className="text-slate-700">
              Every request routed through {productName} appears in {activityLogLabel} with risk signals, policy outcomes, and a full audit trail.
            </div>
            <div>
              <a className="underline underline-offset-2" href="/logs">
                Go to {activityLogLabel} →
              </a>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="p-4">
          <CardTitle className="text-base">Contact Support</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 p-4 pt-0 text-sm">
          <div className="text-slate-700">For account access, incident review help, or questions about {rulesLabel}, contact:</div>
          <div className="font-medium">
            <a className="text-slate-900 underline underline-offset-2" href={`mailto:${supportEmail}`}>
              {supportEmail}
            </a>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="p-4">
          <CardTitle className="text-base">Common terms</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 p-4 pt-0 text-sm">
          {terms.map((t) => (
            <div key={t.term}>
              <div className="font-medium">{t.term}</div>
              <div className="text-slate-700">{t.definition}</div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="p-4">
          <CardTitle className="text-base">Roles ({orgLabel.toLowerCase()} users)</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 p-4 pt-0 text-sm">
          {roles.map((role) => (
            <div key={role.role} className="rounded-lg border border-slate-200 bg-white p-3">
              <div className="font-medium">{role.role}</div>
              <div className="mt-0.5 text-slate-700">{role.summary}</div>
              <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2">
                <div>
                  <div className="text-xs font-medium text-slate-600">Can</div>
                  <ul className="mt-1 list-disc space-y-0.5 pl-5 text-slate-700">
                    {role.can.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <div className="text-xs font-medium text-slate-600">Cannot</div>
                  <ul className="mt-1 list-disc space-y-0.5 pl-5 text-slate-700">
                    {role.cannot.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </main>
  );
}
