from __future__ import annotations

import re
from dataclasses import dataclass


PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
DATE_RE = re.compile(r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b")
MATTER_RE = re.compile(r"\b(?:matter|case|docket)\s*(?:no\.?|#)\s*[A-Z0-9-]{3,}\b", re.IGNORECASE)
IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")
ROUTING_RE = re.compile(r"\b(?:routing|aba)\s*(?:number|no\.?|#)?\s*[:#]?\s*\d{9}\b", re.IGNORECASE)
ACCOUNT_RE = re.compile(r"\b(?:account|acct)\s*(?:number|no\.?|#)?\s*[:#]?\s*\d{6,17}\b", re.IGNORECASE)
PASSPORT_RE = re.compile(r"\bpassport\s*(?:number|no\.?|#)?\s*[:#]?\s*[A-Z0-9]{6,12}\b", re.IGNORECASE)
DRIVER_LICENSE_RE = re.compile(r"\b(?:driver'?s?\s*license|dl)\s*(?:number|no\.?|#)?\s*[:#]?\s*[A-Z0-9-]{6,20}\b", re.IGNORECASE)


@dataclass(frozen=True)
class PhiScanResult:
    score: int
    redacted_snippet: str
    matches: list[str]


def _mask(pattern: re.Pattern, text: str, mask: str) -> tuple[str, bool]:
    new, n = pattern.subn(mask, text)
    return new, n > 0


def scan_phi(text: str, *, snippet_len: int = 200) -> PhiScanResult:
    matches: list[str] = []
    score = 0
    redacted = text

    redacted, hit = _mask(EMAIL_RE, redacted, "[EMAIL]")
    if hit:
        matches.append("EMAIL")
        score += 25

    redacted, hit = _mask(PHONE_RE, redacted, "[PHONE]")
    if hit:
        matches.append("PHONE")
        score += 20

    redacted, hit = _mask(SSN_RE, redacted, "[SSN]")
    if hit:
        matches.append("SSN")
        score += 40

    redacted, hit = _mask(MATTER_RE, redacted, "[MATTER_NO]")
    if hit:
        matches.append("MATTER_NO")
        score += 20

    redacted, hit = _mask(IBAN_RE, redacted, "[IBAN]")
    if hit:
        matches.append("IBAN")
        score += 35

    redacted, hit = _mask(ROUTING_RE, redacted, "[ROUTING]")
    if hit:
        matches.append("ROUTING")
        score += 30

    redacted, hit = _mask(ACCOUNT_RE, redacted, "[ACCOUNT]")
    if hit:
        matches.append("ACCOUNT")
        score += 25

    redacted, hit = _mask(PASSPORT_RE, redacted, "[PASSPORT]")
    if hit:
        matches.append("PASSPORT")
        score += 25

    redacted, hit = _mask(DRIVER_LICENSE_RE, redacted, "[DRIVER_LICENSE]")
    if hit:
        matches.append("DRIVER_LICENSE")
        score += 25

    redacted, hit = _mask(DATE_RE, redacted, "[DATE]")
    if hit:
        matches.append("DATE")
        score += 10

    score = max(0, min(100, score))
    snippet = redacted[:snippet_len]
    return PhiScanResult(score=score, redacted_snippet=snippet, matches=matches)


def confidentiality_exposure_level(score: int | None) -> str | None:
    """
    Map the existing 0-100 heuristic score to a human-friendly level for UI display.
    """
    if score is None:
        return None
    if score < 34:
        return "LOW"
    if score <= 66:
        return "MEDIUM"
    return "HIGH"
