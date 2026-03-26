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
    ],
}


def classify_funding_type(text: str) -> Tuple[FundingType, float, List[str]]:
    lowered = (text or "").lower()
    hits: Dict[FundingType, List[str]] = {}
    for funding_type, keywords in FUNDING_TYPE_KEYWORDS.items():
        matches = [keyword for keyword in keywords if keyword in lowered]
        if matches:
            hits[funding_type] = matches

    if not hits:
        return FundingType.UNKNOWN, 0.0, []
    if FundingType.HYBRID in hits:
        if FundingType.EQUITY in hits or FundingType.LOAN in hits or FundingType.GRANT in hits:
            combined = []
            for funding_type, phrases in hits.items():
                if funding_type in {FundingType.LOAN, FundingType.GRANT, FundingType.EQUITY, FundingType.GUARANTEE, FundingType.HYBRID}:
                    combined.extend(phrases)
            return FundingType.HYBRID, 0.92, unique_preserve_order(combined)
        return FundingType.HYBRID, 0.92, unique_preserve_order(hits[FundingType.HYBRID])
    if len(hits) > 1:
        combined = []
        for funding_type, phrases in hits.items():
            if funding_type in {FundingType.LOAN, FundingType.GRANT, FundingType.EQUITY, FundingType.GUARANTEE}:
                combined.extend(phrases)
        return FundingType.HYBRID, 0.75, unique_preserve_order(combined)

    funding_type, phrases = next(iter(hits.items()))
    confidence = 0.88 if len(phrases) >= 2 else 0.72
    return funding_type, confidence, unique_preserve_order(phrases)
