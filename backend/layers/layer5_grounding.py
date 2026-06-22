"""Layer 5: Grounding — RAG verification, hallucination detection, confidence scoring."""
from __future__ import annotations

import re

from schemas.proxy import GroundingResult, ModelResponse, PipelineRequest


def _split_claims(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in sentences if len(s.strip()) > 20]


def _score_claim(claim: str, sources: list[str]) -> float:
    if not sources:
        return 0.0
    claim_words = set(claim.lower().split())
    best = 0.0
    for src in sources:
        src_words = set(src.lower().split())
        if not src_words:
            continue
        overlap = len(claim_words & src_words) / max(len(claim_words), 1)
        if overlap > best:
            best = overlap
    return best


async def layer5_ground(
    req: PipelineRequest,
    response: ModelResponse,
    sources: list[str] | None = None,
    block_threshold: float = 0.5,
    warn_threshold: float = 0.8,
) -> GroundingResult:
    """Verify model response against source documents."""
    if not sources:
        return GroundingResult(
            score=1.0,
            block_threshold=block_threshold,
            warn_threshold=warn_threshold,
            grounding_applicable=False,
        )

    claims = _split_claims(response.content)
    if not claims:
        return GroundingResult(
            score=1.0,
            block_threshold=block_threshold,
            warn_threshold=warn_threshold,
            grounding_applicable=True,
        )

    grounded: list[str] = []
    ungrounded: list[str] = []

    for claim in claims:
        score = _score_claim(claim, sources)
        if score >= 0.3:
            grounded.append(claim)
        else:
            ungrounded.append(claim)

    overall = len(grounded) / len(claims) if claims else 1.0

    return GroundingResult(
        score=round(overall, 3),
        block_threshold=block_threshold,
        warn_threshold=warn_threshold,
        grounded_claims=grounded,
        ungrounded_claims=ungrounded,
        grounding_applicable=True,
    )
