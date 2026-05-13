"""Money and numeric range extraction helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from scraper.utils.text import clean_text, sentence_chunks


CURRENCY_MAP = {
    "R": "ZAR",
    "ZAR": "ZAR",
    "$": "USD",
    "US$": "USD",
    "USD": "USD",
    "EUR": "EUR",
    "£": "GBP",
    "MK": "MWK",
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
    r"(?P<currency>ZAR|US\$|USD|EUR|GBP|MK|R|\$|£)?\s*"
    r"(?P<number>\d[\d\s,]*(?:\.\d+)?)\s*"
    r"(?P<scale>thousand|million|billion|mn|bn|k|m|b)?\b",
    re.I,
)

RANGE_RE = re.compile(
    r"(?:between|from)\s+(?P<left>[^,;.]{1,40}?)\s+(?:and|to|-|–|—)\s+(?P<right>[^,;.]{1,40})",
    re.I,
)
PLAIN_RANGE_RE = re.compile(
    r"(?P<left>(?:ZAR|US\$|USD|EUR|GBP|MK|R|\$|£)?\s*\d[\d\s,]*(?:\.\d+)?\s*(?:thousand|million|billion|mn|bn|k|m|b)?)\s*(?:to|-|–|—)\s*(?P<right>(?:ZAR|US\$|USD|EUR|GBP|MK|R|\$|£)?\s*\d[\d\s,]*(?:\.\d+)?\s*(?:thousand|million|billion|mn|bn|k|b|m)?)",
    re.I,
)
UP_TO_RE = re.compile(r"(?:up to|maximum of|max(?:imum)?\s*)(?P<value>[^,;.]{1,40})", re.I)
FROM_RE = re.compile(r"(?:starting from|minimum of|min(?:imum)?\s*|from)\s*(?P<value>[^,;.]{1,40})", re.I)
FUNDING_CONTEXT_RE = re.compile(
    r"\b(?:funding|fund|grant|loan|finance|financing|investment|equity|ticket size|loan amount|grant amount|"
    r"capital amount|startup capital|start-up capital|working capital|maximum of|minimum of|up to|from|between)\b",
    re.I,
)
REJECT_CONTEXT_RE = re.compile(
    r"\b(?:trl|technology readiness level|tender number|bid number|rfp|rfq|telephone|tel|phone|fax|percent|percentage)\b",
    re.I,
)
DATE_LIKE_RE = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b")
PHONE_LIKE_RE = re.compile(r"(?:\+?\d[\s().-]*){7,}")
PERCENT_LIKE_RE = re.compile(r"\b\d{1,3}(?:\.\d+)?\s?%")
TRL_LIKE_RE = re.compile(r"\bTRL\s*\d+(?:\s*[-–]\s*\d+)?\b", re.I)


@dataclass
class MoneyMatch:
    raw: str
    value: float
    currency: Optional[str]
    confidence: float = 0.0
    scale: Optional[int] = None


def _parse_number(number_text: str, scale_text: Optional[str]) -> float:
    number = float(number_text.replace(" ", "").replace(",", ""))
    if scale_text:
        number *= SCALE_MAP[scale_text.lower()]
    return number


def _scale_from_text(scale_text: Optional[str]) -> Optional[int]:
    if not scale_text:
        return None
    return SCALE_MAP.get(scale_text.lower())


def _should_inherit_scale(token_text: str, parsed: MoneyMatch) -> bool:
    if parsed.scale is not None:
        return False
    if parsed.value is None or parsed.value >= 1000:
        return False
    return not bool(re.search(r"[\s,]", token_text or ""))


def _looks_like_year(number_text: str) -> bool:
    digits = re.sub(r"[\s,]", "", number_text)
    if not re.fullmatch(r"\d{4}", digits):
        return False
    try:
        year = int(digits)
    except ValueError:
        return False
    return 1900 <= year <= 2099


def _surrounding_text(text: str, start: int, end: int, window: int = 48) -> str:
    return text[max(0, start - window) : min(len(text), end + window)]


def _has_funding_context(text: str) -> bool:
    return bool(FUNDING_CONTEXT_RE.search(text or ""))


def _has_rejected_numeric_context(text: str) -> bool:
    context = text or ""
    if REJECT_CONTEXT_RE.search(context) or DATE_LIKE_RE.search(context) or PERCENT_LIKE_RE.search(context) or TRL_LIKE_RE.search(context):
        return True
    if PHONE_LIKE_RE.fullmatch(clean_text(context)):
        return True
    return False


def parse_money_token(
    text: str,
    default_currency: Optional[str] = None,
    *,
    surrounding_text: str = "",
    require_context: bool = True,
    inherited_currency: Optional[str] = None,
    inherited_scale: Optional[int] = None,
) -> Optional[MoneyMatch]:
    cleaned = clean_text(text)
    match = MONEY_TOKEN_RE.fullmatch(cleaned)
    if not match:
        token_match = re.fullmatch(r"(?P<currency>ZAR|US\$|USD|EUR|GBP|MK|R|\$|£)?\s*(?P<number>\d[\d\s,]*(?:\.\d+)?)\b", cleaned, re.I)
        if not token_match:
            return None
        currency = token_match.group("currency")
        number = token_match.group("number")
        context = clean_text(" ".join([surrounding_text, cleaned]))
        if _has_rejected_numeric_context(context):
            return None
        if _looks_like_year(number):
            return None
        if require_context and not currency and inherited_currency is None and not _has_funding_context(context):
            return None
        if not currency and not inherited_currency and not default_currency:
            try:
                if float(number.replace(" ", "").replace(",", "")) < 1000:
                    return None
            except ValueError:
                return None
        parsed_currency = CURRENCY_MAP.get((currency or "").upper()) if currency else inherited_currency or default_currency
        try:
            value = _parse_number(number, None)
        except (KeyError, ValueError):
            return None
        if inherited_scale:
            value *= inherited_scale
        confidence = 0.88 if currency else 0.7 if inherited_scale else 0.55
        return MoneyMatch(raw=cleaned, value=value, currency=parsed_currency, confidence=confidence, scale=inherited_scale)
    currency = match.group("currency")
    scale = match.group("scale")
    number = match.group("number")
    context = clean_text(" ".join([surrounding_text, cleaned]))
    if _has_rejected_numeric_context(context):
        return None
    if _looks_like_year(number):
        return None
    if require_context and not currency and not scale and not _has_funding_context(context):
        return None
    if require_context and scale and not currency and not _has_funding_context(context):
        return None
    if not currency and not scale:
        try:
            if float(number.replace(" ", "").replace(",", "")) < 1000:
                return None
        except ValueError:
            return None
    parsed_currency = CURRENCY_MAP.get((currency or "").upper()) if currency else default_currency
    try:
        value = _parse_number(number, scale)
    except (KeyError, ValueError):
        return None
    confidence = 0.9 if currency else 0.72 if scale and _has_funding_context(context) else 0.55
    return MoneyMatch(raw=cleaned, value=value, currency=parsed_currency, confidence=confidence, scale=_scale_from_text(scale))


def find_money_mentions(text: str, default_currency: Optional[str] = None, *, require_context: bool = True) -> List[MoneyMatch]:
    clean = clean_text(text)
    mentions: List[MoneyMatch] = []
    for match in MONEY_TOKEN_RE.finditer(clean):
        token = clean[match.start() : match.end()]
        context = _surrounding_text(clean, match.start(), match.end())
        parsed = parse_money_token(
            token,
            default_currency=default_currency,
            surrounding_text=context,
            require_context=require_context,
        )
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


def _endpoint_matches_from_range(
    text: str,
    *,
    default_currency: Optional[str] = None,
    inherited_currency: Optional[str] = None,
    inherited_scale: Optional[int] = None,
    require_context: bool = True,
) -> Optional[MoneyMatch]:
    parsed = parse_money_token(
        text,
        default_currency=default_currency,
        surrounding_text=text,
        require_context=require_context,
        inherited_currency=inherited_currency,
        inherited_scale=inherited_scale,
    )
    if parsed:
        return parsed
    return parse_money_token(
        text,
        default_currency=default_currency,
        surrounding_text=text,
        require_context=False,
        inherited_currency=inherited_currency,
        inherited_scale=inherited_scale,
    )


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
        context = pattern.group(0)
        left_text = clean_text(pattern.group("left"))
        right_text = clean_text(pattern.group("right"))
        left = _endpoint_matches_from_range(left_text, default_currency=default_currency, require_context=False)
        right = _endpoint_matches_from_range(right_text, default_currency=default_currency, require_context=False)
        if left and right:
            if left.currency is None:
                left.currency = right.currency or default_currency
            if right.currency is None:
                right.currency = left.currency or default_currency
            if left.scale is None and right.scale is not None and _should_inherit_scale(left_text, left):
                left.scale = right.scale
                left.value *= right.scale
            if right.scale is None and left.scale is not None and _should_inherit_scale(right_text, right):
                right.scale = left.scale
                right.value *= left.scale
            if left.scale and right.scale and left.scale != right.scale:
                pass
            elif left.scale and right.scale and left.scale == right.scale:
                pass
            elif left.scale and not right.scale:
                right.scale = left.scale
            elif right.scale and not left.scale:
                left.scale = right.scale
        else:
            left_mentions = find_money_mentions(context, default_currency=default_currency)
            right_mentions = find_money_mentions(context, default_currency=default_currency)
            left = left_mentions[0] if left_mentions else parse_money_token(left_text, default_currency=default_currency, surrounding_text=context)
            right = right_mentions[-1] if len(right_mentions) > 1 else parse_money_token(right_text, default_currency=default_currency, surrounding_text=context)
            if left and right:
                if left.scale is None and right.scale is not None and _should_inherit_scale(left_text, left):
                    left.value *= right.scale
                    left.scale = right.scale
                if right.scale is None and left.scale is not None and _should_inherit_scale(right_text, right):
                    right.value *= left.scale
                    right.scale = left.scale
        if left and right:
            currency = left.currency or right.currency or default_currency
            minimum = min(left.value, right.value)
            maximum = max(left.value, right.value)
            return minimum, maximum, currency, pattern.group(0), 0.9

    plain_range = PLAIN_RANGE_RE.search(clean)
    if plain_range:
        left_text = clean_text(plain_range.group("left"))
        right_text = clean_text(plain_range.group("right"))
        left = _endpoint_matches_from_range(left_text, default_currency=default_currency, require_context=False)
        right = _endpoint_matches_from_range(right_text, default_currency=default_currency, require_context=False)
        if left and right:
            if left.currency is None:
                left.currency = right.currency or default_currency
            if right.currency is None:
                right.currency = left.currency or default_currency
            if left.scale is None and right.scale is not None and _should_inherit_scale(left_text, left):
                left.scale = right.scale
                left.value *= right.scale
            if right.scale is None and left.scale is not None and _should_inherit_scale(right_text, right):
                right.scale = left.scale
                right.value *= left.scale
            currency = left.currency or right.currency or default_currency
            minimum = min(left.value, right.value)
            maximum = max(left.value, right.value)
            return minimum, maximum, currency, plain_range.group(0), 0.9

    up_to = UP_TO_RE.search(clean)
    if up_to:
        context = up_to.group(0)
        mentions = find_money_mentions(context, default_currency=default_currency)
        maximum_value = mentions[0] if mentions else parse_money_token(up_to.group("value"), default_currency=default_currency, surrounding_text=context)
        if maximum_value:
            return None, maximum_value.value, maximum_value.currency, up_to.group(0), max(0.7, maximum_value.confidence)

    from_match = FROM_RE.search(clean)
    if from_match:
        context = from_match.group(0)
        value_text = clean_text(from_match.group("value"))
        plain_range = PLAIN_RANGE_RE.search(value_text)
        if plain_range:
            left_text = clean_text(plain_range.group("left"))
            right_text = clean_text(plain_range.group("right"))
            left = _endpoint_matches_from_range(left_text, default_currency=default_currency, require_context=False)
            right = _endpoint_matches_from_range(right_text, default_currency=default_currency, require_context=False)
            if left and right:
                if left.currency is None:
                    left.currency = right.currency or default_currency
                if right.currency is None:
                    right.currency = left.currency or default_currency
                if left.scale is None and right.scale is not None and _should_inherit_scale(left_text, left):
                    left.scale = right.scale
                    left.value *= right.scale
                if right.scale is None and left.scale is not None and _should_inherit_scale(right_text, right):
                    right.scale = left.scale
                    right.value *= left.scale
                currency = left.currency or right.currency or default_currency
                minimum = min(left.value, right.value)
                maximum = max(left.value, right.value)
                return minimum, maximum, currency, from_match.group(0), 0.9
        mentions = find_money_mentions(value_text or context, default_currency=default_currency)
        if len(mentions) >= 2:
            left, right = mentions[:2]
            if left.currency is None:
                left.currency = right.currency or default_currency
            if right.currency is None:
                right.currency = left.currency or default_currency
            if left.scale is None and right.scale is not None and _should_inherit_scale(left.raw, left):
                left.scale = right.scale
                left.value *= right.scale
            if right.scale is None and left.scale is not None and _should_inherit_scale(right.raw, right):
                right.scale = left.scale
                right.value *= left.scale
            currency = left.currency or right.currency or default_currency
            minimum = min(left.value, right.value)
            maximum = max(left.value, right.value)
            return minimum, maximum, currency, from_match.group(0), 0.9
        minimum_value = mentions[0] if mentions else parse_money_token(value_text, default_currency=default_currency, surrounding_text=context)
        if minimum_value:
            return minimum_value.value, None, minimum_value.currency, from_match.group(0), max(0.7, minimum_value.confidence)

    mentions = find_money_mentions(clean, default_currency=default_currency)
    if len(mentions) >= 2:
        left, right = mentions[:2]
        if left.currency is None:
            left.currency = right.currency or default_currency
        if right.currency is None:
            right.currency = left.currency or default_currency
        if left.scale is None and right.scale is not None and _should_inherit_scale(left.raw, left):
            left.scale = right.scale
            left.value *= right.scale
        if right.scale is None and left.scale is not None and _should_inherit_scale(right.raw, right):
            right.scale = left.scale
            right.value *= left.scale
        values = sorted((left, right), key=lambda item: item.value)
        currency = values[0].currency or values[1].currency or default_currency
        confidence = min(values[0].confidence, values[1].confidence, 0.68)
        return values[0].value, values[1].value, currency, "%s to %s" % (values[0].raw, values[1].raw), confidence
    if mentions:
        mention = mentions[0]
        return None, mention.value, mention.currency, mention.raw, min(mention.confidence, 0.65)
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


def extract_amount_evidence(text: str, default_currency: Optional[str] = None) -> Dict[str, Any]:
    clean = clean_text(text)
    evidence: Dict[str, Any] = {}
    if not clean:
        return evidence

    ideal_markers = ("ideal", "preferred", "target", "typical", "recommended")
    min_markers = ("minimum", "min ", "min.", "at least", "starting from", "no less than")
    max_markers = ("maximum", "max ", "max.", "up to", "not exceeding", "ceiling")
    amount_markers = ("fund", "funding", "loan", "grant", "investment", "ticket", "amount", "capital", "budget", "size")

    for sentence in sentence_chunks(clean):
        lowered = sentence.lower()
        if not (
            any(term in lowered for term in amount_markers)
            or any(marker in lowered for marker in ideal_markers)
            or any(marker in lowered for marker in min_markers)
            or any(marker in lowered for marker in max_markers)
        ):
            continue
        minimum, maximum, currency, raw, confidence = extract_money_range(sentence, default_currency=default_currency)
        if raw is None:
            continue
        currency_code = currency or default_currency
        if any(marker in lowered for marker in ideal_markers):
            if minimum is None and maximum is not None:
                minimum = maximum
            ideal_entry: Dict[str, Any] = {
                "raw": raw,
                "min": minimum,
                "max": maximum,
                "currency": currency_code,
            }
            evidence.setdefault("ideal_range", ideal_entry)
            continue
        if any(marker in lowered for marker in min_markers):
            if minimum is None and maximum is not None:
                minimum = maximum
            evidence.setdefault(
                "minimum",
                {
                    "raw": raw,
                    "value": minimum,
                    "currency": currency_code,
                    "confidence": confidence,
                },
            )
            continue
        if any(marker in lowered for marker in max_markers):
            if maximum is None and minimum is not None:
                maximum = minimum
            evidence.setdefault(
                "maximum",
                {
                    "raw": raw,
                    "value": maximum,
                    "currency": currency_code,
                    "confidence": confidence,
                },
            )
            continue
        if minimum is not None or maximum is not None:
            evidence.setdefault(
                "range",
                {
                    "raw": raw,
                    "min": minimum,
                    "max": maximum,
                    "currency": currency_code,
                    "confidence": confidence,
                },
            )
    return evidence
