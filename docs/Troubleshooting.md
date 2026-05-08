# Sentinel Troubleshooting

## Read the error envelope

Sentinel API failures now use this structure:

```json
{
  "error": {
    "code": "PROVIDER_UNAVAILABLE",
    "message": "The AI provider is currently unavailable.",
    "detail": "OpenAI request failed with status 502",
    "request_id": "req_123",
    "retryable": true
  },
  "detail": "OpenAI request failed with status 502"
}
```

Use the fields this way:
- `error.message`: safe text to show to end users.
- `error.detail`: operator-facing explanation.
- `error.code`: stable programmatic identifier.
- `error.request_id`: include this in support tickets and log searches.
- `error.retryable`: whether retrying is likely to help.

## Common error codes

### `AUTH_REQUIRED`
- Meaning: the user session or API key is missing, invalid, revoked, or expired.
- What to do:
  - Sign in again.
  - For API traffic, confirm the current Sentinel API key is being sent.

### `FORBIDDEN`
- Meaning: the authenticated user does not have the required role.
- What to do:
  - Confirm you are in the right account.
  - Confirm your role includes the requested action.
  - In the UI, Sentinel redirects forbidden routes to the `/forbidden` page.

### `TENANT_SCOPE_ERROR`
- Meaning: an organization-scoped action was attempted without valid organization context.
- What to do:
  - In the admin console, select the correct organization in the top bar.
  - For `super_admin`, send a valid `X-Tenant-Id` for tenant-scoped admin APIs.

### `POLICY_BLOCKED`
- Meaning: Organization AI Rules or organization provider/model approval controls rejected the request.
- What to do:
  - Review `error.detail`, `reason_code`, and the `policy` object in the response.
  - Common causes:
    - blocked prompt pattern
    - provider not approved for the organization
    - model not approved for the organization
    - no default provider/model configured when omitted by the client

### `PROVIDER_TIMEOUT`
- Meaning: the upstream AI provider did not respond before Sentinel’s timeout.
- What to do:
  - Retry later.
  - Check provider status and network connectivity.
  - Use `request_id` to correlate Sentinel logs.

### `PROVIDER_UNAVAILABLE`
- Meaning: the upstream provider rejected or failed the request.
- What to do:
  - Check provider credentials and provider-specific configuration.
  - If `retryable = true`, try again after a short delay.
  - If `retryable = false`, treat it as a configuration/authentication problem first.

### `EXPORT_FAILED`
- Meaning: Sentinel could not generate the requested export.
- What to do:
  - Retry the export.
  - Narrow filters if the result set is very large.
  - Check server logs with the returned `request_id`.

### `VALIDATION_ERROR`
- Meaning: the request shape or parameters were invalid.
- What to do:
  - Review required fields and allowed values.
  - For gateway calls, confirm `messages`, `provider`, `model`, and metadata are valid.

### `INTERNAL_ERROR`
- Meaning: Sentinel hit an unexpected server-side failure.
- What to do:
  - Retry once if appropriate.
  - Capture the `request_id`.
  - Review backend logs for that request ID.

## Frontend-specific notes

- Sentinel no longer shows raw stack traces in normal page UX.
- Missing routes render a custom 404 page.
- Forbidden routes redirect to a 403 page.
- Retryable provider failures show safe retry guidance in the Provider Settings UI.

## Alerting-specific checks

### Test alert says delivery failed
- Meaning: Sentinel accepted the test request, but at least one alert channel could not deliver.
- What to check:
  - For email:
    - confirm `SMTP_HOST` is set
    - confirm `SMTP_PORT` is correct
    - if `SMTP_USER` is set, confirm `SMTP_PASSWORD` is also set
    - confirm the tenant’s recipient list contains real addresses
  - For webhooks:
    - confirm the stored webhook was saved successfully
    - confirm the target system accepts the selected webhook format (`generic`, `slack`, or `teams`)
    - confirm outbound network access from the Sentinel host
  - Review the current organization’s recent alert history on the **Alerts** page.

### Expected alerts are not arriving
- Meaning: the underlying audit events may be below threshold, disabled, or throttled.
- What to check:
  - Confirm the relevant trigger is enabled on the **Alerts** page.
  - Confirm the organization’s severity threshold is not higher than the event severity.
  - Confirm the confidentiality threshold is not set above the observed `phi_score`.
  - Confirm an earlier alert of the same type was not already sent inside the throttle window.
  - Search the audit trail for `ALERT_SENT` and `ALERT_FAILED` actions for the same time range.

### Repeated provider failures are not alerting
- Meaning: Sentinel only alerts after the same provider fails enough times inside the configured window.
- What to check:
  - Confirm **Repeated provider failures** is enabled.
  - Confirm the provider failure threshold is low enough for the current incident volume.
  - Confirm the failures share the same provider name and are occurring inside the configured throttle window.

### Alert history is empty
- Meaning: no alert deliveries have been attempted for the current organization.
- What to do:
  - Confirm you are viewing the correct organization.
  - Send a test alert from the **Alerts** page.
  - If the test call is rejected, configure at least one email recipient or webhook first.
