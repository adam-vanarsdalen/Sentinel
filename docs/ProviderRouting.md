# SentinelLaw Provider Routing

This document describes how SentinelLaw chooses a provider and model for a tenant-scoped gateway request, and how the new resilience controls behave.

## Routing order

For `POST /v1/chat/completions`:

1. SentinelLaw resolves the tenant from the presented API key.
2. If the tenant has provider-config rows:
   - only enabled provider configs are considered approved
   - the tenant default provider is used when the request omits `provider`
   - the provider allowlist is enforced server-side
   - the provider default model or deployment is used when the request omits `model`
3. If the tenant has no provider-config rows:
   - development may still fall back to the legacy env-based provider routing
   - production fails closed

## Timeout and retry policy

Each provider config can carry a `config_json.resilience` block:

```json
{
  "connect_timeout_seconds": 5,
  "read_timeout_seconds": 60,
  "retry_count": 1,
  "retryable_status_codes": [408, 409, 425, 429, 500, 502, 503, 504],
  "retryable_error_classes": ["timeout", "connection", "rate_limit", "server_error"],
  "fallback_enabled": false,
  "fallback_provider": null,
  "fallback_model": null
}
```

Current behavior:
- The selected provider gets the configured connect/read timeout values.
- Transient failures are retried up to `retry_count`.
- Retry decisions use the union of:
  - provider-reported retryability
  - configured retryable status codes
  - configured retryable error classes

Audit events:
- `PROVIDER_TIMEOUT`: written for each timed-out provider attempt
- `PROVIDER_RETRY`: written when SentinelLaw schedules another attempt after a transient failure

## Fallback policy

Fallback is opt-in and conservative.

SentinelLaw will only attempt fallback when:
- the active provider config explicitly enables fallback
- a `fallback_provider` and `fallback_model` are configured
- the fallback target is still approved and enabled for the same tenant
- the fallback target passes the same provider/model approval rules as any direct request

SentinelLaw will not silently switch providers when fallback is disabled.

Audit events:
- `PROVIDER_FALLBACK_USED`: written when SentinelLaw switches from the primary target to the configured fallback target
- `PROVIDER_FALLBACK_DENIED`: written when fallback was configured but the fallback target is not allowed for the tenant or is otherwise invalid

## Final request audit trail

Every request still ends with the existing `LLM_REQUEST` audit event.

Key points:
- `provider` and `model` on the final `LLM_REQUEST` row reflect the provider/model that actually handled the request
- `request_id` is preserved across retries and fallback attempts
- `event_data.routing.attempts` records the route history for that request

Example attempt history:

```json
{
  "routing": {
    "attempts": [
      {
        "provider": "openai",
        "model": "gpt-4.1",
        "attempt_number": 1,
        "outcome": "fail",
        "error_code": "PROVIDER_TIMEOUT",
        "error_class": "timeout",
        "provider_status_code": null
      },
      {
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "attempt_number": 1,
        "outcome": "success"
      }
    ]
  }
}
```

## Conservative posture notes

- Fallback is never an implicit “best effort” load-balancing feature.
- A tenant must approve the fallback provider/model explicitly before it can be used.
- If the configured fallback target is not allowed, SentinelLaw records `PROVIDER_FALLBACK_DENIED` and fails the request instead of routing to an alternate provider anyway.
