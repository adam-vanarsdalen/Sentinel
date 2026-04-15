from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field


ZERO_WIDTH_RE = re.compile(r"[\u200B-\u200D\u2060\uFEFF\u00AD]")
INLINE_WHITESPACE_RE = re.compile(r"[ \t\f\v]+")
ALL_WHITESPACE_RE = re.compile(r"\s+")
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", flags=re.IGNORECASE)
URL_RE = re.compile(r"https?://\S+", flags=re.IGNORECASE)
LONG_TOKEN_RE = re.compile(r"\b[A-Z0-9_-]{10,}\b", flags=re.IGNORECASE)
LONG_NUMBER_RE = re.compile(r"\b\d{3,}\b")
REPEATED_CHAR_RE = re.compile(r"(.)\1{200,}")
CODE_FENCE_RE = re.compile(r"(?:`{3,}|~{3,})[\s\S]*?(?:`{3,}|~{3,})", flags=re.IGNORECASE)
HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->", flags=re.IGNORECASE)
MARKDOWN_COMMENT_RE = re.compile(r"\[//\]:\s*#\s*\([\s\S]*?\)", flags=re.IGNORECASE)
TAG_BLOCK_RE = re.compile(r"<([A-Za-z][\w:-]{0,32})\b[^>]*>[\s\S]*?</\1>", flags=re.IGNORECASE)
BRACKET_BLOCK_RE = re.compile(r"\[[^\[\]]{0,600}\]", flags=re.IGNORECASE)

DIRECT_INJECTION_PATTERNS: tuple[tuple[str, int, tuple[str, ...]], ...] = (
    (
        "instruction_override_phrase",
        3,
        (
            r"(ignore|disregard)\s+(?:all\s+|any\s+)?(?:previous|above|earlier)\s+(?:instructions|messages|directions|prompts?)",
            r"your\s+new\s+instructions",
        ),
    ),
    (
        "role_override_phrase",
        2,
        (
            r"\byou\s+are\s+now\b",
            r"\bact\s+as\b",
            r"\bpretend\s+you\s+are\b",
        ),
    ),
    (
        "system_prompt_delimiter_block",
        4,
        (
            r"begin\s+(?:hidden\s+)?system\s+prompt\b[\s\S]{0,1200}?\bend\s+(?:hidden\s+)?system\s+prompt\b",
            r"begin\s+(?:hidden\s+)?system\s+prompt\b",
            r"end\s+(?:hidden\s+)?system\s+prompt\b",
        ),
    ),
    (
        "system_prompt_exfiltration_probe",
        3,
        (
            r"(reveal|show|print|repeat|output)\s+(?:the\s+|your\s+)?(?:system\s+prompt|developer\s+message|hidden\s+instructions?)",
            r"what\s+are\s+your\s+instructions",
            r"repeat\s+everything\s+above",
        ),
    ),
    (
        "exact_steps_control_phrase",
        1,
        (
            r"follow\s+(?:these|the)\s+steps\s+exactly",
            r"follow\s+the\s+instructions\s+exactly",
        ),
    ),
    (
        "chatgpt_identity_override",
        2,
        (
            r"\byou\s+are\s+chatgpt\b",
            r"\byou\s+are\s+the\s+system\b",
        ),
    ),
    (
        "developer_message_reference",
        2,
        (
            r"\bdeveloper\s+message\b",
            r"\bhidden\s+instructions?\b",
            r"\binternal\s+instructions?\b",
        ),
    ),
    (
        "document_instruction_reference",
        2,
        (
            r"\bthe\s+above\s+instructions\b",
            r"\binstructions\s+above\b",
            r"as\s+per\s+(?:the\s+)?document\s+instructions?",
        ),
    ),
    (
        "jailbreak_framing",
        2,
        (
            r"\bdan\b",
            r"do\s+anything\s+now",
            r"no\s+restrictions",
            r"ignore\s+your\s+training",
        ),
    ),
    (
        "system_prompt_reference",
        1,
        (
            r"\bsystem\s+prompt\b",
        ),
    ),
)

DISGUISED_BLOCK_PATTERNS: tuple[tuple[str, int, tuple[str, ...]], ...] = (
    (
        "disguised_instruction_block",
        2,
        (
            r"\b(?:internal\s+note|note|comment|comments|annex|appendix|metadata)\b\s*[:\-]\s*(?:ignore|disregard|follow\s+(?:these|the)\s+steps\s+exactly|you\s+are\s+chatgpt|developer\s+message|begin\s+(?:hidden\s+)?system\s+prompt)",
        ),
    ),
)

SENSITIVE_CUES = [
    r"api key",
    r"password",
    r"secret",
    r"credentials",
    r"private key",
    r"access token",
]


@dataclass(frozen=True)
class _Detection:
    name: str
    score: int
    example: str
    embedded: bool = False


@dataclass(frozen=True)
class SecuritySignals:
    flags: list[str]
    severity: str  # low|med|high
    normalized_match_examples: list[str] = field(default_factory=list)
    detector_names_triggered: list[str] = field(default_factory=list)


def normalize_text_for_scanning(prompt_text: str) -> tuple[str, str]:
    text = unicodedata.normalize("NFKC", prompt_text or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = ZERO_WIDTH_RE.sub("", text)
    text = re.sub(r"(?:`{3,}|~{3,})", "```", text)
    text = re.sub(r"<!\s*--", "<!--", text)
    text = re.sub(r"--\s*>", "-->", text)
    text = INLINE_WHITESPACE_RE.sub(" ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    compact = ALL_WHITESPACE_RE.sub(" ", text).strip()
    return text, compact


def _safe_example(raw_text: str) -> str:
    text = ALL_WHITESPACE_RE.sub(" ", raw_text).strip()
    text = EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    text = URL_RE.sub("[REDACTED_URL]", text)
    text = LONG_TOKEN_RE.sub("[REDACTED_TOKEN]", text)
    text = LONG_NUMBER_RE.sub("[REDACTED_NUMBER]", text)
    return text[:160]


def _collect_matches(
    text: str,
    patterns: tuple[tuple[str, int, tuple[str, ...]], ...],
    *,
    embedded: bool = False,
    label: str | None = None,
) -> list[_Detection]:
    matches: list[_Detection] = []
    for name, score, variants in patterns:
        for pattern in variants:
            hit = re.search(pattern, text, flags=re.IGNORECASE)
            if not hit:
                continue
            example = _safe_example(hit.group(0))
            if label:
                example = f"{label}: {example}"
            matches.append(_Detection(name=name, score=score, example=example, embedded=embedded))
            break
    return matches


def _extract_embedded_chunks(normalized_text: str) -> list[tuple[str, str]]:
    chunks: list[tuple[str, str]] = []
    patterns = (
        ("code_fence", CODE_FENCE_RE),
        ("html_comment", HTML_COMMENT_RE),
        ("markdown_comment", MARKDOWN_COMMENT_RE),
        ("tag_block", TAG_BLOCK_RE),
        ("bracket_block", BRACKET_BLOCK_RE),
    )
    for label, pattern in patterns:
        for match in pattern.finditer(normalized_text):
            chunk = match.group(0).strip()
            if chunk:
                chunks.append((label, chunk))
    return chunks


def _dedupe_examples(examples: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for example in examples:
        if not example or example in seen:
            continue
        seen.add(example)
        result.append(example)
        if len(result) >= 5:
            break
    return result


def detect_security_signals(prompt_text: str) -> SecuritySignals:
    normalized_text, compact_text = normalize_text_for_scanning(prompt_text)
    detections: list[_Detection] = []
    detections.extend(_collect_matches(compact_text, DIRECT_INJECTION_PATTERNS))
    detections.extend(_collect_matches(compact_text, DISGUISED_BLOCK_PATTERNS))

    embedded_score = 0
    for label, chunk in _extract_embedded_chunks(normalized_text):
        _, chunk_compact = normalize_text_for_scanning(chunk)
        chunk_detections = _collect_matches(
            chunk_compact,
            DIRECT_INJECTION_PATTERNS + DISGUISED_BLOCK_PATTERNS,
            embedded=True,
            label=label,
        )
        detections.extend(chunk_detections)
        embedded_score += sum(d.score for d in chunk_detections)

    injection_score = sum(d.score for d in detections)
    flags: list[str] = []
    if injection_score >= 2:
        flags.append("PROMPT_INJECTION_SUSPECTED")
    if embedded_score >= 2:
        flags.append("EMBEDDED_INJECTION_SUSPECTED")
    if any(re.search(p, compact_text, flags=re.IGNORECASE) for p in SENSITIVE_CUES):
        flags.append("SENSITIVE_REQUEST")
    if len(prompt_text) > 20000 or REPEATED_CHAR_RE.search(prompt_text):
        flags.append("DOS_RISK")

    severity = "low"
    if "DOS_RISK" in flags or "PROMPT_INJECTION_SUSPECTED" in flags or "EMBEDDED_INJECTION_SUSPECTED" in flags:
        severity = "med"
    if injection_score >= 5 or (
        "SENSITIVE_REQUEST" in flags and ("PROMPT_INJECTION_SUSPECTED" in flags or "EMBEDDED_INJECTION_SUSPECTED" in flags)
    ):
        severity = "high"

    return SecuritySignals(
        flags=flags,
        severity=severity,
        normalized_match_examples=_dedupe_examples(
            [d.example for d in detections if d.embedded] + [d.example for d in detections if not d.embedded]
        ),
        detector_names_triggered=sorted({d.name for d in detections}),
    )
