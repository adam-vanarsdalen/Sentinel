"""Unified compliance mapper — audit event layer → regulation controls."""
from __future__ import annotations

from regulatory import colorado_sb205, eu_ai_act, hipaa, nist_ai_rmf


def get_controls_for_layer(layer: int) -> dict[str, list[str]]:
    """Return all regulation controls mapped to a given layer number."""
    result: dict[str, list[str]] = {}

    if controls := eu_ai_act.LAYER_CONTROLS.get(layer):
        result["EU_AI_ACT"] = controls
    if controls := nist_ai_rmf.LAYER_CONTROLS.get(layer):
        result["NIST_AI_RMF"] = controls
    if controls := colorado_sb205.LAYER_CONTROLS.get(layer):
        result["COLORADO_SB205"] = controls
    if controls := hipaa.LAYER_CONTROLS.get(layer):
        result["HIPAA"] = controls

    return result


def get_kill_switch_controls() -> dict[str, list[str]]:
    return {
        "EU_AI_ACT": eu_ai_act.KILL_SWITCH_CONTROLS,
        "NIST_AI_RMF": nist_ai_rmf.KILL_SWITCH_CONTROLS,
    }


def get_human_review_controls() -> dict[str, list[str]]:
    return {
        "EU_AI_ACT": eu_ai_act.HUMAN_REVIEW_CONTROLS,
        "NIST_AI_RMF": nist_ai_rmf.HUMAN_REVIEW_CONTROLS,
    }


def all_controls() -> dict[str, list[str]]:
    return {
        "EU_AI_ACT": eu_ai_act.ALL_ARTICLES,
        "NIST_AI_RMF": nist_ai_rmf.ALL_CONTROLS,
        "COLORADO_SB205": colorado_sb205.ALL_CONTROLS,
        "HIPAA": hipaa.ALL_CONTROLS,
    }
