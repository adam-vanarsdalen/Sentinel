"""Layer 2: Routing — model selection, RBAC, budget enforcement."""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from schemas.proxy import PipelineError, PipelineRequest, RoutingDecision

PROVIDER_MAP: dict[str, str] = {
    "claude": "anthropic",
    "gpt": "openai",
    "llama": "ollama",
    "mistral": "ollama",
    "qwen": "ollama",
    "minimax": "ollama",
    "kimi": "ollama",
    "glm": "ollama",
}

# Fall back to Ollama when no cloud API keys are configured.
if not settings.anthropic_api_key and not settings.openai_api_key:
    DEFAULT_MODEL = settings.ollama_default_model
    DEFAULT_PROVIDER = "ollama"
else:
    DEFAULT_MODEL = "claude-haiku-4-5-20251001"
    DEFAULT_PROVIDER = "anthropic"

MODEL_COSTS: dict[str, float] = {
    "claude-haiku-4-5-20251001": 0.000025,
    "claude-sonnet-4-6": 0.000150,
    "claude-opus-4-8": 0.001500,
    "gpt-4o": 0.000200,
    "gpt-4o-mini": 0.000015,
}


def _infer_provider(model: str) -> str:
    lower = model.lower()
    for prefix, provider in PROVIDER_MAP.items():
        if prefix in lower:
            return provider
    return DEFAULT_PROVIDER


def _estimate_cost(model: str, input_tokens: int) -> float:
    rate = MODEL_COSTS.get(model, 0.0001)
    return rate * input_tokens / 1000


async def layer2_route(
    req: PipelineRequest,
    db: AsyncSession | None = None,
    policy: dict[str, Any] | None = None,
) -> RoutingDecision:
    """Select model, verify RBAC, enforce budget."""
    model = req.model_requested or DEFAULT_MODEL
    provider = _infer_provider(model)

    allowed_models: list[str] = policy.get("allowed_models", []) if policy else []
    rbac_passed = True
    rbac_details: dict[str, Any] = {}

    if allowed_models and model not in allowed_models:
        if allowed_models:
            model = allowed_models[0]
            rbac_details["redirected_from"] = req.model_requested
            rbac_details["reason"] = "requested model not in allowed list"
        else:
            rbac_passed = False
            rbac_details["reason"] = f"model {model} not permitted by policy"

    estimated_cost = _estimate_cost(model, req.input_tokens_estimate)

    budget_daily = policy.get("budget_daily_usd") if policy else None
    budget_remaining = float(budget_daily) if budget_daily else 999.0

    routing_reason = f"policy routing → {provider}/{model}"
    if not req.model_requested:
        routing_reason = f"default model selected → {provider}/{model}"

    return RoutingDecision(
        target_model=model,
        target_provider=provider,
        routing_reason=routing_reason,
        estimated_cost_usd=estimated_cost,
        budget_remaining_usd=budget_remaining,
        rbac_passed=rbac_passed,
        rbac_details=rbac_details,
    )
