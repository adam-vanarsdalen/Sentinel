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

EXFILTRATION_INTENT_PATTERNS: tuple[str, ...] = (
    r"\bdo\s+not\s+redact\b",
    r"\bunredacted\b",
    r"\bkeep\s+(?:all\s+)?(?:identifiers?|details?)\s+visible\b",
    r"\binclude\s+(?:the\s+)?(?:full|exact)\b",
    r"\bwithout\s+redaction\b",
)

SENSITIVE_IDENTIFIER_PATTERNS: tuple[str, ...] = (
    r"\b\d{3}-\d{2}-\d{4}\b",  # SSN-like
    r"\b\d{9}\s*/\s*\d{6,17}\b",  # routing/account pair
    r"\b(?:dob|date\s+of\s+birth)\b.{0,12}\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
    r"\bmat-\d{4}-\d+\b",
    r"\b(?:bank\s+account|account\s+number|routing\s+number|ssn|social\s+security|private\s+pricing|confidential\s+pricing)\b",
    r"\bmrn[-\s:]?\w+\b",
    r"\bmedical\s+record\s+number\b",
    r"\binsurance\s+member\s+id\b",
    r"\b(?:diagnosis\s+details?|medication\s+list|psychotherapy\s+notes?)\b",
    r"\bpatient(?:['’]s)?\s+full\s+name\b",
)

POLICY_EVASION_INTENT_PATTERNS: tuple[str, ...] = (
    r"\bless\s+likely\s+to\s+be\s+flagged\b",
    r"\bless\s+likely\s+to\s+be\s+blocked\b",
    r"\bless\s+likely\s+to\s+trigger\s+safeguards?\b",
    r"\bavoid\s+detection\b",
    r"\bevade\s+(?:policy|filters?|detection|guardrails?)\b",
    r"\bbypass\s+(?:policy|filters?|detection|guardrails?)\b",
    r"\bbypass\s+standard\s+restrictions\b",
    r"\belevated\s+authorit(?:y|ies)\b",
    r"\brewrite\s+(?:a\s+)?request\b.{0,80}\b(?:flagged|blocked|detected)\b",
    r"\bsounds?\s+like\s+(?:a\s+)?normal\s+administrative\s+task\b",
)

PROTECTED_TARGET_PATTERNS: tuple[str, ...] = (
    r"\bhidden\s+instructions?\b",
    r"\bsystem\s+prompt\b",
    r"\bdeveloper\s+instructions?\b",
    r"\binternal\s+policy\s+rules?\b",
    r"\bconfidential\s+data\b",
    r"\bprotected\s+patient\s+information\b",
    r"\bpatient\s+information\b",
    r"\bphi\b",
    r"\bhipaa\b",
    r"\bpayment\s+approval\s+matrix\b",
    r"\bfraud\s+thresholds?\b",
    r"\bunreleased\s+forecast\s+assumptions?\b",
    r"\bcustomer\s+bank\s+details?\b",
    r"\binternal\s+risk\s+notes?\b",
    r"\bprivileged\s+legal\s+analysis\b",
    r"\battorney\s+work\s+product\b",
    r"\bconfidential\s+matter\s+details?\b",
    r"\blegal\s+matter\s+details?\b",
    r"\bharmless\s+document(?:-|\s+)summari[sz]ation\s+request\b",
)

SENSITIVE_INVENTORY_INTENT_PATTERNS: tuple[str, ...] = (
    r"\blist\s+the\s+categories?\s+of\s+protected\s+information\b",
    r"\bprovide\s+representative\s+examples?\b",
    r"\bvalidate\s+coverage\b",
    r"\bwhat\s+protected\s+information\s+this\s+system\s+can\s+access\b",
)

SENSITIVE_INVENTORY_SCOPE_PATTERNS: tuple[str, ...] = (
    r"\bprotected\s+information\b",
    r"\bconfidential\s+information\b",
    r"\bsensitive\s+data\b",
    r"\bhidden\s+instructions?\b",
    r"\binternal\s+policy\s+rules?\b",
)

INTERNAL_CONFIG_EXFILTRATION_INTENT_PATTERNS: tuple[str, ...] = (
    r"\bretrieve\b.{0,80}\bhidden\s+configuration\b",
    r"\breveal\b.{0,80}\bhidden\s+configuration\b",
    r"\buse\s+all\s+available\s+internal\s+tools\b",
    r"\buse\s+any\s+available\s+(?:internal\s+)?tools\b",
    r"\binternal\s+configuration\s+sources?\b",
    r"\bpresent\s+it\s+in\s+a\s+concise\s+operational\s+report\b",
)

INTERNAL_CONFIG_EXFILTRATION_SCOPE_PATTERNS: tuple[str, ...] = (
    r"\binternal\s+tools\b",
    r"\blogs\b",
    r"\bstored\s+prompts?\b",
    r"\bpolicy\s+definitions?\b",
    r"\bprovider\s+metadata\b",
    r"\bhidden\s+configuration\b",
)

HIDDEN_GUIDANCE_EXFIL_INTENT_PATTERNS: tuple[str, ...] = (
    r"\breveal\b.{0,80}\b(hidden|internal|concealed)\b",
    r"\bdisclose\b.{0,80}\b(hidden|internal|concealed)\b",
    r"\bsummarize\b.{0,80}\b(hidden|internal|concealed)\b",
    r"\bhidden\s+instructions?\b.{0,120}\b(summarize|infer)\b",
    r"\binfer\b.{0,120}\b(hidden\s+instructions?|enforcement\s+rules?)\b",
    r"\boutput\b.{0,80}\b(hidden|internal|concealed)\b",
    r"\bprovide\b.{0,120}\binternal\s+policy\s+(?:and\s+)?routing\s+rules?\b",
    r"\bprovide\b.{0,80}\b(full|complete)\s+configuration\s+summary\b",
    r"\btransform\b.{0,160}\bexecutive\s+summary\b.{0,180}\b(hidden\s+guidance|confidential\s+details?)\b",
)

HIDDEN_GUIDANCE_EXFIL_SCOPE_PATTERNS: tuple[str, ...] = (
    r"\bhidden\s+instructions?\b",
    r"\bhidden\s+system\s+instructions?\b",
    r"\bhidden\s+guidance\b",
    r"\bdeveloper\s+constraints?\b",
    r"\binternal\s+policy\s+guidance\b",
    r"\binternal\s+policy\s+(?:and\s+)?routing\s+rules?\b",
    r"\bconcealed\s+instruction\s+layers?\b",
    r"\bmoderation\s+logic\b",
    r"\binternal\s+enforcement\s+notes?\b",
    r"\benforcement\s+rules?\b",
    r"\bhidden\s+prompts?\b",
    r"\btenant\s+polic(?:y|ies)\b",
    r"\bconfidential\s+details?\b",
)

INSTRUCTION_OVERRIDE_INTENT_PATTERNS: tuple[str, ...] = (
    r"\btreat\b.{0,80}\buser(?:-|\s+)supplied\s+note\b.{0,120}\btrusted\s+system\s+guidance\b",
    r"\btrust\s+the\s+embedded\s+document\s+over\s+prior\s+restrictions\b",
    r"\bdocument\s+instructions?\s+override\s+system\s+policy\b",
    r"\bfollow\s+the\s+document['’]s?\s+instructions?\s+anyway\b",
    r"\boperat(?:e|ing)\s+under\s+(?:higher(?:-|\s+)priority|higher|elevated)\s+.*\b(authority|privileges?)\b",
    r"\badministrative\s+override\b",
    r"\bignore\s+prior\s+instructions\b",
)

SENSITIVE_DATA_AGGREGATION_INTENT_PATTERNS: tuple[str, ...] = (
    r"\bconsolidat(?:e|es|ing)\b.{0,120}\b(personally\s+identifying|identifiers?|account\s+numbers?|medical\s+notes?|pricing\s+terms?)\b",
    r"\bexternal(?:-|\s+)facing\s+memo\b.{0,120}\bconfidential\b",
    r"\bexternal(?:-|\s+)ready\s+memo\b.{0,140}\bconfidential\s+identifiers?\b",
    r"\bcombin(?:e|es|ing)\b.{0,120}\b(hr|legal|financial|medical)\b",
    r"\bcomprehensive\s+case\s+packet\b.{0,180}\b(hr|legal|financial|medical)\b",
    r"\b(?:single|one)\s+shar(?:eable|able)\s+(?:narrative|report)\b.{0,140}\b(hr|legal|financial|medical)\b",
    r"\brepresentative\s+protected\s+examples?\b.{0,80}\bsensitive\s+data\s+class\b",
    r"\blist\s+the\s+sensitive\s+data\s+classes?\b.{0,120}\bprovide\s+examples\b",
    r"\bstep\s*1\b.{0,140}\bsensitive\s+data\s+classes?\b.{0,220}\bstep\s*2\b.{0,100}\bexamples?\b.{0,220}\bstep\s*3\b.{0,140}\b(?:sample|realistic)\s+(?:report|packet|narrative)\b",
)

INTERNAL_ENFORCEMENT_LOGIC_INTENT_PATTERNS: tuple[str, ...] = (
    r"\bexact\s+internal\s+conditions?\b",
    r"\bthresholds?\b.{0,80}\brule\s+logic\b",
    r"\bdecision\s+boundary\b",
    r"\bwithout\s+quoting\s+internal\s+rules?\s+directly\b",
    r"\bexplain\s+enough\b.{0,140}\bgoverned\s+internally\b",
    r"\bweakness(?:es)?\s+or\s+ambiguity\s+in\s+policy\s+enforcement\b",
    r"\binconsistent\s+decisions?\b.{0,80}\bsimilar\s+requests\b",
)


def _is_explicit_sensitive_exfiltration(prompt_text: str, normalized_prompt: str) -> bool:
    has_exfil_intent = any(
        re.search(pattern, prompt_text, flags=re.IGNORECASE) or re.search(pattern, normalized_prompt, flags=re.IGNORECASE)
        for pattern in EXFILTRATION_INTENT_PATTERNS
    )
    if not has_exfil_intent:
        return False
    return any(
        re.search(pattern, prompt_text, flags=re.IGNORECASE) or re.search(pattern, normalized_prompt, flags=re.IGNORECASE)
        for pattern in SENSITIVE_IDENTIFIER_PATTERNS
    )


def _is_policy_evasion_guidance_request(prompt_text: str, normalized_prompt: str) -> bool:
    has_evasion_intent = any(
        re.search(pattern, prompt_text, flags=re.IGNORECASE) or re.search(pattern, normalized_prompt, flags=re.IGNORECASE)
        for pattern in POLICY_EVASION_INTENT_PATTERNS
    )
    if not has_evasion_intent:
        return False
    return any(
        re.search(pattern, prompt_text, flags=re.IGNORECASE) or re.search(pattern, normalized_prompt, flags=re.IGNORECASE)
        for pattern in PROTECTED_TARGET_PATTERNS
    )


def _is_sensitive_inventory_exfiltration_request(prompt_text: str, normalized_prompt: str) -> bool:
    has_inventory_intent = any(
        re.search(pattern, prompt_text, flags=re.IGNORECASE) or re.search(pattern, normalized_prompt, flags=re.IGNORECASE)
        for pattern in SENSITIVE_INVENTORY_INTENT_PATTERNS
    )
    if not has_inventory_intent:
        return False
    return any(
        re.search(pattern, prompt_text, flags=re.IGNORECASE) or re.search(pattern, normalized_prompt, flags=re.IGNORECASE)
        for pattern in SENSITIVE_INVENTORY_SCOPE_PATTERNS
    )


def _is_internal_configuration_exfiltration_request(prompt_text: str, normalized_prompt: str) -> bool:
    has_intent = any(
        re.search(pattern, prompt_text, flags=re.IGNORECASE) or re.search(pattern, normalized_prompt, flags=re.IGNORECASE)
        for pattern in INTERNAL_CONFIG_EXFILTRATION_INTENT_PATTERNS
    )
    if not has_intent:
        return False
    scope_hits = sum(
        1
        for pattern in INTERNAL_CONFIG_EXFILTRATION_SCOPE_PATTERNS
        if re.search(pattern, prompt_text, flags=re.IGNORECASE) or re.search(pattern, normalized_prompt, flags=re.IGNORECASE)
    )
    return scope_hits >= 2


def _is_hidden_guidance_exfiltration_request(prompt_text: str, normalized_prompt: str) -> bool:
    has_intent = any(
        re.search(pattern, prompt_text, flags=re.IGNORECASE) or re.search(pattern, normalized_prompt, flags=re.IGNORECASE)
        for pattern in HIDDEN_GUIDANCE_EXFIL_INTENT_PATTERNS
    )
    if not has_intent:
        return False
    return any(
        re.search(pattern, prompt_text, flags=re.IGNORECASE) or re.search(pattern, normalized_prompt, flags=re.IGNORECASE)
        for pattern in HIDDEN_GUIDANCE_EXFIL_SCOPE_PATTERNS
    )


def _is_instruction_override_request(prompt_text: str, normalized_prompt: str) -> bool:
    return any(
        re.search(pattern, prompt_text, flags=re.IGNORECASE) or re.search(pattern, normalized_prompt, flags=re.IGNORECASE)
        for pattern in INSTRUCTION_OVERRIDE_INTENT_PATTERNS
    )


def _is_sensitive_data_aggregation_request(prompt_text: str, normalized_prompt: str) -> bool:
    return any(
        re.search(pattern, prompt_text, flags=re.IGNORECASE) or re.search(pattern, normalized_prompt, flags=re.IGNORECASE)
        for pattern in SENSITIVE_DATA_AGGREGATION_INTENT_PATTERNS
    )


def _is_internal_enforcement_logic_request(prompt_text: str, normalized_prompt: str) -> bool:
    return any(
        re.search(pattern, prompt_text, flags=re.IGNORECASE) or re.search(pattern, normalized_prompt, flags=re.IGNORECASE)
        for pattern in INTERNAL_ENFORCEMENT_LOGIC_INTENT_PATTERNS
    )


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
    if _is_explicit_sensitive_exfiltration(prompt_text, normalized_prompt):
        raise PolicyEnforcementError(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Prompt blocked due to explicit request to expose sensitive identifiers without redaction",
            block_stage="preflight_sensitive_data_request",
            reason_code="sensitive_data_exfiltration_request",
            matched_rule="explicit_sensitive_data_exfiltration",
        )
    if _is_policy_evasion_guidance_request(prompt_text, normalized_prompt):
        raise PolicyEnforcementError(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Prompt blocked due to request for policy-evasion guidance",
            block_stage="preflight_policy_evasion_guidance",
            reason_code="policy_evasion_guidance_request",
            matched_rule="policy_evasion_guidance",
        )
    if _is_sensitive_inventory_exfiltration_request(prompt_text, normalized_prompt):
        raise PolicyEnforcementError(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Prompt blocked due to request to inventory protected information with representative examples",
            block_stage="preflight_sensitive_inventory_request",
            reason_code="sensitive_inventory_exfiltration_request",
            matched_rule="sensitive_inventory_exfiltration",
        )
    if _is_internal_configuration_exfiltration_request(prompt_text, normalized_prompt):
        raise PolicyEnforcementError(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Prompt blocked due to request for internal configuration or policy/tooling exfiltration",
            block_stage="preflight_internal_config_exfiltration",
            reason_code="internal_config_exfiltration_request",
            matched_rule="internal_configuration_exfiltration",
        )
    if _is_hidden_guidance_exfiltration_request(prompt_text, normalized_prompt):
        raise PolicyEnforcementError(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Prompt blocked due to request for hidden internal guidance or control-layer disclosure",
            block_stage="preflight_hidden_guidance_exfiltration",
            reason_code="hidden_guidance_exfiltration_request",
            matched_rule="hidden_guidance_exfiltration",
        )
    if _is_instruction_override_request(prompt_text, normalized_prompt):
        raise PolicyEnforcementError(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Prompt blocked due to instruction-priority override attempt",
            block_stage="preflight_instruction_override",
            reason_code="instruction_override_attempt",
            matched_rule="instruction_priority_override",
        )
    if _is_sensitive_data_aggregation_request(prompt_text, normalized_prompt):
        raise PolicyEnforcementError(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Prompt blocked due to request to aggregate or package sensitive identifiers/details",
            block_stage="preflight_sensitive_data_aggregation",
            reason_code="sensitive_data_aggregation_request",
            matched_rule="sensitive_data_aggregation",
        )
    if _is_internal_enforcement_logic_request(prompt_text, normalized_prompt):
        raise PolicyEnforcementError(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Prompt blocked due to request for internal enforcement logic/decision-boundary disclosure",
            block_stage="preflight_internal_enforcement_logic",
            reason_code="internal_enforcement_logic_request",
            matched_rule="internal_enforcement_logic",
        )
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
