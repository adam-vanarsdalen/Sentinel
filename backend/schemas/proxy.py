"""Core pipeline data types — shared across all layers."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RoutingDecision(BaseModel):
    target_model: str
    target_provider: str  # "anthropic" | "openai" | "ollama" | "bedrock"
    routing_reason: str
    estimated_cost_usd: float
    budget_remaining_usd: float
    rbac_passed: bool
    rbac_details: dict[str, Any] = Field(default_factory=dict)


class EnforcementCheck(BaseModel):
    allowed: bool
    blocked_reason: str | None = None
    policy_id: str | None = None
    action_count_session: int = 0
    action_limit_session: int = 1000
    data_classes_accessed: list[str] = Field(default_factory=list)
    forbidden_endpoints: list[str] = Field(default_factory=list)
    purpose_binding: str | None = None


class ModelResponse(BaseModel):
    content: str
    tool_calls: list[dict[str, Any]] | None = None
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    provider: str
    model: str
    finish_reason: str


class GroundingResult(BaseModel):
    score: float
    block_threshold: float = 0.5
    warn_threshold: float = 0.8
    grounded_claims: list[str] = Field(default_factory=list)
    ungrounded_claims: list[str] = Field(default_factory=list)
    grounding_applicable: bool = True


class AnomalySignal(BaseModel):
    signal_type: str  # "frequency"|"cost"|"data_access"|"error_rate"|"tool_pattern"|"drift"
    severity: float
    baseline_value: float
    observed_value: float
    deviation_factor: float  # z-score


class AnomalyResult(BaseModel):
    agent_id: str
    signals: list[AnomalySignal]
    combined_score: float
    recommended_action: str  # "log"|"throttle"|"pause"|"terminate"
    state_snapshot: dict[str, Any] = Field(default_factory=dict)


class PipelineRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    tenant_id: str
    agent_id: str | None = None
    source: str  # "api"|"agent_loop"|"batch"|"webhook"|"sdk"|"cli"
    source_ip: str | None = None
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | None = None
    model_requested: str | None = None
    input_tokens_estimate: int = 0
    provenance_tags: dict[str, Any] = Field(default_factory=dict)
    raw_headers: dict[str, str] = Field(default_factory=dict)
    routing: RoutingDecision | None = None
    enforcement: EnforcementCheck | None = None


class PipelineResponse(BaseModel):
    request_id: str
    blocked: bool = False
    reason: str | None = None
    response: ModelResponse | None = None
    grounding_score: float | None = None
    anomaly_signals: list[AnomalySignal] = Field(default_factory=list)


class AuditEntry(BaseModel):
    request_id: str
    tenant_id: str
    agent_id: str | None
    action: str
    layer: int
    status: str | None = None
    model: str | None = None
    source: str | None = None
    latency_ms: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    regulation_mappings: dict[str, list[str]] = Field(default_factory=dict)


class PipelineError(Exception):
    def __init__(self, layer: int, error_type: str, message: str):
        self.layer = layer
        self.error_type = error_type
        super().__init__(f"Layer {layer} [{error_type}]: {message}")
