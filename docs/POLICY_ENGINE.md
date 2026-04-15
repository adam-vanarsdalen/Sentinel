# Policy Engine

## Purpose

The policy engine is Sentinel’s central enforcement layer for AI governance. It determines whether a request is allowed, blocked, flagged, or routed for review based on tenant policy and runtime signals.

## When it runs

- Preflight: before provider call
- Postflight: after provider response (when applicable)

## What it evaluates

- approved provider/model constraints
- prompt pattern blocks and injection signals
- confidential data risk heuristics
- metadata requirements and request bounds
- output validation rules
- tenant-level rate/usage limits

## Policy outcomes

- `allow`: request proceeds and is audited
- `block`: request is denied with structured error envelope
- `flag`: request proceeds with risk annotations
- `review`: request/result is marked for human review workflow

## Tenant and preset awareness

- Policy application is tenant-scoped.
- Presets influence terminology, defaults, and demo policy templates.
- Core policy enforcement logic remains shared across presets.

## Interaction with provider routing

- Policy checks gate provider routing decisions.
- Provider/model approval rules are enforced before request execution.
- Routing attempts/fallback behavior are reflected in audit metadata.

## Interaction with audit and reporting

Policy decisions are written as structured audit events with outcome/reason/risk metadata to support operational review and exported governance reporting.
