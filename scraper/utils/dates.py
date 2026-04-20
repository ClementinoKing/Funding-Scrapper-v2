"""Date and deadline parsing utilities."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Dict, Optional

import dateparser
from dateparser.search import search_dates

from scraper.utils.text import clean_text, sentence_chunks


OPEN_PATTERNS = [
    "open year-round",
    "open year round",
    "accept applications anytime",
    "accepting applications anytime",
    "applications are open",
    "always open",
    "apply anytime",
]
ROLLING_PATTERNS = [
    "rolling basis",
    "rolling applications",
    "applications are considered on a rolling basis",
    "reviewed on a rolling basis",
]
FIXED_HINTS = [
    "deadline",
    "applications close",
    "closing date",
    "closes on",
    "close on",
    "submissions close",
]

MONTH_NAME_PATTERN = re.compile(
    r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|"
    r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b",
    re.I,
)
NUMERIC_DATE_PATTERN = re.compile(
    r"\b(?:\d{1,2}[\/\-]\d{1,2}(?:[\/\-]\d{2,4})?|\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2})\b"
)


def _has_explicit_date_shape(text: str) -> bool:
    candidate = clean_text(text)
    if not candidate:
        return False
    if "%" in candidate:
        return False
    if MONTH_NAME_PATTERN.search(candidate):
        return True
    if NUMERIC_DATE_PATTERN.search(candidate):
        return True
    return False


def parse_deadline_info(text: str, relative_base: Optional[datetime] = None) -> Dict[str, object]:
    clean = clean_text(text)
    lowered = clean.lower()
    if not clean:
        return {"deadline_type": "Unknown", "deadline_date": None, "snippet": None, "confidence": 0.0}

    for pattern in OPEN_PATTERNS:
        if pattern in lowered:
            return {"deadline_type": "Open", "deadline_date": None, "snippet": pattern, "confidence": 0.9}
    for pattern in ROLLING_PATTERNS:
        if pattern in lowered:
            return {"deadline_type": "Rolling", "deadline_date": None, "snippet": pattern, "confidence": 0.88}

    settings = {
        "PREFER_DATES_FROM": "future",
        "DATE_ORDER": "DMY",
        "RELATIVE_BASE": relative_base or datetime.utcnow(),
        "RETURN_AS_TIMEZONE_AWARE": False,
    }

    candidate_sentences = [
        sentence
        for sentence in sentence_chunks(clean)
        if any(hint in sentence.lower() for hint in FIXED_HINTS)
    ]
    if not candidate_sentences:
        candidate_sentences = sentence_chunks(clean)[:12]

    for sentence in candidate_sentences:
        match = search_dates(sentence, settings=settings, languages=["en"])
        if not match:
            continue
        if not _has_explicit_date_shape(sentence):
            continue
        for found_text, found_date in match:
            if found_date and _has_explicit_date_shape(found_text):
                return {
                    "deadline_type": "FixedDate",
                    "deadline_date": found_date.date(),
                    "snippet": sentence,
                    "confidence": 0.9 if any(hint in sentence.lower() for hint in FIXED_HINTS) else 0.72,
                }

    inline_date = re.search(
        r"(deadline|applications?\s+close|closing date|closes on)[:\s]+([^.]+)",
        clean,
        re.I,
    )
    if inline_date:
        candidate_text = inline_date.group(2)
        if not _has_explicit_date_shape(candidate_text):
            return {"deadline_type": "Unknown", "deadline_date": None, "snippet": None, "confidence": 0.0}
        parsed = dateparser.parse(candidate_text, settings=settings)
        if parsed:
            return {
                "deadline_type": "FixedDate",
                "deadline_date": parsed.date(),
                "snippet": inline_date.group(0),
                "confidence": 0.8,
            }

    return {"deadline_type": "Unknown", "deadline_date": None, "snippet": None, "confidence": 0.0}


def looks_expired(text: str, deadline_date: Optional[date]) -> bool:
    lowered = (text or "").lower()
    if any(term in lowered for term in ["closed", "applications closed", "no longer accepting applications"]):
        return True
    if deadline_date and deadline_date < datetime.utcnow().date():
        return True
    return False
