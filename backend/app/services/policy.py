from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException, status
from jsonschema import Draft202012Validator

from app.services.security_flags import SecuritySignals, normalize_text_for_scanning


POLICY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "allowed_models": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "max_tokens_per_request": {"type": "integer", "minimum": 1, "maximum": 8192},
        "max_prompt_chars": {"type": "integer", "minimum": 1, "maximum": 200000},
        "rate_limits": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "tenant_per_minute": {"type": "integer", "minimum": 1, "maximum": 100000},
                "api_key_per_minute": {"type": "integer", "minimum": 1, "maximum": 100000},
            },
        },
        "block_prompt_patterns": {"type": "array", "items": {"type": "string"}},
        "require_system_prompt_prefix": {"type": "string"},
        "metadata_requirements": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "data_classification": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            },
        },
        "output_validation_rules": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "type": {"type": "string", "enum": ["regex", "json_schema"]},
                    "pattern": {"type": "string"},
                    "schema": {"type": "object"},
                    "action": {"type": "string", "enum": ["flag", "block"]},
                    "reason": {"type": "string"},
                },
                "required": ["type"],
            },
        },
        "logging": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "store_redacted_snippets": {"type": "boolean"},
                "store_raw_content": {"type": "boolean"},
            },
        },
        "security": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "prompt_injection_action": {"type": "string", "enum": ["flag", "block_high", "block_med"]},
            },
        },
        "phi": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "enabled": {"type": "boolean"},
                "threshold_score": {"type": "integer", "minimum": 0, "maximum": 100},
                "action": {"type": "string", "enum": ["flag", "block"]},
                "flag_on_any_match": {"type": "boolean"},
            },
        },
        "legal": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "system_prompt_prefix_base": {"type": "string"},
                "allow_document_content": {"type": "boolean"},
                "employment_bias_guard": {"type": "boolean"},
            },
        },
        "assistant_profile": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "system_prompt_prefix_base": {"type": "string"},
                "allow_document_content": {"type": "boolean"},
                "employment_bias_guard": {"type": "boolean"},
            },
        },
    },
    "required": ["allowed_models", "max_tokens_per_request"],
}


DEFAULT_POLICY: dict[str, Any] = {
    "allowed_models": ["mock"],
    "max_tokens_per_request": 512,
    "max_prompt_chars": 20000,
    "block_prompt_patterns": [],
    "require_system_prompt_prefix": "",
    "output_validation_rules": [],
    "logging": {"store_redacted_snippets": False, "store_raw_content": False},
    "security": {"prompt_injection_action": "flag"},
    "phi": {"enabled": True, "threshold_score": 80, "action": "flag"},
}

SEVERITY_ORDER = {"low": 0, "med": 1, "high": 2}


class PolicyEnforcementError(HTTPException):
    def __init__(
        self,
        *,
        status_code: int,
        detail: str,
        block_stage: str,
        reason_code: str,
        matched_rule: str | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.block_stage = block_stage
        self.reason_code = reason_code
        self.matched_rule = matched_rule


def validate_policy_json(policy_json: dict) -> None:
    v = Draft202012Validator(POLICY_SCHEMA)
    errors = sorted(v.iter_errors(policy_json), key=lambda e: e.path)
    if errors:
        msg = "; ".join([e.message for e in errors[:3]])
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid policy: {msg}")

    for pat in policy_json.get("block_prompt_patterns", []):
        re.compile(pat)
    for rule in policy_json.get("output_validation_rules", []):
        if rule.get("type") == "regex" and rule.get("pattern"):
            re.compile(rule["pattern"])


def enforce_preflight(
    *, policy: dict, model: str, prompt_text: str, max_tokens: int | None, metadata: dict | None = None
) -> None:
    if model not in policy["allowed_models"]:
        raise PolicyEnforcementError(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Model not allowed by policy",
            block_stage="preflight_model_allowlist",
            reason_code="model_not_allowed_by_policy",
            matched_rule="allowed_models",
        )
    if max_tokens is not None and max_tokens > int(policy["max_tokens_per_request"]):
        raise PolicyEnforcementError(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="max_tokens exceeds tenant policy",
            block_stage="preflight_max_tokens",
            reason_code="max_tokens_exceeds_policy_limit",
            matched_rule="max_tokens_per_request",
        )
    if len(prompt_text) > int(policy.get("max_prompt_chars", 20000)):
        raise PolicyEnforcementError(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Prompt too long",
            block_stage="preflight_prompt_length",
            reason_code="prompt_too_long",
            matched_rule="max_prompt_chars",
        )
    _, normalized_prompt = normalize_text_for_scanning(prompt_text)
    for pat in policy.get("block_prompt_patterns", []):
        if re.search(pat, prompt_text, flags=re.IGNORECASE) or re.search(pat, normalized_prompt, flags=re.IGNORECASE):
            raise PolicyEnforcementError(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Prompt blocked by policy",
                block_stage="preflight_prompt_pattern",
                reason_code="prompt_pattern_block",
                matched_rule=str(pat),
            )
    metadata_reqs = policy.get("metadata_requirements") or {}
    if isinstance(metadata_reqs, dict) and metadata_reqs.get("data_classification"):
        allowed = set([str(v) for v in (metadata_reqs.get("data_classification") or [])])
        got = None
        if isinstance(metadata, dict):
            got = metadata.get("data_classification")
        if not got or str(got) not in allowed:
            raise PolicyEnforcementError(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"metadata.data_classification required (allowed: {', '.join(sorted(allowed))})",
                block_stage="preflight_metadata_requirements",
                reason_code="metadata_data_classification_required",
                matched_rule="metadata_requirements.data_classification",
            )


def prompt_injection_action(policy: dict) -> str:
    security = policy.get("security") or {}
    if not isinstance(security, dict):
        return "flag"
    action = str(security.get("prompt_injection_action") or "flag").strip().lower()
    if action not in {"flag", "block_high", "block_med"}:
        return "flag"
    return action


def should_block_prompt_injection(*, policy: dict, signals: SecuritySignals) -> bool:
    if "PROMPT_INJECTION_SUSPECTED" not in signals.flags and "EMBEDDED_INJECTION_SUSPECTED" not in signals.flags:
        return False
    action = prompt_injection_action(policy)
    if action == "flag":
        return False
    threshold = "med" if action == "block_med" else "high"
    return SEVERITY_ORDER.get(signals.severity, 0) >= SEVERITY_ORDER[threshold]


def apply_required_system_prefix(*, policy: dict, messages: list[dict]) -> list[dict]:
    profile = policy.get("assistant_profile") or policy.get("legal") or {}
    prefix = (profile.get("system_prompt_prefix_base") if isinstance(profile, dict) else None) or policy.get("require_system_prompt_prefix") or ""
    if prefix and isinstance(profile, dict):
        if profile.get("allow_document_content") is False:
            prefix = (
                prefix.rstrip()
                + "\n"
                + "- Do not request or process full document contents; ask for a short excerpt or a summary when needed.\n"
            )
        if profile.get("employment_bias_guard") is True:
            prefix = (
                prefix.rstrip()
                + "\n"
                + "- In employment/hiring contexts, avoid protected-class or discriminatory reasoning; focus on job-related, lawful criteria.\n"
            )
    if not prefix:
        return messages
    if messages and messages[0].get("role") == "system":
        content = messages[0].get("content") or ""
        if content.startswith(prefix):
            return messages
        messages = [{"role": "system", "content": prefix + "\n" + content}] + messages[1:]
        return messages
    return [{"role": "system", "content": prefix}] + messages


def evaluate_output_rules(*, policy: dict, output_text: str) -> tuple[list[str], bool]:
    flags: list[str] = []
    blocked = False
    for rule in policy.get("output_validation_rules", []):
        action = rule.get("action", "flag")
        reason = rule.get("reason") or "Output validation triggered"
        if rule.get("type") == "regex" and rule.get("pattern"):
            if re.search(rule["pattern"], output_text, flags=re.IGNORECASE):
                flags.append(f"OUTPUT_RULE:{reason}")
                if action == "block":
                    blocked = True
        if rule.get("type") == "json_schema" and rule.get("schema"):
            try:
                import json

                obj = json.loads(output_text)
                Draft202012Validator(rule["schema"]).validate(obj)
            except Exception:
                flags.append(f"OUTPUT_RULE:{reason}")
                if action == "block":
                    blocked = True
    return flags, blocked
