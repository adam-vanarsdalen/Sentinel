from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CatalogModel:
    id: str
    display_name: str
    status: str = "active"
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class CatalogProvider:
    id: str
    display_name: str
    default_model_field: str | None
    supports_custom_models: bool
    enabled_by_default: bool
    models: tuple[CatalogModel, ...]
    notes: str | None = None


PROVIDER_CATALOG: dict[str, CatalogProvider] = {
    "mock": CatalogProvider(
        id="mock",
        display_name="Mock",
        default_model_field="default_model",
        supports_custom_models=False,
        enabled_by_default=True,
        models=(
            CatalogModel(id="mock", display_name="Mock"),
        ),
        notes="Internal deterministic provider for local development and test flows.",
    ),
    "openai": CatalogProvider(
        id="openai",
        display_name="OpenAI",
        default_model_field="default_model",
        supports_custom_models=False,
        enabled_by_default=True,
        models=(
            CatalogModel(id="gpt-4.1-mini", display_name="GPT-4.1 mini"),
            CatalogModel(id="gpt-4.1", display_name="GPT-4.1"),
            CatalogModel(id="gpt-4o-mini", display_name="GPT-4o mini", status="legacy"),
            CatalogModel(id="gpt-4o", display_name="GPT-4o", status="legacy"),
            CatalogModel(id="gpt-4-turbo", display_name="GPT-4 Turbo", status="legacy"),
        ),
        notes="Curated OpenAI model IDs used by Sentinel demos, tests, and operator workflows.",
    ),
    "anthropic": CatalogProvider(
        id="anthropic",
        display_name="Anthropic",
        default_model_field="default_model",
        supports_custom_models=False,
        enabled_by_default=False,
        models=(
            CatalogModel(id="claude-sonnet-4-6", display_name="Claude Sonnet 4.6"),
            CatalogModel(id="claude-opus-4-6", display_name="Claude Opus 4.6"),
            CatalogModel(id="claude-3-5-sonnet-latest", display_name="Claude 3.5 Sonnet (latest)", status="legacy"),
            CatalogModel(id="claude-sonnet-4-5", display_name="Claude Sonnet 4.5", status="legacy"),
            CatalogModel(id="claude-opus-4", display_name="Claude Opus 4", status="legacy"),
            CatalogModel(id="claude-3-haiku-20240307", display_name="Claude 3 Haiku (20240307)", status="legacy"),
        ),
        notes="Curated Anthropic model IDs currently used in Sentinel seeds/tests and compatibility paths.",
    ),
    "azure_openai": CatalogProvider(
        id="azure_openai",
        display_name="Azure OpenAI",
        default_model_field="default_deployment",
        supports_custom_models=True,
        enabled_by_default=False,
        models=(
            CatalogModel(id="care-gpt-4o-mini", display_name="care-gpt-4o-mini", status="example"),
            CatalogModel(id="care-gpt-4.1-mini", display_name="care-gpt-4.1-mini", status="example"),
            CatalogModel(id="gpt-4o-prod", display_name="gpt-4o-prod", status="example"),
        ),
        notes="`model` is treated as Azure deployment name; custom deployment IDs are allowed.",
    ),
}


PROVIDER_TYPES: tuple[str, ...] = tuple([provider_id for provider_id in PROVIDER_CATALOG if provider_id != "mock"])
ALL_PROVIDER_TYPES: tuple[str, ...] = tuple(PROVIDER_CATALOG.keys())


def provider_default_model_field(provider_id: str) -> str:
    provider = get_provider_or_raise(provider_id)
    if not provider.default_model_field:
        raise ValueError(f"Provider '{provider.id}' does not define a default model field")
    return provider.default_model_field


def get_provider_or_raise(provider_id: str) -> CatalogProvider:
    normalized = normalize_provider_id(provider_id)
    provider = PROVIDER_CATALOG.get(normalized)
    if provider is None:
        raise ValueError("Invalid provider_type")
    return provider


def normalize_provider_id(provider_id: str | None, *, allow_mock: bool = True) -> str:
    normalized = str(provider_id or "").strip().lower()
    allowed = ALL_PROVIDER_TYPES if allow_mock else PROVIDER_TYPES
    if normalized not in allowed:
        raise ValueError("Invalid provider_type")
    return normalized


def _known_models_for_provider(provider: CatalogProvider) -> dict[str, str]:
    known: dict[str, str] = {}
    for model in provider.models:
        model_id = model.id.strip()
        if model_id:
            known[model_id.lower()] = model_id
        for alias in model.aliases:
            alias_id = alias.strip()
            if alias_id:
                known[alias_id.lower()] = model_id
    return known


def normalize_model_id(provider_id: str, model_id: str | None, *, allow_empty: bool = True) -> str:
    provider = get_provider_or_raise(provider_id)
    raw = str(model_id or "").strip()
    if not raw:
        if allow_empty:
            return ""
        raise ValueError("model is required")

    known = _known_models_for_provider(provider)
    if raw.lower() in known:
        return known[raw.lower()]
    if provider.supports_custom_models:
        return raw
    raise ValueError(f"Unknown model for provider '{provider.id}': {raw}")


def normalize_model_allowlist(provider_id: str, models: list[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for item in models or []:
        model = normalize_model_id(provider_id, item, allow_empty=True)
        if not model:
            continue
        key = model.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(model)
    return normalized


def catalog_payload(*, include_mock: bool = False) -> dict[str, Any]:
    provider_ids = ALL_PROVIDER_TYPES if include_mock else PROVIDER_TYPES
    providers: list[dict[str, Any]] = []
    for provider_id in provider_ids:
        provider = PROVIDER_CATALOG[provider_id]
        providers.append(
            {
                "id": provider.id,
                "display_name": provider.display_name,
                "default_model_field": provider.default_model_field,
                "supports_custom_models": provider.supports_custom_models,
                "enabled_by_default": provider.enabled_by_default,
                "notes": provider.notes,
                "models": [
                    {
                        "id": model.id,
                        "display_name": model.display_name,
                        "status": model.status,
                        "aliases": list(model.aliases),
                    }
                    for model in provider.models
                ],
            }
        )
    return {"providers": providers}


def policy_model_options(*, include_mock: bool = True) -> list[str]:
    options: list[str] = []
    seen: set[str] = set()
    provider_ids = ALL_PROVIDER_TYPES if include_mock else PROVIDER_TYPES
    for provider_id in provider_ids:
        provider = PROVIDER_CATALOG[provider_id]
        for model in provider.models:
            key = model.id.lower()
            if key in seen:
                continue
            seen.add(key)
            options.append(model.id)
    return options


def default_model_for_provider(provider_id: str) -> str | None:
    provider = get_provider_or_raise(provider_id)
    if not provider.models:
        return None
    return provider.models[0].id
