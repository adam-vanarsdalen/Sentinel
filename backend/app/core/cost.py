from __future__ import annotations

from decimal import Decimal


# Pilot price table (USD) per 1K tokens.
#
# Notes:
# - This table is intentionally small and pattern-based; it is meant to provide rough estimates for governance,
#   not billing.
# - Azure OpenAI deployments often use custom "model" names (deployment names). For those, we attempt a
#   best-effort substring match (e.g., "gpt-4o" appearing in the deployment name).
MODEL_PRICES_PER_1K_TOKENS: dict[str, dict[str, Decimal]] = {
    "mock": {"prompt": Decimal("0.0000"), "completion": Decimal("0.0000")},
}

MODEL_PREFIX_PRICES_PER_1K_TOKENS: list[tuple[str, dict[str, Decimal]]] = [
    # OpenAI (examples; update as needed for your approved models)
    ("gpt-4o-mini", {"prompt": Decimal("0.00015"), "completion": Decimal("0.00060")}),
    ("gpt-4o", {"prompt": Decimal("0.00500"), "completion": Decimal("0.01500")}),
    ("gpt-4.1-mini", {"prompt": Decimal("0.00030"), "completion": Decimal("0.00120")}),
    ("gpt-4.1", {"prompt": Decimal("0.01000"), "completion": Decimal("0.03000")}),
    ("gpt-4-turbo", {"prompt": Decimal("0.01000"), "completion": Decimal("0.03000")}),
    ("gpt-4", {"prompt": Decimal("0.03000"), "completion": Decimal("0.06000")}),
    ("gpt-3.5-turbo", {"prompt": Decimal("0.00050"), "completion": Decimal("0.00150")}),
    # Anthropic (Claude 3/3.5 families)
    ("claude-3-5-sonnet", {"prompt": Decimal("0.00300"), "completion": Decimal("0.01500")}),
    ("claude-3-5-haiku", {"prompt": Decimal("0.00080"), "completion": Decimal("0.00400")}),
    ("claude-3-opus", {"prompt": Decimal("0.01500"), "completion": Decimal("0.07500")}),
    ("claude-3-sonnet", {"prompt": Decimal("0.00300"), "completion": Decimal("0.01500")}),
    ("claude-3-haiku", {"prompt": Decimal("0.00025"), "completion": Decimal("0.00125")}),
]

MODEL_SUBSTRING_PRICES_PER_1K_TOKENS: list[tuple[str, dict[str, Decimal]]] = [
    # Best-effort mapping for Azure deployment names (e.g., "gpt-4o-prod", "claude-3-haiku-azure").
    ("gpt-4o-mini", {"prompt": Decimal("0.00015"), "completion": Decimal("0.00060")}),
    ("gpt-4o", {"prompt": Decimal("0.00500"), "completion": Decimal("0.01500")}),
    ("gpt-4.1-mini", {"prompt": Decimal("0.00030"), "completion": Decimal("0.00120")}),
    ("gpt-4.1", {"prompt": Decimal("0.01000"), "completion": Decimal("0.03000")}),
    ("gpt-4", {"prompt": Decimal("0.03000"), "completion": Decimal("0.06000")}),
    ("gpt-3.5-turbo", {"prompt": Decimal("0.00050"), "completion": Decimal("0.00150")}),
    ("claude-3-5-sonnet", {"prompt": Decimal("0.00300"), "completion": Decimal("0.01500")}),
    ("claude-3-5-haiku", {"prompt": Decimal("0.00080"), "completion": Decimal("0.00400")}),
    ("claude-3-opus", {"prompt": Decimal("0.01500"), "completion": Decimal("0.07500")}),
    ("claude-3-sonnet", {"prompt": Decimal("0.00300"), "completion": Decimal("0.01500")}),
    ("claude-3-haiku", {"prompt": Decimal("0.00025"), "completion": Decimal("0.00125")}),
]


def _lookup_prices(model: str) -> dict[str, Decimal] | None:
    m = (model or "").strip().lower()
    if not m:
        return None
    exact = MODEL_PRICES_PER_1K_TOKENS.get(m)
    if exact:
        return exact
    for prefix, prices in MODEL_PREFIX_PRICES_PER_1K_TOKENS:
        if m.startswith(prefix):
            return prices
    for needle, prices in MODEL_SUBSTRING_PRICES_PER_1K_TOKENS:
        if needle in m:
            return prices
    return None


def estimate_cost_usd(*, model: str, prompt_tokens: int, completion_tokens: int) -> Decimal:
    prices = _lookup_prices(model)
    if not prices:
        return Decimal("0.0")
    return (Decimal(prompt_tokens) / Decimal(1000)) * prices["prompt"] + (
        Decimal(completion_tokens) / Decimal(1000)
    ) * prices["completion"]
