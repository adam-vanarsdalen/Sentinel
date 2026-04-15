from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import settings


DEFAULT_PRESET_ID = "general"
PRESET_FILES = ("manifest", "terminology", "copy", "roles", "risk_taxonomy")


def _resolve_presets_root() -> Path:
    current = Path(__file__).resolve()
    candidates = [
        current.parents[3] / "config" / "presets",  # repo root layout
        current.parents[2] / "config" / "presets",  # docker image layout (/app/config/presets)
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


PRESETS_ROOT = _resolve_presets_root()


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Preset file must contain an object: {path}")
    return data


@lru_cache(maxsize=1)
def list_presets() -> list[dict[str, Any]]:
    presets: list[dict[str, Any]] = []
    if not PRESETS_ROOT.exists():
        return presets
    for entry in sorted(PRESETS_ROOT.iterdir()):
        if not entry.is_dir():
            continue
        manifest_path = entry / "manifest.json"
        if not manifest_path.exists():
            continue
        manifest = _read_json(manifest_path)
        presets.append(
            {
                "id": str(manifest.get("id") or entry.name),
                "name": str(manifest.get("name") or entry.name.title()),
                "industry": str(manifest.get("industry") or entry.name),
                "product_name": str(manifest.get("product_name") or manifest.get("name") or entry.name.title()),
            }
        )
    return presets


@lru_cache(maxsize=16)
def get_preset(preset_id: str) -> dict[str, Any]:
    normalized = (preset_id or "").strip().lower() or DEFAULT_PRESET_ID
    preset_dir = PRESETS_ROOT / normalized
    if not preset_dir.exists() or not preset_dir.is_dir():
        if normalized == DEFAULT_PRESET_ID:
            raise FileNotFoundError(f"Default preset directory is missing: {preset_dir}")
        return get_preset(DEFAULT_PRESET_ID)

    loaded: dict[str, Any] = {"id": normalized}
    for section in PRESET_FILES:
        loaded[section] = _read_json(preset_dir / f"{section}.json")
    loaded["id"] = str(loaded["manifest"].get("id") or normalized)
    return loaded


def get_active_preset_id() -> str:
    requested = (settings.sentinel_preset or "").strip().lower() or DEFAULT_PRESET_ID
    available = {preset["id"] for preset in list_presets()}
    if requested in available:
        return requested
    return DEFAULT_PRESET_ID


def get_active_preset() -> dict[str, Any]:
    return get_preset(get_active_preset_id())


def get_demo_seed(preset_id: str | None = None) -> dict[str, Any]:
    resolved_preset_id = (preset_id or get_active_preset_id()).strip().lower() or DEFAULT_PRESET_ID
    preset = get_preset(resolved_preset_id)
    seed_path = PRESETS_ROOT / str(preset.get("id") or resolved_preset_id) / "demo_seed.json"
    if not seed_path.exists():
        return {}
    return _read_json(seed_path)


def get_terminology() -> dict[str, Any]:
    return dict(get_active_preset().get("terminology") or {})


def get_copy() -> dict[str, Any]:
    return dict(get_active_preset().get("copy") or {})


def get_role_presentations() -> dict[str, Any]:
    return dict(get_active_preset().get("roles") or {})


def get_risk_taxonomy() -> dict[str, Any]:
    return dict(get_active_preset().get("risk_taxonomy") or {})


def get_default_policy_template_id() -> str:
    manifest = get_active_preset().get("manifest") or {}
    return str(manifest.get("default_policy_template_id") or "general_default_policy_v1")


def get_demo_defaults(preset_id: str | None = None) -> dict[str, Any]:
    manifest = get_preset(preset_id or get_active_preset_id()).get("manifest") or {}
    demo = manifest.get("demo") or {}
    return demo if isinstance(demo, dict) else {}


def get_product_name() -> str:
    manifest = get_active_preset().get("manifest") or {}
    return str(manifest.get("product_name") or "Sentinel")


def get_console_name() -> str:
    manifest = get_active_preset().get("manifest") or {}
    return str(manifest.get("console_name") or f"{get_product_name()} Console")


def build_public_app_config() -> dict[str, Any]:
    preset = get_active_preset()
    manifest = dict(preset.get("manifest") or {})
    return {
        "preset_id": get_active_preset_id(),
        "available_presets": list_presets(),
        "product": {
            "name": str(manifest.get("product_name") or "Sentinel"),
            "console_name": str(manifest.get("console_name") or f'{manifest.get("product_name") or "Sentinel"} Console'),
            "support_email": manifest.get("support_email"),
        },
        "terminology": dict(preset.get("terminology") or {}),
        "copy": dict(preset.get("copy") or {}),
        "roles": dict(preset.get("roles") or {}),
        "risk_taxonomy": dict(preset.get("risk_taxonomy") or {}),
    }
