"""Money and numeric range extraction helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from scraper.utils.text import clean_text


CURRENCY_MAP = {
    "R": "ZAR",
    "ZAR": "ZAR",
    "$": "USD",
    "US$": "USD",
    "USD": "USD",
    "EUR": "EUR",
    "£": "GBP",
}

SCALE_MAP = {
    "k": 1_000,
    "thousand": 1_000,
    "m": 1_000_000,
    "mn": 1_000_000,
    "million": 1_000_000,
    "b": 1_000_000_000,
    "bn": 1_000_000_000,
    "billion": 1_000_000_000,
}

MONEY_TOKEN_RE = re.compile(
    r"(?P<currency>ZAR|US\$|USD|EUR|GBP|R|\$|£)?\s*"
    r"(?P<number>\d[\d\s,]*(?:\.\d+)?)\s*"
    r"(?P<scale>k|m|mn|bn|b|thousand|million|billion)?",
    re.I,
)

RANGE_RE = re.compile(
    r"(?:between|from)\s+(?P<left>[^,;.]{1,40}?)\s+(?:and|to|-)\s+(?P<right>[^,;.]{1,40})",
    re.I,
)
UP_TO_RE = re.compile(r"(?:up to|maximum of|max(?:imum)?\s*)(?P<value>[^,;.]{1,40})", re.I)
FROM_RE = re.compile(r"(?:starting from|minimum of|min(?:imum)?\s*|from)\s*(?P<value>[^,;.]{1,40})", re.I)


@dataclass
class MoneyMatch:
    raw: str
    value: float
    currency: Optional[str]


def _parse_number(number_text: str, scale_text: Optional[str]) -> float:
    number = float(number_text.replace(" ", "").replace(",", ""))
    if scale_text:
        number *= SCALE_MAP[scale_text.lower()]
    return number


def _looks_like_year(number_text: str) -> bool:
    digits = re.sub(r"[\s,]", "", number_text)
    if not re.fullmatch(r"\d{4}", digits):
        return False
    try:
        year = int(digits)
    except ValueError:
        return False
    return 1900 <= year <= 2099


def parse_money_token(text: str, default_currency: Optional[str] = None) -> Optional[MoneyMatch]:
    cleaned = clean_text(text)
    match = MONEY_TOKEN_RE.fullmatch(cleaned)
    if not match:
        return None
    currency = match.group("currency")
    scale = match.group("scale")
    number = match.group("number")
    if not currency and not scale:
        try:
            if _looks_like_year(number):
                return None
            if float(number.replace(" ", "").replace(",", "")) < 1000:
                return None
        except ValueError:
            return None
    parsed_currency = CURRENCY_MAP.get((currency or "").upper()) if currency else default_currency
    try:
        value = _parse_number(number, scale)
    except (KeyError, ValueError):
        return None
    return MoneyMatch(raw=cleaned, value=value, currency=parsed_currency)


def find_money_mentions(text: str, default_currency: Optional[str] = None) -> List[MoneyMatch]:
    clean = clean_text(text)
    mentions: List[MoneyMatch] = []
    for match in MONEY_TOKEN_RE.finditer(clean):
        token = clean[match.start() : match.end()]
        parsed = parse_money_token(token, default_currency=default_currency)
        if parsed:
            mentions.append(parsed)
    deduped: List[MoneyMatch] = []
    seen = set()
    for mention in mentions:
        key = (mention.value, mention.currency)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(mention)
    return deduped


def infer_default_currency(text: str, source_domain: str = "") -> Optional[str]:
    lowered = clean_text(text).lower()
    domain_lower = source_domain.lower()
    if "zar" in lowered or " rand " in " %s " % lowered or lowered.startswith("r ") or ".za" in domain_lower:
        return "ZAR"
    return None


def extract_money_range(text: str, default_currency: Optional[str] = None) -> Tuple[Optional[float], Optional[float], Optional[str], Optional[str], float]:
    clean = clean_text(text)
    if not clean:
        return None, None, None, None, 0.0

    for pattern in RANGE_RE.finditer(clean):
        left_mentions = find_money_mentions(pattern.group("left"), default_currency=default_currency)
        right_mentions = find_money_mentions(pattern.group("right"), default_currency=default_currency)
        left = left_mentions[0] if left_mentions else parse_money_token(pattern.group("left"), default_currency=default_currency)
        right = right_mentions[0] if right_mentions else parse_money_token(pattern.group("right"), default_currency=default_currency)
        if left and right:
            currency = left.currency or right.currency or default_currency
            minimum = min(left.value, right.value)
            maximum = max(left.value, right.value)
            return minimum, maximum, currency, pattern.group(0), 0.9

    up_to = UP_TO_RE.search(clean)
    if up_to:
        mentions = find_money_mentions(up_to.group("value"), default_currency=default_currency)
        maximum_value = mentions[0] if mentions else parse_money_token(up_to.group("value"), default_currency=default_currency)
        if maximum_value:
            return None, maximum_value.value, maximum_value.currency, up_to.group(0), 0.82

    from_match = FROM_RE.search(clean)
    if from_match:
        mentions = find_money_mentions(from_match.group("value"), default_currency=default_currency)
        minimum_value = mentions[0] if mentions else parse_money_token(from_match.group("value"), default_currency=default_currency)
        if minimum_value:
            return minimum_value.value, None, minimum_value.currency, from_match.group(0), 0.82

    mentions = find_money_mentions(clean, default_currency=default_currency)
    if len(mentions) >= 2:
        values = sorted(mentions[:2], key=lambda item: item.value)
        currency = values[0].currency or values[1].currency or default_currency
        return values[0].value, values[1].value, currency, "%s to %s" % (values[0].raw, values[1].raw), 0.62
    if mentions:
        mention = mentions[0]
        return None, mention.value, mention.currency, mention.raw, 0.45
    return None, None, None, None, 0.0


def extract_budget_total(text: str, default_currency: Optional[str] = None) -> Tuple[Optional[float], Optional[str], Optional[str], float]:
    clean = clean_text(text)
    for sentence in re.split(r"(?<=[.!?])\s+", clean):
        lowered = sentence.lower()
        if not any(keyword in lowered for keyword in ["budget", "fund size", "capital pool", "allocated", "allocation"]):
            continue
        mentions = find_money_mentions(sentence, default_currency=default_currency)
        if mentions:
            return mentions[0].value, mentions[0].currency, sentence, 0.78
    return None, default_currency, None, 0.0
