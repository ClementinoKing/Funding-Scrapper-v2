"""Funding type classification helpers."""

from __future__ import annotations

from typing import Dict, List, Tuple

from scraper.schemas import FundingType
from scraper.utils.text import unique_preserve_order


FUNDING_TYPE_KEYWORDS: Dict[FundingType, List[str]] = {
    FundingType.GRANT: ["grant", "grant funding", "matching grant", "micro-grant", "non-repayable"],
    FundingType.LOAN: ["loan", "term loan", "working capital loan", "bridging loan", "asset finance", "credit facility"],
    FundingType.EQUITY: ["equity", "equity finance", "equity investment", "minority stake", "venture capital"],
    FundingType.GUARANTEE: ["guarantee", "credit guarantee", "partial guarantee", "risk-sharing"],
    FundingType.HYBRID: [
        "blended finance",
        "hybrid",
        "debt + grant",
        "grant and loan",
        "equity and debt",
        "debt",
        "quasi-equity",
        "quasi equity",
        "debt and equity",
        "debt, quasi-equity and equity",
        "debt and grant",
        "loan and grant",
        "grant and loan",
        "loan and equity",
        "equity and grant",
        "debt and hybrid",
        "grant loan equity",
    ],
}

HYBRID_MARKERS = (
    "hybrid",
    "blended finance",
    "mezzanine",
    "convertible",
    "convertible note",
    "convertible instrument",
    "quasi-equity",
    "quasi equity",
    "debt",
)

SEPARATOR_NORMALIZATION_RE = (
    ("•", " "),
    ("+", " "),
    ("/", " "),
    ("&", " "),
)


def _normalized_text(text: str) -> str:
    lowered = (text or "").lower()
    for old, new in SEPARATOR_NORMALIZATION_RE:
        lowered = lowered.replace(old, new)
    lowered = " ".join(lowered.split())
    return lowered


def classify_funding_type(text: str) -> Tuple[FundingType, float, List[str]]:
    lowered = _normalized_text(text or "")
    hits: Dict[FundingType, List[str]] = {}
    for funding_type, keywords in FUNDING_TYPE_KEYWORDS.items():
        matches = [keyword for keyword in keywords if keyword in lowered]
        if matches:
            hits[funding_type] = matches

    if not hits:
        return FundingType.UNKNOWN, 0.0, []

    explicit_hybrid = any(marker in lowered for marker in HYBRID_MARKERS if marker != "debt")
    has_debt = any(keyword in lowered for keyword in FUNDING_TYPE_KEYWORDS[FundingType.LOAN]) or "debt" in lowered
    has_grant = FundingType.GRANT in hits
    has_loan = FundingType.LOAN in hits or has_debt
    has_equity = FundingType.EQUITY in hits
    has_guarantee = FundingType.GUARANTEE in hits

    if explicit_hybrid or sum(bool(flag) for flag in (has_grant, has_loan, has_equity, has_guarantee, FundingType.HYBRID in hits)) > 1:
        combined = []
        for funding_type, phrases in hits.items():
            if funding_type in {FundingType.LOAN, FundingType.GRANT, FundingType.EQUITY, FundingType.GUARANTEE, FundingType.HYBRID}:
                combined.extend(phrases)
        if has_debt and "debt" not in combined:
            combined.append("debt")
        if not combined and "hybrid" in lowered:
            combined.append("hybrid")
        return FundingType.HYBRID, 0.93 if explicit_hybrid else 0.82, unique_preserve_order(combined)

    funding_type, phrases = next(iter(hits.items()))
    confidence = 0.88 if len(phrases) >= 2 else 0.72
    return funding_type, confidence, unique_preserve_order(phrases)
