"""Repayment and payback extraction helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence, Tuple

from scraper.schemas import RepaymentFrequency
from scraper.utils.text import clean_text, sentence_chunks, unique_preserve_order


PAYBACK_KEYWORDS = (
    "repayment",
    "repay",
    "repayable",
    "pay back",
    "payback",
    "loan term",
    "facility term",
    "repayment term",
    "tenor",
    "tenure",
    "duration",
    "repayment period",
    "loan duration",
    "payment period",
    "instalment",
    "installment",
    "moratorium",
    "grace period",
    "deferred payment",
    "repayment holiday",
    "bullet repayment",
    "balloon payment",
    "monthly repayment",
    "quarterly repayment",
    "annual repayment",
    "cash flow",
    "once-off",
    "once off",
)


_MONTHS_IN_YEAR = 12
_RANGE_PATTERNS = (
    re.compile(
        r"\b(?:between|from)\s*(\d+(?:\.\d+)?)\s*(?:months?|years?)?\s*(?:and|to|-)\s*(\d+(?:\.\d+)?)\s*(months?|years?)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:between|from)\s*(\d+(?:\.\d+)?)\s*(months?|years?)\s*(?:and|to|-)\s*(\d+(?:\.\d+)?)\s*(months?|years?)\b",
        re.I,
    ),
    re.compile(
        r"\b(\d+(?:\.\d+)?)\s*(months?|years?)\s*(?:to|-|and)\s*(\d+(?:\.\d+)?)\s*(months?|years?)\b",
        re.I,
    ),
    re.compile(r"\b(?:up to|maximum of|max(?:imum)?(?: term)?(?: of)?|not exceeding)\s*(\d+(?:\.\d+)?)\s*(months?|years?)\b", re.I),
    re.compile(
        r"\b(?:repayable over|over|for a period of|term of|tenor of|duration of|repayment period of|loan term of|facility term of)\s*(\d+(?:\.\d+)?)\s*(months?|years?)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:repayment term|loan term|facility term|tenor|tenure|duration|repayment period|loan duration|payment period|payback)\s*(?:of|is|are|for|up to|over)?\s*(\d+(?:\.\d+)?)\s*(months?|years?)\b",
        re.I,
    ),
)

_GRACE_PATTERNS = (
    re.compile(
        r"\b(?:grace period|moratorium|repayment holiday|deferred payment)\b(?:[^0-9]{0,30})?(\d+(?:\.\d+)?)\s*(months?|years?)\b",
        re.I,
    ),
    re.compile(
        r"\b(\d+(?:\.\d+)?)\s*(months?|years?)\s*(?:grace period|moratorium|repayment holiday|deferred payment)\b",
        re.I,
    ),
)

_FREQUENCY_PATTERNS = (
    (
        RepaymentFrequency.MONTHLY,
        (
            "monthly repayment",
            "monthly repayments",
            "monthly instalment",
            "monthly installments",
            "repay monthly",
            "per month",
            "every month",
            "month-end repayment",
        ),
    ),
    (
        RepaymentFrequency.QUARTERLY,
        (
            "quarterly repayment",
            "quarterly repayments",
            "quarterly instalment",
            "quarterly installments",
            "every quarter",
            "every 3 months",
            "every three months",
            "three-monthly",
            "three monthly",
        ),
    ),
    (
        RepaymentFrequency.ANNUALLY,
        (
            "annual repayment",
            "annually",
            "annual instalment",
            "annual installments",
            "yearly",
            "per annum",
            "every year",
        ),
    ),
    (
        RepaymentFrequency.ONCE_OFF,
        (
            "once-off",
            "once off",
            "bullet repayment",
            "bullet payment",
            "balloon payment",
            "lump sum repayment",
            "single repayment",
            "repay in full at maturity",
        ),
    ),
    (
        RepaymentFrequency.FLEXIBLE,
        (
            "flexible schedule",
            "flexible repayment",
            "variable repayment",
            "variable schedule",
            "cash flow linked",
            "linked to cash flow",
            "cash flow",
            "repayment holiday",
            "moratorium",
            "deferred payment",
        ),
    ),
    (
        RepaymentFrequency.WEEKLY,
        (
            "weekly repayment",
            "weekly repayments",
            "weekly instalment",
            "weekly installments",
            "per week",
            "every week",
        ),
    ),
    (
        RepaymentFrequency.VARIABLE,
        (
            "case-by-case repayment",
            "case by case repayment",
            "tailored repayment",
            "negotiated repayment",
        ),
    ),
)


@dataclass
class PaybackExtraction:
    raw_text: Optional[str] = None
    term_min_months: Optional[int] = None
    term_max_months: Optional[int] = None
    structure: Optional[str] = None
    grace_period_months: Optional[int] = None
    repayment_frequency: RepaymentFrequency = RepaymentFrequency.UNKNOWN
    confidence: float = 0.0
    snippets: List[str] = field(default_factory=list)


def _months_from_value(value: float, unit: str) -> int:
    return int(round(value * _MONTHS_IN_YEAR)) if unit.lower().startswith("year") else int(round(value))


def _extract_numeric_pair(sentence: str) -> Tuple[Optional[int], Optional[int], Optional[str], float]:
    for pattern in _RANGE_PATTERNS:
        match = pattern.search(sentence)
        if not match:
            continue
        groups = match.groups()
        if len(groups) == 3 and groups[2]:
            first = _months_from_value(float(groups[0]), groups[2])
            second = _months_from_value(float(groups[1]), groups[2])
            return first, second, clean_text(match.group(0)), 0.82
        if len(groups) == 4 and groups[2]:
            first = _months_from_value(float(groups[0]), groups[1])
            second = _months_from_value(float(groups[2]), groups[3])
            return first, second, clean_text(match.group(0)), 0.82
        if len(groups) == 2 and groups[1]:
            value = _months_from_value(float(groups[0]), groups[1])
            source = clean_text(match.group(0))
            lowered = source.lower()
            if any(term in lowered for term in ("up to", "maximum", "max", "not exceeding")):
                return None, value, source, 0.8
            return value, value, source, 0.84
    return None, None, None, 0.0


def _extract_grace_period(sentence: str) -> Tuple[Optional[int], Optional[str], float]:
    for pattern in _GRACE_PATTERNS:
        match = pattern.search(sentence)
        if not match:
            continue
        value = _months_from_value(float(match.group(1)), match.group(2))
        return value, clean_text(match.group(0)), 0.78
    return None, None, 0.0


def _classify_frequency(text: str) -> Tuple[RepaymentFrequency, Optional[str], float]:
    lowered = (text or "").lower()
    for frequency, phrases in _FREQUENCY_PATTERNS:
        for phrase in phrases:
            if phrase in lowered:
                return frequency, phrase, 0.72
    return RepaymentFrequency.UNKNOWN, None, 0.0


def _classify_structure(text: str, frequency: RepaymentFrequency) -> Tuple[Optional[str], Optional[str], float]:
    lowered = (text or "").lower()
    structure_rules: Sequence[Tuple[Iterable[str], str]] = (
        (
            ("interest-only", "interest only", "principal repayment", "capital repayment"),
            "interest-only period then principal repayment",
        ),
        (
            ("bullet repayment", "bullet payment", "balloon payment", "lump sum repayment", "single repayment", "once-off"),
            "bullet repayment",
        ),
        (
            ("repayment linked to cash flow", "linked to cash flow", "cash flow linked", "cash flow"),
            "repayment linked to cash flow",
        ),
        (
            ("monthly repayment", "monthly repayments", "monthly instalment", "monthly installments"),
            "monthly instalments",
        ),
        (
            ("quarterly repayment", "quarterly repayments", "quarterly instalment", "quarterly installments"),
            "quarterly repayments",
        ),
        (
            ("annual repayment", "annually", "annual instalment", "annual installments", "yearly", "per annum"),
            "annual repayments",
        ),
        (
            ("weekly repayment", "weekly repayments", "weekly instalment", "weekly installments"),
            "weekly repayments",
        ),
        (
            ("moratorium", "grace period", "repayment holiday", "deferred payment"),
            "moratorium applies",
        ),
    )
    for phrases, label in structure_rules:
        if any(phrase in lowered for phrase in phrases):
            return label, label, 0.68
    if frequency == RepaymentFrequency.ONCE_OFF:
        return "bullet repayment", "bullet repayment", 0.65
    if frequency == RepaymentFrequency.FLEXIBLE:
        return "flexible repayment schedule", "flexible repayment schedule", 0.6
    if frequency == RepaymentFrequency.MONTHLY:
        return "monthly instalments", "monthly instalments", 0.58
    if frequency == RepaymentFrequency.QUARTERLY:
        return "quarterly repayments", "quarterly repayments", 0.58
    if frequency == RepaymentFrequency.ANNUALLY:
        return "annual repayments", "annual repayments", 0.58
    return None, None, 0.0


def extract_payback_details(text: str) -> PaybackExtraction:
    cleaned_text = clean_text(text)
    if not cleaned_text:
        return PaybackExtraction()

    sentences = [sentence for sentence in sentence_chunks(cleaned_text) if sentence]
    candidate_sentences = [
        sentence
        for sentence in sentences
        if (
            any(keyword in sentence.lower() for keyword in PAYBACK_KEYWORDS)
            or any(pattern.search(sentence) for pattern in _RANGE_PATTERNS)
            or any(pattern.search(sentence) for pattern in _GRACE_PATTERNS)
            or any(
                phrase in sentence.lower()
                for _frequency, phrases in _FREQUENCY_PATTERNS
                for phrase in phrases
            )
        )
    ]
    if not candidate_sentences:
        return PaybackExtraction()

    raw_text = unique_preserve_order(candidate_sentences)
    raw_text_value = " ".join(raw_text) if raw_text else None

    term_min: Optional[int] = None
    term_max: Optional[int] = None
    term_snippets: List[str] = []
    grace_period_months: Optional[int] = None
    grace_snippet: Optional[str] = None
    confidence = 0.25

    for sentence in candidate_sentences:
        sentence_term_min, sentence_term_max, sentence_snippet, sentence_confidence = _extract_numeric_pair(sentence)
        if sentence_snippet:
            term_snippets.append(sentence_snippet)
            if sentence_term_min is not None and (term_min is None or sentence_term_min < term_min):
                term_min = sentence_term_min
            if sentence_term_max is not None and (term_max is None or sentence_term_max > term_max):
                term_max = sentence_term_max
            confidence = max(confidence, sentence_confidence)

        sentence_grace_period, sentence_grace_snippet, sentence_grace_confidence = _extract_grace_period(sentence)
        if sentence_grace_snippet and grace_period_months is None:
            grace_period_months = sentence_grace_period
            grace_snippet = sentence_grace_snippet
            confidence = max(confidence, sentence_grace_confidence)

    if term_min is not None and term_max is not None and term_min > term_max:
        term_min, term_max = term_max, term_min
    elif term_min is None and term_max is not None:
        term_min = None
    elif term_max is None and term_min is not None:
        term_max = term_min

    frequency, frequency_snippet, frequency_confidence = _classify_frequency(raw_text_value or cleaned_text)
    confidence = max(confidence, frequency_confidence)

    structure, structure_snippet, structure_confidence = _classify_structure(raw_text_value or cleaned_text, frequency)
    confidence = max(confidence, structure_confidence)

    if term_min is not None or term_max is not None:
        confidence = min(1.0, confidence + 0.25)
    if grace_period_months is not None:
        confidence = min(1.0, confidence + 0.08)
    if structure is not None:
        confidence = min(1.0, confidence + 0.08)
    if frequency != RepaymentFrequency.UNKNOWN:
        confidence = min(1.0, confidence + 0.07)

    snippets = unique_preserve_order(
        [
            *term_snippets,
            *([grace_snippet] if grace_snippet else []),
            *([frequency_snippet] if frequency_snippet else []),
            *([structure_snippet] if structure_snippet else []),
        ]
    )

    if not raw_text_value and not snippets:
        return PaybackExtraction()

    return PaybackExtraction(
        raw_text=raw_text_value,
        term_min_months=term_min,
        term_max_months=term_max,
        structure=structure,
        grace_period_months=grace_period_months,
        repayment_frequency=frequency,
        confidence=round(min(1.0, confidence), 4),
        snippets=snippets,
    )
