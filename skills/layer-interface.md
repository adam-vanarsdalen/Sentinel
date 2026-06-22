# Sentinel Layer Interface Contract

Every layer function receives a PipelineRequest and returns its own typed result.
No layer may mutate PipelineRequest directly — attach results to the response object.

## PipelineRequest fields (read-only within layers)
request_id: str          # UUID4 — never modify, always thread through to audit
timestamp: datetime      # UTC, set at ingestion
tenant_id: str           # Required on every DB write
agent_id: str | None
messages: list[dict]
tools: list[dict] | None
input_tokens_estimate: int
provenance_tags: dict
routing: RoutingDecision | None    # Set by Layer 2, read by 3+
enforcement: EnforcementCheck | None  # Set by Layer 3, read by 4+

## Layer return types (exact signatures)
layer1_ingest() -> PipelineRequest
layer2_route()  -> RoutingDecision
layer3_enforce() -> EnforcementCheck
layer4_reason()  -> ModelResponse
layer5_ground()  -> GroundingResult
layer6_detect()  -> AnomalyResult | None
layer7_record()  -> AuditEntry

## Blocking convention
Any layer that blocks must: set allowed=False, set blocked_reason (human-readable),
write to audit_log BEFORE returning, emit alert via Redis pub/sub.
Never return a block silently.
