"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { RequireRole } from "@/components/layout/require-role";
import { RequireTenantScope } from "@/components/layout/require-tenant";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/toaster";
import { api } from "@/lib/api-client";
import { useAppConfig } from "@/lib/app-config-context";
import { formatDateTime } from "@/lib/format";
import { hasAnyRole } from "@/lib/roles";

type Severity = "low" | "med" | "high";

type TriggerState = {
  high_confidentiality_exposure: boolean;
  prompt_injection_detected: boolean;
  policy_blocked: boolean;
  repeated_provider_failures: boolean;
  blocked_request_spike: boolean;
};

const DEFAULT_TRIGGERS: TriggerState = {
  high_confidentiality_exposure: true,
  prompt_injection_detected: true,
  policy_blocked: true,
  repeated_provider_failures: true,
  blocked_request_spike: false,
};

function parseRecipients(text: string): string[] {
  return text
    .split(/[\n,;]/g)
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
}

export default function AlertsPage() {
  const appConfig = useAppConfig();
  const qc = useQueryClient();
  const toast = useToast();
  const organizationLabel = appConfig.terminology.organization_context;
  const rulesLabel = appConfig.terminology.rules_label;

  React.useEffect(() => {
    document.title = `Alerts — ${appConfig.product.name}`;
  }, [appConfig.product.name]);

  const meQuery = useQuery({ queryKey: ["me"], queryFn: () => api.auth.me() });
  const canView = hasAnyRole(meQuery.data?.role, ["org_admin", "compliance_admin"]);

  const alertsQuery = useQuery({
    queryKey: ["alerts", "current"],
    queryFn: () => api.alerts.getCurrent(),
    enabled: canView,
  });
  const historyQuery = useQuery({
    queryKey: ["alerts", "history"],
    queryFn: () => api.alerts.history(20),
    enabled: canView,
  });

  const [emailRecipientsText, setEmailRecipientsText] = React.useState("");
  const [webhookUrl, setWebhookUrl] = React.useState("");
  const [clearWebhook, setClearWebhook] = React.useState(false);
  const [webhookFormat, setWebhookFormat] = React.useState<"generic" | "slack" | "teams">("generic");
  const [severityThreshold, setSeverityThreshold] = React.useState<Severity>("med");
  const [phiThreshold, setPhiThreshold] = React.useState("80");
  const [throttleWindowMinutes, setThrottleWindowMinutes] = React.useState("30");
  const [providerFailureThreshold, setProviderFailureThreshold] = React.useState("3");
  const [triggers, setTriggers] = React.useState<TriggerState>(DEFAULT_TRIGGERS);
  const [errors, setErrors] = React.useState<Record<string, string>>({});

  React.useEffect(() => {
    const data = alertsQuery.data?.alerts;
    if (!data) return;
    setEmailRecipientsText((data.email_recipients ?? []).join("\n"));
    setWebhookUrl("");
    setClearWebhook(false);
    setWebhookFormat(data.webhook_format);
    setSeverityThreshold(data.severity_threshold);
    setPhiThreshold(String(data.phi_threshold));
    setThrottleWindowMinutes(String(data.throttle_window_minutes));
    setProviderFailureThreshold(String(data.provider_failure_threshold));
    setTriggers({
      high_confidentiality_exposure: data.triggers.high_confidentiality_exposure,
      prompt_injection_detected: data.triggers.prompt_injection_detected,
      policy_blocked: data.triggers.policy_blocked,
      repeated_provider_failures: data.triggers.repeated_provider_failures,
      blocked_request_spike: data.triggers.blocked_request_spike,
    });
    setErrors({});
  }, [alertsQuery.data]);

  function validate(): Record<string, string> {
    const nextErrors: Record<string, string> = {};
    for (const recipient of parseRecipients(emailRecipientsText)) {
      if (!recipient.includes("@")) {
        nextErrors.email_recipients = "Use one valid email address per line.";
        break;
      }
    }
    if (webhookUrl.trim()) {
      try {
        const parsed = new URL(webhookUrl.trim());
        if (!["http:", "https:"].includes(parsed.protocol)) {
          nextErrors.webhook_url = "Webhook URL must start with http:// or https://.";
        }
      } catch {
        nextErrors.webhook_url = "Enter a valid webhook URL.";
      }
    }
    const phi = Number(phiThreshold);
    if (!Number.isFinite(phi) || phi < 0 || phi > 100) {
      nextErrors.phi_threshold = "Use a confidentiality threshold from 0 to 100.";
    }
    const throttle = Number(throttleWindowMinutes);
    if (!Number.isFinite(throttle) || throttle < 1 || throttle > 1440) {
      nextErrors.throttle_window_minutes = "Use a throttle window between 1 and 1440 minutes.";
    }
    const failureThreshold = Number(providerFailureThreshold);
    if (!Number.isFinite(failureThreshold) || failureThreshold < 2 || failureThreshold > 20) {
      nextErrors.provider_failure_threshold = "Use a repeated-failure threshold between 2 and 20.";
    }
    return nextErrors;
  }

  const saveMutation = useMutation({
    mutationFn: async () => {
      const nextErrors = validate();
      setErrors(nextErrors);
      if (Object.keys(nextErrors).length > 0) {
        throw new Error("Please fix the highlighted alert settings.");
      }
      return api.alerts.updateCurrent({
        email_recipients: parseRecipients(emailRecipientsText),
        webhook_url: webhookUrl.trim() ? webhookUrl.trim() : null,
        clear_webhook: clearWebhook,
        webhook_format: webhookFormat,
        severity_threshold: severityThreshold,
        phi_threshold: Number(phiThreshold),
        triggers,
        throttle_window_minutes: Number(throttleWindowMinutes),
        provider_failure_threshold: Number(providerFailureThreshold),
      });
    },
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["alerts", "current"] }),
        qc.invalidateQueries({ queryKey: ["settings", "current"] }),
      ]);
      toast.push({ title: "Alert settings saved" });
    },
    onError: (error) => {
      toast.push({
        title: "Could not save alert settings",
        description: error instanceof Error ? error.message : "Check the highlighted fields and try again.",
      });
    },
  });

  const testMutation = useMutation({
    mutationFn: () => api.alerts.sendTest(),
    onSuccess: async (result) => {
      await qc.invalidateQueries({ queryKey: ["alerts", "history"] });
      const failed = result.results.filter((item) => item.status === "failed");
      if (failed.length > 0) {
        toast.push({
          title: "Test alert finished with delivery issues",
          description: failed.map((item) => `${item.channel}: ${item.error ?? "delivery failed"}`).join(" | "),
        });
        return;
      }
      toast.push({ title: "Test alert sent", description: "Delivery was attempted for every configured channel." });
    },
    onError: (error) => {
      toast.push({
        title: "Could not send test alert",
        description: error instanceof Error ? error.message : "Configure at least one alert channel first.",
      });
    },
  });

  const configured = alertsQuery.data?.alerts ?? null;
  const noChannelsConfigured =
    configured != null ? configured.email_recipients.length === 0 && !configured.webhook_configured : false;

  return (
    <main className="space-y-4" data-testid="alerts-settings">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Alerts</h1>
          <p className="text-sm text-slate-600">Send governance alerts by email or webhook so your team does not have to watch the dashboard continuously.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" disabled={!canView || testMutation.isPending} onClick={() => testMutation.mutate()}>
            {testMutation.isPending ? "Sending test…" : "Send Test Alert"}
          </Button>
          <Button disabled={!canView || saveMutation.isPending} onClick={() => saveMutation.mutate()}>
            {saveMutation.isPending ? "Saving…" : "Save Alerts"}
          </Button>
        </div>
      </div>

      <RequireRole allow={["org_admin", "compliance_admin"]}>
        <RequireTenantScope>
          {configured ? (
            <Card>
              <CardHeader className="p-4">
                <CardTitle className="text-base">Current Status</CardTitle>
                <CardDescription>Keep at least one delivery channel configured, or alerts will stay inside the audit trail only.</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-wrap items-center gap-2 p-4 pt-0 text-sm">
                <Badge variant="secondary">{configured.email_recipients.length} email recipient(s)</Badge>
                {configured.webhook_configured ? <Badge variant="secondary">Webhook configured</Badge> : <Badge>No webhook</Badge>}
                <Badge variant="secondary">Threshold: {configured.severity_threshold}</Badge>
                <Badge variant="secondary">Throttle: {configured.throttle_window_minutes} min</Badge>
                {configured.webhook_destination_hint ? <span className="text-slate-600">Webhook destination: {configured.webhook_destination_hint}</span> : null}
              </CardContent>
            </Card>
          ) : null}

          {noChannelsConfigured ? (
            <div className="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              No delivery channels are configured yet. Alerts will not be sent until you add at least one email recipient or webhook.
            </div>
          ) : null}

          <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
            <Card>
              <CardHeader className="p-4">
                <CardTitle className="text-base">Delivery</CardTitle>
                <CardDescription>Use email first for pilot reliability. Webhooks can forward alerts to Slack or Teams if your organization prefers chat notifications.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 p-4 pt-0">
                <div className="space-y-2">
                  <Label htmlFor="alert-email-recipients">Email recipients</Label>
                  <Textarea
                    id="alert-email-recipients"
                    value={emailRecipientsText}
                    onChange={(e) => setEmailRecipientsText(e.target.value)}
                    placeholder={"security@example.com\nops@example.com"}
                    className="min-h-[120px]"
                  />
                  <p className="text-xs text-slate-500">Enter one address per line. {appConfig.product.name} will send a separate message to each recipient.</p>
                  {errors.email_recipients ? <p className="text-xs text-red-700">{errors.email_recipients}</p> : null}
                </div>

                <div className="grid gap-4 md:grid-cols-[1fr_180px]">
                  <div className="space-y-2">
                    <Label htmlFor="alert-webhook-url">Webhook URL</Label>
                    <Input
                      id="alert-webhook-url"
                      value={webhookUrl}
                      onChange={(e) => {
                        setWebhookUrl(e.target.value);
                        if (e.target.value.trim()) setClearWebhook(false);
                      }}
                      placeholder="https://hooks.example.com/..."
                    />
                    <p className="text-xs text-slate-500">
                      Leave blank to keep the stored webhook hidden. {configured?.webhook_configured ? "Stored webhook is configured." : "No webhook stored yet."}
                    </p>
                    {errors.webhook_url ? <p className="text-xs text-red-700">{errors.webhook_url}</p> : null}
                  </div>
                  <div className="space-y-2">
                    <Label>Webhook format</Label>
                    <Select value={webhookFormat} onValueChange={(value) => setWebhookFormat(value as "generic" | "slack" | "teams")}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="generic">Generic</SelectItem>
                        <SelectItem value="slack">Slack</SelectItem>
                        <SelectItem value="teams">Teams</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <label className="flex items-center gap-2 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-slate-300"
                    checked={clearWebhook}
                    onChange={(e) => {
                      setClearWebhook(e.target.checked);
                      if (e.target.checked) setWebhookUrl("");
                    }}
                  />
                  Remove the currently stored webhook on next save
                </label>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="p-4">
                <CardTitle className="text-base">Alert Sensitivity</CardTitle>
                <CardDescription>Keep the first rollout conservative: notify on medium-and-above events, then tighten only if your team wants fewer messages.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 p-4 pt-0">
                <div className="space-y-2">
                  <Label>Severity threshold</Label>
                  <Select value={severityThreshold} onValueChange={(value) => setSeverityThreshold(value as Severity)}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="low">Low and above</SelectItem>
                      <SelectItem value="med">Medium and above</SelectItem>
                      <SelectItem value="high">High only</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="alert-phi-threshold">High confidentiality threshold</Label>
                  <Input id="alert-phi-threshold" value={phiThreshold} onChange={(e) => setPhiThreshold(e.target.value)} inputMode="numeric" />
                  {errors.phi_threshold ? <p className="text-xs text-red-700">{errors.phi_threshold}</p> : null}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="alert-throttle-window">Throttle window (minutes)</Label>
                  <Input
                    id="alert-throttle-window"
                    value={throttleWindowMinutes}
                    onChange={(e) => setThrottleWindowMinutes(e.target.value)}
                    inputMode="numeric"
                  />
                  {errors.throttle_window_minutes ? <p className="text-xs text-red-700">{errors.throttle_window_minutes}</p> : null}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="alert-provider-threshold">Repeated provider failure threshold</Label>
                  <Input
                    id="alert-provider-threshold"
                    value={providerFailureThreshold}
                    onChange={(e) => setProviderFailureThreshold(e.target.value)}
                    inputMode="numeric"
                  />
                  {errors.provider_failure_threshold ? <p className="text-xs text-red-700">{errors.provider_failure_threshold}</p> : null}
                </div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader className="p-4">
              <CardTitle className="text-base">Trigger Events</CardTitle>
              <CardDescription>Choose which governance events should generate alerts for this {organizationLabel}.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 p-4 pt-0 md:grid-cols-2">
              <label className="flex items-start gap-3 rounded border border-slate-200 p-3 text-sm">
                <input
                  type="checkbox"
                  className="mt-1 h-4 w-4 rounded border-slate-300"
                  checked={triggers.high_confidentiality_exposure}
                  onChange={(e) => setTriggers((current) => ({ ...current, high_confidentiality_exposure: e.target.checked }))}
                />
                <span>
                  <span className="block font-medium">High confidentiality exposure</span>
                  <span className="text-slate-600">Alert when a request crosses the organization’s confidentiality score threshold.</span>
                </span>
              </label>
              <label className="flex items-start gap-3 rounded border border-slate-200 p-3 text-sm">
                <input
                  type="checkbox"
                  className="mt-1 h-4 w-4 rounded border-slate-300"
                  checked={triggers.prompt_injection_detected}
                  onChange={(e) => setTriggers((current) => ({ ...current, prompt_injection_detected: e.target.checked }))}
                />
                <span>
                  <span className="block font-medium">Prompt injection detected</span>
                  <span className="text-slate-600">Alert when {appConfig.product.name} detects instruction-hijacking patterns in document content.</span>
                </span>
              </label>
              <label className="flex items-start gap-3 rounded border border-slate-200 p-3 text-sm">
                <input
                  type="checkbox"
                  className="mt-1 h-4 w-4 rounded border-slate-300"
                  checked={triggers.policy_blocked}
                  onChange={(e) => setTriggers((current) => ({ ...current, policy_blocked: e.target.checked }))}
                />
                <span>
                  <span className="block font-medium">Requests blocked by {rulesLabel}</span>
                  <span className="text-slate-600">Alert when a user request is denied by policy, model approvals, or confidentiality controls.</span>
                </span>
              </label>
              <label className="flex items-start gap-3 rounded border border-slate-200 p-3 text-sm">
                <input
                  type="checkbox"
                  className="mt-1 h-4 w-4 rounded border-slate-300"
                  checked={triggers.repeated_provider_failures}
                  onChange={(e) => setTriggers((current) => ({ ...current, repeated_provider_failures: e.target.checked }))}
                />
                <span>
                  <span className="block font-medium">Repeated provider failures</span>
                  <span className="text-slate-600">Alert when the same provider keeps failing inside the configured throttle window.</span>
                </span>
              </label>
              <div className="rounded border border-dashed border-slate-200 p-3 text-sm text-slate-500">
                Blocked-request spike detection is reserved for a later pass. This first version focuses on the highest-signal governance events.
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="p-4">
              <CardTitle className="text-base">Recent Alert History</CardTitle>
              <CardDescription>Most recent alert delivery attempts for this {organizationLabel} only.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 p-4 pt-0">
              {historyQuery.data && historyQuery.data.length > 0 ? (
                historyQuery.data.map((item) => (
                  <div key={item.id} className="rounded border border-slate-200 p-3 text-sm">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant={item.status === "sent" ? "secondary" : undefined}>{item.status}</Badge>
                      {item.trigger_type ? <Badge variant="secondary">{item.trigger_type.replaceAll("_", " ")}</Badge> : null}
                      {item.channel ? <Badge variant="secondary">{item.channel}</Badge> : null}
                      <span className="text-slate-600">{formatDateTime(item.timestamp)}</span>
                    </div>
                    <div className="mt-2 text-slate-700">
                      {item.destination ? <div>Destination: {item.destination}</div> : null}
                      {item.reason ? <div>Reason: {item.reason}</div> : null}
                      {item.request_id ? <div>Request ID: {item.request_id}</div> : null}
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded border border-dashed border-slate-200 p-4 text-sm text-slate-500">
                  No alerts have been sent for this {organizationLabel} yet.
                </div>
              )}
            </CardContent>
          </Card>
        </RequireTenantScope>
      </RequireRole>
    </main>
  );
}
