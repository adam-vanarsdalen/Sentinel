from __future__ import annotations

from app.core.presets import build_public_app_config, get_demo_seed, get_preset, list_presets


def test_list_presets_includes_expected_verticals():
    preset_ids = {preset["id"] for preset in list_presets()}
    assert {"general", "legal", "finance", "healthcare"} <= preset_ids


def test_missing_preset_falls_back_to_general():
    preset = get_preset("does-not-exist")
    assert preset["manifest"]["id"] == "general"
    assert preset["terminology"]["organization_singular"] == "Organization"


def test_public_app_config_defaults_to_general(monkeypatch):
    monkeypatch.setattr("app.core.presets.settings.sentinel_preset", "general")

    config = build_public_app_config()

    assert config["preset_id"] == "general"
    assert config["product"]["name"] == "Sentinel"
    assert config["terminology"]["organization_singular"] == "Organization"
    assert config["terminology"]["rules_label"] == "Organization AI Rules"
    assert config["terminology"]["messages"]["blocked_by_rules"] == "Blocked by AI Rules."


def test_public_app_config_uses_legal_terminology_when_legal_preset_is_active(monkeypatch):
    monkeypatch.setattr("app.core.presets.settings.sentinel_preset", "legal")

    config = build_public_app_config()

    assert config["preset_id"] == "legal"
    assert config["product"]["name"] == "SentinelLaw"
    assert config["terminology"]["organization_singular"] == "Firm"
    assert config["terminology"]["rules_label"] == "Firm AI Rules"
    assert config["terminology"]["workflow"]["primary_entity_label"] == "Matter"


def test_demo_seed_contains_coherent_general_demo_definition():
    seed = get_demo_seed("general")

    assert seed["tenant"]["name"] == "Northwind Operations"
    assert seed["tenant"]["profile"] == "Enterprise Operations"
    assert len(seed["users"]) >= 5
    assert len(seed["providers"]) >= 2
    assert len(seed["policy_versions"]) >= 2
    assert len(seed["audit_events"]) >= 5
    assert seed["eval_run"]["provider"] == "openai"


def test_demo_seed_contains_preset_specific_legal_content():
    seed = get_demo_seed("legal")

    assert seed["tenant"]["name"] == "Calder & Pine LLP"
    assert any(item["template_id"] == "legal_strict_confidentiality_v1" for item in seed["policy_versions"])
    assert any(event["action_type"] == "AUDIT_REPORT_EXPORTED" for event in seed["audit_events"])
