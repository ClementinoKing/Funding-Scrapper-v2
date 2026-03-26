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
        for found_text, found_date in match:
            if found_date:
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
        parsed = dateparser.parse(inline_date.group(2), settings=settings)
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

