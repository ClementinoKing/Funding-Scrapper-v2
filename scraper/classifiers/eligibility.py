"""Eligibility criteria extraction helpers."""

from __future__ import annotations

import re
from typing import List

from scraper.utils.text import clean_text, sentence_chunks, split_lines, unique_preserve_order


ELIGIBILITY_HEADING_TERMS = (
    "eligibility criteria",
    "qualifying criteria",
    "qualification criteria",
    "who qualifies",
    "who can apply",
    "applicant requirements",
    "funding requirements",
    "minimum requirements",
    "compliance requirements",
    "mandatory requirements",
    "requirements",
    "criteria",
    "conditions",
    "terms and conditions",
    "selection criteria",
    "application criteria",
    "funding criteria",
    "investment criteria",
)

_ELIGIBILITY_SPLIT_PATTERN = re.compile(r"[;•·|]\s*")
_ELIGIBILITY_HEADING_PREFIX_PATTERN = re.compile(
    r"^(?:"
    + "|".join(re.escape(term) for term in ELIGIBILITY_HEADING_TERMS)
    + r")\s*[:\-–—]\s*",
    re.I,
)
_LIST_MARKER_PATTERN = re.compile(r"^(?:\d+[\).:-]?\s*|[-*•]\s*)")
_ELIGIBILITY_REQUIREMENT_HINTS = (
    "must",
    "must be",
    "must submit",
    "required",
    "required to",
    "should",
    "shall",
    "eligible",
    "qualify",
    "qualified",
    "applicant",
    "applicants",
    "business must",
    "enterprise must",
    "minimum",
    "maximum",
    "at least",
    "not less than",
    "no less than",
    "provide",
    "submit",
    "demonstrate",
    "comply",
    "compliance",
    "condition",
    "criteria",
)
_ELIGIBILITY_ALLOWLIST_HINTS = (
    "black-owned",
    "majority black-owned",
    "women-owned",
    "female-owned",
    "youth-owned",
    "minority-owned",
    "smmes",
    "sme",
    "registered",
    "registration",
    "tax clearance",
    "operationally involved",
    "commercial viability",
    "sustainability",
    "financial statements",
    "business plan",
    "proof of",
    "valid",
)
_ELIGIBILITY_EXCLUDE_HINTS = (
    "loan term",
    "repayment",
    "repay",
    "payback",
    "tenor",
    "interest rate",
    "interest",
    "amount",
    "funding amount",
    "contact",
    "email",
    "phone",
    "call",
    "website",
    "brochure",
    "download",
    "marketing",
    "overview",
    "news",
    "press release",
    "media release",
)


def _split_fragments(text: str) -> List[str]:
    fragments: List[str] = []
    for line in split_lines(text):
        parts = [line]
        if _ELIGIBILITY_SPLIT_PATTERN.search(line):
            parts = _ELIGIBILITY_SPLIT_PATTERN.split(line)
        for part in parts:
            for sentence in sentence_chunks(part) or [part]:
                cleaned = clean_text(sentence)
                if cleaned:
                    cleaned = _LIST_MARKER_PATTERN.sub("", cleaned)
                    cleaned = _ELIGIBILITY_HEADING_PREFIX_PATTERN.sub("", cleaned)
                    cleaned = clean_text(cleaned)
                    if cleaned:
                        fragments.append(cleaned)
    return unique_preserve_order(fragments)


def _looks_like_eligibility_statement(fragment: str) -> bool:
    lowered = fragment.lower()
    if any(term in lowered for term in _ELIGIBILITY_EXCLUDE_HINTS):
        if not any(term in lowered for term in _ELIGIBILITY_REQUIREMENT_HINTS):
            return False
    if any(term in lowered for term in _ELIGIBILITY_REQUIREMENT_HINTS):
        return True
    if any(term in lowered for term in _ELIGIBILITY_ALLOWLIST_HINTS):
        return True
    return False


def extract_eligibility_criteria(text: str) -> List[str]:
    cleaned_text = clean_text(text)
    if not cleaned_text:
        return []

    fragments = _split_fragments(cleaned_text)
    criteria: List[str] = []
    for fragment in fragments:
        normalized = clean_text(fragment)
        if not normalized:
            continue
        word_count = len(normalized.split())
        if word_count < 2:
            continue
        if _looks_like_eligibility_statement(normalized):
            criteria.append(normalized)
    return unique_preserve_order(criteria)
