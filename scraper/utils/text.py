"""Text utilities for extraction and normalization."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


WHITESPACE_RE = re.compile(r"\s+")
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
NUMBERED_SECTION_RE = re.compile(r"^\s*\d+(?:[.)]\s*|\s+)?")

SUPPORT_TITLE_HINTS = (
    "eligibility criteria",
    "eligibility",
    "programme guidelines",
    "program guidelines",
    "funding criteria",
    "how to apply",
    "application procedure",
    "application portal",
    "ttf checklist",
    "checklist",
    "brochure",
    "background",
    "preamble",
    "contact details",
    "disclaimer",
    "other conditions",
    "adjudication process",
    "post investment monitoring",
    "terms and structure",
    "required documents",
    "timing",
    "deadline",
)


def collapse_whitespace(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text or "").strip()


def clean_text(text: str) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.replace("\xa0", " ")
    return collapse_whitespace(normalized)


def looks_like_support_title(text: str) -> bool:
    cleaned = clean_text(text).lower()
    if not cleaned:
        return False
    stripped = NUMBERED_SECTION_RE.sub("", cleaned).strip()
    if stripped in SUPPORT_TITLE_HINTS:
        return True
    return any(hint in stripped for hint in SUPPORT_TITLE_HINTS)


def split_lines(text: str) -> List[str]:
    lines = [clean_text(line) for line in (text or "").splitlines()]
    return [line for line in lines if line]


def unique_preserve_order(items: Sequence[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for item in items:
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def slugify(value: str, max_length: int = 60) -> str:
    if not value:
        return "unknown"
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    value = re.sub(r"-{2,}", "-", value)
    return (value or "unknown")[:max_length].strip("-") or "unknown"


def generate_program_id(source_domain: str, funder_name: Optional[str], program_name: Optional[str]) -> str:
    domain_slug = slugify(source_domain, max_length=30)
    program_slug = slugify(program_name or "unknown-program", max_length=40)
    fingerprint = "|".join([source_domain or "", funder_name or "", program_name or ""])
    digest = hashlib.blake2b(fingerprint.encode("utf-8"), digest_size=4).hexdigest()
    return "funding_%s_%s_%s" % (domain_slug, program_slug, digest)


def extract_emails(text: str) -> List[str]:
    return unique_preserve_order([match.group(0).lower() for match in EMAIL_RE.finditer(text or "")])


def extract_phone_numbers(text: str) -> List[str]:
    phones: List[str] = []
    for match in PHONE_RE.finditer(text or ""):
        phone = collapse_whitespace(match.group(0))
        digits = re.sub(r"\D", "", phone)
        if len(digits) >= 9:
            phones.append(phone)
    return unique_preserve_order(phones)


def sentence_chunks(text: str) -> List[str]:
    if not text:
        return []
    pieces = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [clean_text(piece) for piece in pieces if clean_text(piece)]


def matching_phrases(text: str, phrases: Iterable[str]) -> List[str]:
    haystack = (text or "").casefold()
    matches = [phrase for phrase in phrases if _contains_phrase(haystack, phrase.casefold())]
    return unique_preserve_order(matches)


def _contains_phrase(haystack: str, phrase: str) -> bool:
    if not haystack or not phrase:
        return False
    pattern = r"(?<![0-9a-z])%s(?![0-9a-z])" % re.escape(phrase)
    return re.search(pattern, haystack, re.I) is not None


def match_keyword_map(text: str, keyword_map: Dict[str, Sequence[str]]) -> Tuple[List[str], Dict[str, List[str]]]:
    haystack = (text or "").casefold()
    categories: List[str] = []
    evidence: Dict[str, List[str]] = {}
    for category, keywords in keyword_map.items():
        hits = [keyword for keyword in keywords if _contains_phrase(haystack, keyword.casefold())]
        if hits:
            categories.append(category)
            evidence[category] = unique_preserve_order(hits)
    return unique_preserve_order(categories), evidence


def completeness_score(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, str):
        return 2 if clean_text(value) else 0
    if isinstance(value, (int, float, bool)):
        return 2
    if isinstance(value, dict):
        return sum(completeness_score(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return sum(completeness_score(item) for item in value)
    return 1


def take_best_snippet(snippets: Sequence[str], default: str = "") -> str:
    cleaned = [clean_text(snippet) for snippet in snippets if clean_text(snippet)]
    if not cleaned:
        return default
    return max(cleaned, key=len)
