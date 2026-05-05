"""Normalization logic turning candidate blocks into canonical records."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

from scraper.classifiers.funding_type import classify_funding_type
from scraper.classifiers.geography import classify_geography
from scraper.classifiers.industries import classify_industries
from scraper.classifiers.eligibility import extract_eligibility_criteria
from scraper.classifiers.ownership_targets import classify_ownership_targets
from scraper.classifiers.repayment import extract_payback_details
from scraper.classifiers.use_of_funds import classify_use_of_funds
from scraper.config import ScraperSettings
from scraper.parsers.extractor_rules import CandidateBlock, detect_archive_signals, find_section_values
from scraper.schemas import (
    ApplicationChannel,
    DeadlineType,
    FieldEvidence,
    FundingProgrammeRecord,
    InterestType,
    PageDebugPackage,
    PageDebugRecord,
    ProgrammeStatus,
    RepaymentFrequency,
    TriState,
)
from scraper.utils.dates import looks_expired, parse_deadline_info
from scraper.utils.money import extract_budget_total, extract_money_range, infer_default_currency
from scraper.utils.page_classification import classify_global_page_type
from scraper.utils.text import (
    clean_text,
    extract_emails,
    extract_phone_numbers,
    extract_urls,
    looks_like_support_title,
    match_keyword_map,
    sentence_chunks,
    split_lines,
    take_best_snippet,
    unique_preserve_order,
)
from scraper.utils.urls import extract_domain, is_probably_document_url


STAGE_PATTERNS = {
    "startup": ["startup", "start-up"],
    "seed": ["seed stage", "seed"],
    "early stage": ["early stage", "early-stage"],
    "growth stage": ["growth stage", "scale-up", "growth-focused"],
    "expansion": ["expansion", "expanding"],
    "established business": ["established business", "existing business", "trading for"],
}

SECURITY_PATTERNS = {
    TriState.YES: ["collateral required", "security required", "must provide security"],
    TriState.NO: ["no collateral", "no security required", "unsecured"],
    TriState.MAYBE: ["may require security", "security may be required", "subject to security"],
}

EQUITY_PATTERNS = {
    TriState.YES: ["equity stake required", "equity participation", "dilution required"],
    TriState.NO: ["loan only", "no dilution", "no equity required"],
    TriState.MAYBE: ["case-by-case equity", "equity participation may apply"],
}

INTEREST_PATTERNS = {
    InterestType.FIXED: ["fixed interest", "fixed rate"],
    InterestType.PRIME_LINKED: ["linked to prime", "prime-linked", "prime plus", "prime less"],
    InterestType.FACTOR_RATE: ["factor fee", "factor rate"],
}

REPAYMENT_PATTERNS = {
    RepaymentFrequency.MONTHLY: ["monthly instalments", "monthly installments", "monthly repayments", "repay monthly"],
    RepaymentFrequency.WEEKLY: ["weekly repayments", "repay weekly"],
    RepaymentFrequency.QUARTERLY: ["quarterly repayments", "repay quarterly", "every quarter"],
    RepaymentFrequency.ANNUALLY: ["annual repayments", "annual instalments", "annually", "yearly", "per annum"],
    RepaymentFrequency.ONCE_OFF: ["once-off", "once off", "bullet repayment", "balloon payment", "lump sum repayment"],
    RepaymentFrequency.FLEXIBLE: ["flexible schedule", "variable repayment", "case-by-case repayment", "cash flow linked"],
    RepaymentFrequency.VARIABLE: ["variable schedule", "tailored repayment", "negotiated repayment"],
}

APPLICATION_TEXT_PATTERNS = {
    ApplicationChannel.EMAIL: ["submit by email", "email your application", "send application to"],
    ApplicationChannel.BRANCH: ["visit nearest branch", "apply at branch", "branch application"],
    ApplicationChannel.PARTNER_REFERRAL: ["partner referral", "through incubator", "via incubator", "through partner"],
    ApplicationChannel.ONLINE_FORM: ["apply online", "online application", "apply now", "complete the form online"],
}

SOURCE_SCOPE_HINTS = {
    "support_page": (
        "criteria",
        "eligibility",
        "guidelines",
        "how-to-apply",
        "how to apply",
        "application",
        "documents",
        "checklist",
        "faq",
        "support",
        "instrument",
    ),
    "parent_page": (
        "programme",
        "program",
        "fund",
        "overview",
        "about",
    ),
}

APPLICATION_LINK_POSITIVE_TERMS = (
    "portal",
    "apply",
    "application",
    "register",
    "submit",
    "online",
    "form",
)

APPLICATION_LINK_NEGATIVE_TERMS = (
    "brochure",
    "checklist",
    "guidelines",
    "download",
    "template",
    "sample",
)


def _scope_from_text(page_url: str, page_title: Optional[str], text: str, heading: str = "") -> str:
    haystack = " ".join([page_url or "", page_title or "", text or "", heading or ""]).lower()
    if any(term in haystack for term in SOURCE_SCOPE_HINTS["support_page"]):
        return "support_page"
    path_segments = [segment for segment in urlparse(page_url or "").path.split("/") if segment]
    if len(path_segments) <= 2 and any(term in haystack for term in SOURCE_SCOPE_HINTS["parent_page"]):
        return "parent_page"
    return "product_page"


def _percentage_mentions(text: str) -> List[str]:
    mentions: List[str] = []
    for match in re.finditer(r"\b\d{1,3}(?:\.\d+)?\s?%", text or ""):
        mentions.append(clean_text(match.group(0)))
    return unique_preserve_order(mentions)


def _ownership_thresholds(text: str) -> List[str]:
    thresholds: List[str] = []
    patterns = [
        re.compile(r"\b(?:minimum of|min\.?|at least|not less than)\s*(\d{1,3}(?:\.\d+)?)\s*%\s*(black|female|women|youth|black women|black female|black-owned|women-owned|youth-owned|minority)?(?:\s*(?:ownership|shareholding|equity|interest|ownership stake))?", re.I),
        re.compile(r"\b(\d{1,3}(?:\.\d+)?)\s*%\s*(black|female|women|youth|black women|black female|black-owned|women-owned|youth-owned|minority)[^\n.]{0,80}", re.I),
    ]
    for pattern in patterns:
        for match in pattern.finditer(text or ""):
            thresholds.append(clean_text(match.group(0)))
    return unique_preserve_order(thresholds)


def _funding_keywords(text: str) -> List[str]:
    keywords = []
    for phrase in ["grant", "loan", "equity", "guarantee", "hybrid", "quasi-equity", "debt", "working capital", "asset finance", "acquisition finance"]:
        if phrase in (text or "").lower():
            keywords.append(phrase)
    return unique_preserve_order(keywords)


def _source_scope_for_record(page_url: str, page_title: Optional[str], text: str, heading: str, page_type: Optional[str] = None) -> str:
    if page_type in {"parent"}:
        return "parent_page"
    if page_type in {"application_support_page", "support-document", "supporting_or_complementary_programme_page"}:
        return "support_page"
    return _scope_from_text(page_url, page_title, text, heading)


def _method_confidence(method: str, fallback: float = 0.0) -> float:
    return EVIDENCE_METHOD_CONFIDENCE.get(method, fallback)


def _normalize_evidence_map(evidence: List[FieldEvidence]) -> Dict[str, List[FieldEvidence]]:
    grouped: Dict[str, List[FieldEvidence]] = {}
    for item in evidence:
        grouped.setdefault(item.field_name, []).append(item)
    return grouped


def _confidence_map_from_evidence(evidence_map: Dict[str, List[FieldEvidence]]) -> Dict[str, float]:
    confidence_map: Dict[str, float] = {}
    for field_name, items in evidence_map.items():
        if not items:
            continue
        best = max(items, key=lambda item: (EVIDENCE_METHOD_PRIORITY.get(item.method, 0), item.confidence))
        confidence_map[field_name] = round(best.confidence, 4)
    return confidence_map

PUBLICATION_PATH_TERMS = (
    "press-release",
    "press-releases",
    "news",
    "media",
    "publication",
    "publications",
    "article",
    "articles",
    "blog",
    "case-study",
    "case-studies",
    "success-story",
    "success-stories",
)

EVIDENCE_METHOD_CONFIDENCE = {
    "direct_page_evidence": 0.96,
    "deterministic_parser": 0.92,
    "regex_from_prose": 0.84,
    "heading_based_inference": 0.72,
    "parent_page_inheritance": 0.64,
    "llm_only_inference": 0.5,
}

EVIDENCE_METHOD_PRIORITY = {
    "direct_page_evidence": 5,
    "deterministic_parser": 4,
    "regex_from_prose": 3,
    "heading_based_inference": 2,
    "parent_page_inheritance": 1,
    "llm_only_inference": 0,
}

PUBLICATION_TEXT_TERMS = (
    "press release",
    "media release",
    "news article",
    "publication",
    "publications",
    "article",
    "success story",
    "case study",
)

INDUSTRY_SECTION_HINTS = (
    "industry",
    "industries",
    "sector",
    "sectors",
    "focus area",
    "focus areas",
    "target sector",
    "target sectors",
    "eligible sector",
    "eligible sectors",
    "who can apply",
)

USE_OF_FUNDS_SECTION_HINTS = (
    "use of funds",
    "funding line",
    "funding lines",
    "funding products",
    "funding offer",
    "funding facilities",
    "funding options",
    "products and services",
    "product",
    "products",
    "facilities",
    "what the funding can be used for",
    "can be used for",
)

TERMS_SECTION_HINTS = (
    "terms",
    "repayment",
    "interest",
    "security",
    "collateral",
    "pricing",
    "tenor",
    "loan term",
    "payback",
    "duration",
    "moratorium",
    "grace period",
    "instalment",
    "installment",
)

ELIGIBILITY_CRITERIA_SECTION_HINTS = (
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

APPLICATION_SECTION_HINTS = (
    "application",
    "apply",
    "how to apply",
    "submission",
    "contact",
)


def _add_evidence(
    field_name: str,
    normalized_value: object,
    snippet: Optional[str],
    confidence: float,
    source_url: str,
    evidence_store: List[FieldEvidence],
    raw_text_snippets: Dict[str, List[str]],
    extraction_confidence: Dict[str, float],
    *,
    raw_value: Optional[object] = None,
    source_section: Optional[str] = None,
    source_scope: Optional[str] = None,
    method: str = "regex_from_prose",
) -> None:
    if snippet:
        cleaned = clean_text(snippet)
        raw_text_snippets.setdefault(field_name, [])
        if cleaned and cleaned not in raw_text_snippets[field_name]:
            raw_text_snippets[field_name].append(cleaned)
        score = max(confidence, _method_confidence(method, confidence))
        evidence_store.append(
            FieldEvidence(
                field_name=field_name,
                normalized_value=normalized_value,
                raw_value=raw_value if raw_value is not None else cleaned,
                evidence_text=cleaned,
                source_url=source_url,
                source_section=source_section,
                source_scope=source_scope,
                confidence=round(score, 4),
                method=method,
            )
        )
    score = max(confidence, _method_confidence(method, confidence))
    if score > extraction_confidence.get(field_name, 0.0):
        extraction_confidence[field_name] = round(score, 4)


def _first_matching_sentences(text: str, keywords: Sequence[str], limit: int = 4) -> List[str]:
    matches = []
    for sentence in sentence_chunks(text):
        lowered = sentence.lower()
        if any(keyword in lowered for keyword in keywords):
            matches.append(sentence)
        if len(matches) >= limit:
            break
    return unique_preserve_order(matches)


def _split_section_items(values: Sequence[str], *, max_items: int = 12) -> List[str]:
    items: List[str] = []
    for value in values:
        for line in split_lines(value):
            for sentence in sentence_chunks(line):
                cleaned = clean_text(sentence)
                if cleaned:
                    items.append(cleaned)
    if not items:
        return []
    deduped = unique_preserve_order(items)
    return deduped[:max_items]


def _extract_stage_eligibility(text: str) -> Tuple[List[str], List[str]]:
    lowered = (text or "").lower()
    stages: List[str] = []
    evidence: List[str] = []
    for label, phrases in STAGE_PATTERNS.items():
        if any(phrase in lowered for phrase in phrases):
            stages.append(label)
            evidence.extend([phrase for phrase in phrases if phrase in lowered])
    return unique_preserve_order(stages), unique_preserve_order(evidence)


def _extract_numeric_range(text: str, unit_keywords: Sequence[str]) -> Tuple[Optional[float], Optional[float], Optional[str], float]:
    candidates = _first_matching_sentences(text, unit_keywords, limit=4)
    patterns = [
        re.compile(r"(\d+(?:\.\d+)?)\s*(?:to|-)\s*(\d+(?:\.\d+)?)", re.I),
        re.compile(r"(?:at least|minimum of|min\.?)\s*(\d+(?:\.\d+)?)", re.I),
        re.compile(r"(?:up to|maximum of|max\.?)\s*(\d+(?:\.\d+)?)", re.I),
    ]
    for sentence in candidates:
        for pattern in patterns:
            match = pattern.search(sentence)
            if not match:
                continue
            if len(match.groups()) == 2 and match.group(2):
                return float(match.group(1)), float(match.group(2)), sentence, 0.8
            if "up to" in sentence.lower() or "maximum" in sentence.lower() or "max" in sentence.lower():
                return None, float(match.group(1)), sentence, 0.72
            return float(match.group(1)), None, sentence, 0.72
    return None, None, None, 0.0


def _extract_month_range(text: str, keywords: Sequence[str]) -> Tuple[Optional[int], Optional[int], Optional[str], float]:
    candidates = _first_matching_sentences(text, keywords, limit=4)
    range_re = re.compile(r"(\d+)\s*(?:to|-)\s*(\d+)\s*(months?|years?)", re.I)
    single_re = re.compile(r"(?:up to|maximum of|max(?:imum)?|minimum of|min(?:imum)?|at least)?\s*(\d+)\s*(months?|years?)", re.I)
    for sentence in candidates:
        range_match = range_re.search(sentence)
        if range_match:
            minimum = int(range_match.group(1))
            maximum = int(range_match.group(2))
            unit = range_match.group(3).lower()
            multiplier = 12 if unit.startswith("year") else 1
            return minimum * multiplier, maximum * multiplier, sentence, 0.84
        single_match = single_re.search(sentence)
        if single_match:
            value = int(single_match.group(1))
            unit = single_match.group(2).lower()
            multiplier = 12 if unit.startswith("year") else 1
            lowered = sentence.lower()
            if any(term in lowered for term in ["up to", "maximum", "max"]):
                return None, value * multiplier, sentence, 0.74
            return value * multiplier, None, sentence, 0.74
    return None, None, None, 0.0


def _extract_day_range(text: str, keywords: Sequence[str]) -> Tuple[Optional[int], Optional[int], Optional[str], float]:
    candidates = _first_matching_sentences(text, keywords, limit=4)
    range_re = re.compile(r"(\d+)\s*(?:to|-)\s*(\d+)\s*(days?|weeks?)", re.I)
    single_re = re.compile(r"within\s+(\d+)\s*(days?|weeks?)", re.I)
    for sentence in candidates:
        match = range_re.search(sentence)
        if match:
            minimum = int(match.group(1))
            maximum = int(match.group(2))
            unit = match.group(3).lower()
            multiplier = 7 if unit.startswith("week") else 1
            return minimum * multiplier, maximum * multiplier, sentence, 0.82
        match = single_re.search(sentence)
        if match:
            value = int(match.group(1))
            unit = match.group(2).lower()
            multiplier = 7 if unit.startswith("week") else 1
            return value * multiplier, value * multiplier, sentence, 0.72
    return None, None, None, 0.0


def _normalize_ordered_pair(
    minimum: Optional[float],
    maximum: Optional[float],
) -> Tuple[Optional[float], Optional[float], bool]:
    if minimum is not None and maximum is not None and minimum > maximum:
        return maximum, minimum, True
    return minimum, maximum, False


def _classify_tristate(text: str, mapping: Dict[TriState, Sequence[str]]) -> Tuple[TriState, Optional[str], float]:
    lowered = (text or "").lower()
    for value, phrases in mapping.items():
        for phrase in phrases:
            if phrase in lowered:
                return value, phrase, 0.86
    return TriState.UNKNOWN, None, 0.0


def _classify_enum(text: str, mapping: Dict[object, Sequence[str]], unknown_value: object) -> Tuple[object, Optional[str], float]:
    lowered = (text or "").lower()
    for value, phrases in mapping.items():
        for phrase in phrases:
            if phrase in lowered:
                return value, phrase, 0.84
    return unknown_value, None, 0.0


def _infer_program_name(block: CandidateBlock, page_title: Optional[str]) -> Optional[str]:
    if block.heading and len(block.heading) > 3 and not looks_like_support_title(block.heading):
        return block.heading
    if page_title:
        for separator in [" | ", " - ", " — ", " :: "]:
            if separator in page_title:
                fragments = [clean_text(part) for part in page_title.split(separator) if clean_text(part)]
                for fragment in fragments:
                    if not looks_like_support_title(fragment):
                        return fragment
        cleaned_title = clean_text(page_title)
        if cleaned_title and not looks_like_support_title(cleaned_title):
            return cleaned_title
    return None


def _infer_funder_name(page_title: Optional[str], text: str) -> Optional[str]:
    patterns = [
        re.compile(r"(?:offered|provided|managed|administered)\s+by\s+([A-Z][A-Za-z0-9&.,'\- ]{3,80})"),
        re.compile(r"([A-Z][A-Za-z0-9&.,'\- ]{3,80})\s+(?:offers|provides|administers)"),
    ]
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return clean_text(match.group(1))
    if page_title:
        for separator in [" | ", " - ", " — ", " :: "]:
            if separator in page_title:
                fragments = [clean_text(part) for part in page_title.split(separator) if clean_text(part)]
                if fragments and looks_like_support_title(fragments[0]):
                    continue
                candidate = fragments[-1] if fragments else ""
                if candidate and len(candidate.split()) <= 8:
                    return candidate
    return None


def _extract_funding_lines(block: CandidateBlock, program_name: Optional[str]) -> List[str]:
    lines: List[str] = []
    lines.extend(_split_section_items(block.section_bundle.funding_offer))
    for heading, values in block.section_map.items():
        lowered = heading.lower()
        if any(term in lowered for term in ["funding products", "products", "facilities", "lines", "offerings"]):
            for value in values:
                lines.extend(_split_section_items([value], max_items=6))
    for value in block.section_map.keys():
        if any(term in value.lower() for term in ["loan", "grant", "finance", "facility"]) and len(value) <= 80:
            lines.append(value)
    if program_name:
        lines = [line for line in lines if clean_text(line).casefold() != clean_text(program_name).casefold()]
    return unique_preserve_order(lines)


def _extract_eligibility_items(block: CandidateBlock) -> List[str]:
    eligibility = block.section_bundle.eligibility or find_section_values(block.section_map, "eligibility", block.section_aliases)
    if eligibility:
        return _split_section_items(eligibility)
    items = []
    for sentence in sentence_chunks(block.text):
        lowered = sentence.lower()
        if any(term in lowered for term in ["must", "eligible", "requirement", "applicants should", "enterprise must"]):
            items.append(sentence)
        if len(items) >= 10:
            break
    return _split_section_items(items)


def _extract_eligibility_criteria_items(block: CandidateBlock, eligibility_data: Sequence[str]) -> List[str]:
    scoped_text = _scoped_section_text(block.section_map, ELIGIBILITY_CRITERIA_SECTION_HINTS)
    source_text = clean_text(
        " ".join(
            unique_preserve_order(
                [
                    *block.section_bundle.eligibility,
                    *find_section_values(block.section_map, "eligibility", block.section_aliases),
                    scoped_text,
                    *eligibility_data,
                    block.text,
                ]
            )
        )
    )
    criteria = extract_eligibility_criteria(source_text)
    if not criteria and eligibility_data:
        criteria = extract_eligibility_criteria(" ".join(eligibility_data))
    return criteria


def _extract_required_documents(block: CandidateBlock) -> List[str]:
    documents = list(block.section_bundle.related_documents)
    documents.extend(find_section_values(block.section_map, "documents", block.section_aliases))
    for document_link in block.document_links:
        documents.append(document_link)
    filtered_documents: List[str] = []
    for document in documents:
        lowered = clean_text(document).lower()
        if not lowered:
            continue
        if any(term in lowered for term in ["apply online", "application portal", "online portal", "submit application"]):
            continue
        if any(term in lowered for term in ["apply", "application", "portal", "form", "submit", "online"]) and not any(
            term in lowered for term in ["document", "documents", "certificate", "certified", "checklist", "guideline", "guidelines", "requirements"]
        ):
            continue
        filtered_documents.append(document)
    return unique_preserve_order(filtered_documents)


def _extract_raw_funding_offer_data(block: CandidateBlock, combined_text: str) -> List[str]:
    section_values = block.section_bundle.funding_offer or find_section_values(block.section_map, "funding", block.section_aliases)
    if section_values:
        return unique_preserve_order(section_values)
    funding_scope = _scoped_section_text(block.section_map, USE_OF_FUNDS_SECTION_HINTS)
    if funding_scope:
        return _first_matching_sentences(funding_scope, ["fund", "finance", "grant", "loan", "equity"], limit=6)
    return _first_matching_sentences(combined_text, ["fund", "finance", "grant", "loan", "equity"], limit=6)


def _extract_raw_terms_data(block: CandidateBlock, combined_text: str) -> List[str]:
    terms_scope = " ".join(block.section_bundle.terms_and_structure) or _scoped_section_text(block.section_map, TERMS_SECTION_HINTS) or combined_text
    return _first_matching_sentences(
        terms_scope,
        ["repayment", "interest", "prime", "collateral", "security", "equity", "tenor"],
        limit=6,
    )


def _extract_raw_application_data(block: CandidateBlock, combined_text: str) -> List[str]:
    application_scope = " ".join(block.section_bundle.application_route) or _scoped_section_text(
        block.section_map,
        APPLICATION_SECTION_HINTS,
        block.section_aliases.get("application", ()),
    )
    if application_scope:
        return unique_preserve_order(split_lines(application_scope)[:8] or sentence_chunks(application_scope)[:8])
    return _first_matching_sentences(
        combined_text,
        ["apply", "application", "submit", "email", "contact", "branch", "referral"],
        limit=6,
    )


def _derive_programme_status(
    combined_text: str,
    notes: Sequence[str],
    deadline_type: DeadlineType,
    deadline_date: Optional[date],
) -> ProgrammeStatus:
    lowered = (combined_text or "").lower()
    notes_lower = " ".join(notes).lower()
    if any(term in lowered or term in notes_lower for term in ["opening soon", "opens soon", "launching soon"]):
        return ProgrammeStatus.OPENING_SOON
    if any(term in lowered or term in notes_lower for term in ["suspended", "temporarily unavailable", "paused"]):
        return ProgrammeStatus.SUSPENDED
    if any(term in lowered or term in notes_lower for term in ["closed", "now closed", "applications closed", "expired", "archived"]):
        return ProgrammeStatus.CLOSED
    if deadline_type in {DeadlineType.OPEN, DeadlineType.ROLLING}:
        return ProgrammeStatus.ACTIVE
    if deadline_type == DeadlineType.FIXED_DATE and deadline_date is not None:
        return ProgrammeStatus.CLOSED if deadline_date < datetime.now(timezone.utc).date() else ProgrammeStatus.ACTIVE
    return ProgrammeStatus.UNKNOWN


def _extract_exclusions(block: CandidateBlock) -> List[str]:
    exclusions = find_section_values(block.section_map, "exclusions", block.section_aliases)
    if exclusions:
        return exclusions
    items = []
    for sentence in sentence_chunks(block.text):
        lowered = sentence.lower()
        if any(term in lowered for term in ["not eligible", "does not fund", "excluded", "will not finance"]):
            items.append(sentence)
    return unique_preserve_order(items)


def _pick_application_route(block: CandidateBlock, page_url: str, text: str) -> Tuple[ApplicationChannel, Optional[str], Optional[str], float]:
    lowered = (text or "").lower()
    if block.application_links:
        page_domain = extract_domain(page_url)

        def score_candidate(url: str) -> float:
            lowered_url = url.lower()
            if not lowered_url:
                return -100.0
            if is_probably_document_url(url):
                return -100.0

            score = 0.0
            if any(term in lowered_url for term in APPLICATION_LINK_POSITIVE_TERMS):
                score += 18.0
            if "online." in lowered_url or "portal" in lowered_url:
                score += 10.0
            if "application portal" in lowered and ("online." in lowered_url or "portal" in lowered_url):
                score += 10.0
            if any(term in lowered_url for term in APPLICATION_LINK_NEGATIVE_TERMS):
                score -= 18.0
            if "/wp-content/uploads/" in lowered_url:
                score -= 24.0
            if extract_domain(url) and extract_domain(url) != page_domain:
                score += 6.0 if any(term in lowered_url for term in ["portal", "apply", "application", "online"]) else -2.0
            if lowered_url.rstrip("/") == page_url.lower().rstrip("/"):
                score -= 6.0
            return score

        ranked_links = sorted(
            unique_preserve_order(block.application_links),
            key=score_candidate,
            reverse=True,
        )
        best_link = ranked_links[0] if ranked_links else None
        if best_link and score_candidate(best_link) >= 8:
            confidence = 0.92 if "portal" in best_link.lower() or "online." in best_link.lower() else 0.84
            return ApplicationChannel.ONLINE_FORM, best_link, best_link, confidence
    text_urls = extract_urls(text)
    if text_urls:
        for url in text_urls:
            lowered_url = url.lower()
            if any(term in lowered_url for term in APPLICATION_LINK_POSITIVE_TERMS):
                return ApplicationChannel.ONLINE_FORM, url, url, 0.86
    for channel, phrases in APPLICATION_TEXT_PATTERNS.items():
        for phrase in phrases:
            if phrase in lowered:
                if channel == ApplicationChannel.ONLINE_FORM:
                    fallback_url = page_url if any(token in page_url.lower() for token in ["apply", "application", "register"]) else None
                    if fallback_url:
                        return channel, fallback_url, phrase, 0.72
                    return ApplicationChannel.UNKNOWN, None, phrase, 0.45
                return channel, None, phrase, 0.72
    return ApplicationChannel.UNKNOWN, None, None, 0.0


def _extract_turnover_range(text: str, source_domain: str) -> Tuple[Optional[float], Optional[float], Optional[str], float]:
    sentences = _first_matching_sentences(text, ["turnover", "revenue", "annual sales"], limit=3)
    default_currency = infer_default_currency(text, source_domain)
    for sentence in sentences:
        minimum, maximum, _currency, snippet, confidence = extract_money_range(sentence, default_currency=default_currency)
        if minimum is not None or maximum is not None:
            return minimum, maximum, snippet, confidence
    return None, None, None, 0.0


def _extract_contact_details(text: str) -> Tuple[Optional[str], Optional[str]]:
    emails = extract_emails(text)
    phones = extract_phone_numbers(text)
    return (emails[0] if emails else None, phones[0] if phones else None)


def _publication_page_signals(page_url: str, page_title: Optional[str], text: str) -> List[str]:
    signals: List[str] = []
    lowered_url = (page_url or "").lower()
    lowered_title = (page_title or "").lower()
    lowered_text = (text or "").lower()
    for term in PUBLICATION_PATH_TERMS:
        if term in lowered_url:
            signals.append(term)
    for term in PUBLICATION_TEXT_TERMS:
        if term in lowered_title or term in lowered_text:
            signals.append(term)
    return unique_preserve_order(signals)


def _scoped_section_text(
    section_map: Dict[str, List[str]],
    heading_terms: Sequence[str],
    extra_heading_terms: Sequence[str] = (),
) -> str:
    matches: List[str] = []
    expected_terms = [term.lower() for term in heading_terms]
    expected_terms.extend([term.lower() for term in extra_heading_terms])
    for heading, values in section_map.items():
        lowered = heading.lower()
        if any(term in lowered for term in expected_terms):
            matches.extend(values)
    return clean_text(" ".join(matches))


def build_programme_record(
    block: CandidateBlock,
    page_url: str,
    page_title: Optional[str],
    settings: ScraperSettings,
) -> Tuple[Optional[FundingProgrammeRecord], List[FieldEvidence]]:
    combined_text = clean_text(" ".join([block.heading, block.text, page_title or ""]))
    if not combined_text:
        return None, []

    source_domain = extract_domain(page_url)
    source_scope = _source_scope_for_record(page_url, page_title, block.text, block.heading)
    default_currency = infer_default_currency(combined_text, source_domain)
    raw_text_snippets: Dict[str, List[str]] = {}
    extraction_confidence: Dict[str, float] = {}
    evidence_store: List[FieldEvidence] = []
    notes: List[str] = []

    identity_text = " ".join(unique_preserve_order([block.heading, page_title or "", " ".join(block.section_bundle.identity)]))
    overview_text = " ".join(block.section_bundle.overview or split_lines(combined_text)[:3])
    funding_text = " ".join(block.section_bundle.funding_offer or find_section_values(block.section_map, "funding", block.section_aliases))
    eligibility_text = " ".join(block.section_bundle.eligibility or find_section_values(block.section_map, "eligibility", block.section_aliases))
    terms_text = " ".join(block.section_bundle.terms_and_structure or find_section_values(block.section_map, "timing", block.section_aliases))
    application_text = " ".join(block.section_bundle.application_route or find_section_values(block.section_map, "application", block.section_aliases))
    related_documents_text = " ".join(block.section_bundle.related_documents or find_section_values(block.section_map, "documents", block.section_aliases))

    program_name = _infer_program_name(block, page_title)
    if program_name:
        _add_evidence(
            "program_name",
            program_name,
            block.heading or page_title,
            0.92 if block.heading else 0.7,
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=block.heading or page_title,
            source_section="identity",
            source_scope=source_scope,
            method="heading_based_inference",
        )

    funder_name = _infer_funder_name(page_title, combined_text)
    if funder_name:
        _add_evidence(
            "funder_name",
            funder_name,
            page_title or combined_text,
            0.68,
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=page_title or combined_text,
            source_section="identity",
            source_scope=source_scope,
            method="regex_from_prose",
        )

    funding_type, funding_type_confidence, funding_hits = classify_funding_type(" ".join([funding_text, overview_text, combined_text]))
    if funding_hits:
        _add_evidence(
            "funding_type",
            funding_type.value,
            ", ".join(funding_hits),
            funding_type_confidence,
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=funding_hits,
            source_section="funding_offer",
            source_scope=source_scope,
            method="deterministic_parser",
        )

    funding_lines = _extract_funding_lines(block, program_name)
    if funding_lines:
        _add_evidence(
            "funding_lines",
            funding_lines,
            take_best_snippet(funding_lines),
            0.72,
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=funding_lines,
            source_section="funding_offer",
            source_scope=source_scope,
            method="regex_from_prose",
        )

    raw_funding_offer_data = _extract_raw_funding_offer_data(block, combined_text)
    if raw_funding_offer_data:
        _add_evidence(
            "raw_funding_offer_data",
            raw_funding_offer_data,
            take_best_snippet(raw_funding_offer_data),
            0.8,
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=raw_funding_offer_data,
            source_section="funding_offer",
            source_scope=source_scope,
            method="direct_page_evidence",
        )

    ticket_min, ticket_max, currency, money_snippet, money_confidence = extract_money_range(
        funding_text or combined_text,
        default_currency=default_currency,
    )
    if money_snippet is None and funding_text:
        ticket_min, ticket_max, currency, money_snippet, money_confidence = extract_money_range(
            combined_text,
            default_currency=default_currency,
        )
    if money_snippet:
        _add_evidence(
            "ticket_range",
            {"ticket_min": ticket_min, "ticket_max": ticket_max, "currency": currency},
            money_snippet,
            money_confidence,
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=money_snippet,
            source_section="funding_offer",
            source_scope=source_scope,
            method="deterministic_parser",
        )

    budget_total, budget_currency, budget_snippet, budget_confidence = extract_budget_total(
        " ".join([funding_text, overview_text, combined_text]),
        default_currency=default_currency,
    )
    if budget_snippet:
        _add_evidence(
            "program_budget_total",
            budget_total,
            budget_snippet,
            budget_confidence,
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=budget_snippet,
            source_section="funding_offer",
            source_scope=source_scope,
            method="deterministic_parser",
        )
    currency = currency or budget_currency

    deadline_info = parse_deadline_info(terms_text or combined_text)
    if deadline_info["snippet"]:
        _add_evidence(
            "deadline",
            {"deadline_type": deadline_info["deadline_type"], "deadline_date": deadline_info["deadline_date"]},
            str(deadline_info["snippet"]),
            float(deadline_info["confidence"]),
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=deadline_info["snippet"],
            source_section="terms_and_structure",
            source_scope=source_scope,
            method="deterministic_parser",
        )

    funding_speed_days_min, funding_speed_days_max, speed_snippet, speed_confidence = _extract_day_range(
        terms_text or combined_text,
        ["turnaround", "processing time", "funding within", "approval within"],
    )
    if speed_snippet:
        _add_evidence(
            "funding_speed",
            {"min": funding_speed_days_min, "max": funding_speed_days_max},
            speed_snippet,
            speed_confidence,
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=speed_snippet,
            source_section="terms_and_structure",
            source_scope=source_scope,
            method="deterministic_parser",
        )

    geography = classify_geography(eligibility_text or combined_text, settings)
    if geography["evidence"]:
        _add_evidence(
            "geography",
            {
                "scope": geography["geography_scope"].value,
                "provinces": geography["provinces"],
                "municipalities": geography["municipalities"],
            },
            ", ".join(geography["evidence"]),
            0.76,
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=geography["evidence"],
            source_section="eligibility",
            source_scope=source_scope,
            method="deterministic_parser",
        )
    notes.extend(geography["notes"])

    industries_text = " ".join(block.section_bundle.overview + block.section_bundle.funding_offer + block.section_bundle.eligibility) or combined_text
    industries_text = _scoped_section_text(
        block.section_map,
        INDUSTRY_SECTION_HINTS,
        block.section_aliases.get("industries", ()),
    ) or industries_text
    industries, industries_evidence = classify_industries(industries_text, settings)
    if industries:
        _add_evidence(
            "industries",
            industries,
            ", ".join(sum(industries_evidence.values(), [])),
            0.72,
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=industries_evidence,
            source_section="overview",
            source_scope=source_scope,
            method="deterministic_parser",
        )

    use_of_funds_text = (
        " ".join(block.section_bundle.funding_offer + block.section_bundle.overview + block.section_bundle.identity)
        or combined_text
    )
    use_of_funds_text = _scoped_section_text(
        block.section_map,
        USE_OF_FUNDS_SECTION_HINTS,
        block.section_aliases.get("funding", ()) + block.section_aliases.get("use_of_funds", ()),
    ) or use_of_funds_text
    use_of_funds, use_of_funds_evidence = classify_use_of_funds(use_of_funds_text, settings)
    if use_of_funds:
        _add_evidence(
            "use_of_funds",
            use_of_funds,
            ", ".join(sum(use_of_funds_evidence.values(), [])),
            0.74,
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=use_of_funds_evidence,
            source_section="funding_offer",
            source_scope=source_scope,
            method="deterministic_parser",
        )

    business_stage, business_stage_evidence = _extract_stage_eligibility(eligibility_text or combined_text)
    if business_stage:
        _add_evidence(
            "business_stage_eligibility",
            business_stage,
            ", ".join(business_stage_evidence),
            0.68,
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=business_stage_evidence,
            source_section="eligibility",
            source_scope=source_scope,
            method="deterministic_parser",
        )

    ownership_targets, ownership_evidence = classify_ownership_targets(eligibility_text or combined_text, settings)
    ownership_thresholds = _ownership_thresholds(eligibility_text or combined_text)
    percentage_mentions = _percentage_mentions(eligibility_text or combined_text)
    if ownership_thresholds:
        ownership_targets = unique_preserve_order([*ownership_targets, *ownership_thresholds])
        ownership_evidence = {**ownership_evidence, "thresholds": ownership_thresholds}
    if percentage_mentions:
        ownership_targets = unique_preserve_order([*ownership_targets, *percentage_mentions])
        ownership_evidence = {**ownership_evidence, "percentages": percentage_mentions}
    if ownership_targets:
        _add_evidence(
            "ownership_targets",
            ownership_targets,
            ", ".join(sum(ownership_evidence.values(), [])) if isinstance(ownership_evidence, dict) else ", ".join(ownership_targets),
            0.76,
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=ownership_evidence,
            source_section="eligibility",
            source_scope=source_scope,
            method="deterministic_parser",
        )

    entity_types_allowed, entity_type_evidence = match_keyword_map(eligibility_text or combined_text, settings.entity_type_keywords)
    if entity_types_allowed:
        _add_evidence(
            "entity_types_allowed",
            entity_types_allowed,
            ", ".join(sum(entity_type_evidence.values(), [])),
            0.64,
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=entity_type_evidence,
            source_section="eligibility",
            source_scope=source_scope,
            method="deterministic_parser",
        )

    certifications_required, certification_evidence = match_keyword_map(eligibility_text or combined_text, settings.certification_keywords)
    if certifications_required:
        _add_evidence(
            "certifications_required",
            certifications_required,
            ", ".join(sum(certification_evidence.values(), [])),
            0.66,
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=certification_evidence,
            source_section="eligibility",
            source_scope=source_scope,
            method="deterministic_parser",
        )

    turnover_min, turnover_max, turnover_snippet, turnover_confidence = _extract_turnover_range(eligibility_text or combined_text, source_domain)
    turnover_min, turnover_max, turnover_swapped = _normalize_ordered_pair(turnover_min, turnover_max)
    if turnover_swapped:
        notes.append("Turnover range values were inverted in source text and were normalized.")
    if turnover_snippet:
        _add_evidence(
            "turnover",
            {"min": turnover_min, "max": turnover_max},
            turnover_snippet,
            turnover_confidence,
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=turnover_snippet,
            source_section="eligibility",
            source_scope=source_scope,
            method="deterministic_parser",
        )

    years_in_business_min, years_in_business_max, years_snippet, years_confidence = _extract_numeric_range(
        eligibility_text or combined_text,
        ["years in business", "years operating", "trading for", "years of operation"],
    )
    years_in_business_min, years_in_business_max, years_swapped = _normalize_ordered_pair(
        years_in_business_min,
        years_in_business_max,
    )
    if years_swapped:
        notes.append("Years-in-business range values were inverted in source text and were normalized.")
    if years_snippet:
        _add_evidence(
            "years_in_business",
            {"min": years_in_business_min, "max": years_in_business_max},
            years_snippet,
            years_confidence,
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=years_snippet,
            source_section="eligibility",
            source_scope=source_scope,
            method="deterministic_parser",
        )

    employee_min_raw, employee_max_raw, employee_snippet, employee_confidence = _extract_numeric_range(
        eligibility_text or combined_text,
        ["employees", "staff", "full-time employees", "headcount"],
    )
    employee_min = int(employee_min_raw) if employee_min_raw is not None else None
    employee_max = int(employee_max_raw) if employee_max_raw is not None else None
    employee_min, employee_max, employee_swapped = _normalize_ordered_pair(employee_min, employee_max)
    if employee_swapped:
        notes.append("Employee range values were inverted in source text and were normalized.")
    if employee_snippet:
        _add_evidence(
            "employees",
            {"min": employee_min, "max": employee_max},
            employee_snippet,
            employee_confidence,
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=employee_snippet,
            source_section="eligibility",
            source_scope=source_scope,
            method="deterministic_parser",
        )

    payback_details = extract_payback_details(terms_text or combined_text)
    payback_months_min = payback_details.term_min_months
    payback_months_max = payback_details.term_max_months
    payback_snippet = payback_details.raw_text
    payback_confidence = payback_details.confidence
    if payback_months_min is None and payback_months_max is None:
        payback_months_min, payback_months_max, payback_snippet_legacy, payback_confidence_legacy = _extract_month_range(
            terms_text or combined_text,
            ["repayment", "repayable", "loan term", "tenor", "repayment term", "payback", "moratorium", "grace period"],
        )
        payback_months_min, payback_months_max, payback_swapped = _normalize_ordered_pair(payback_months_min, payback_months_max)
        if payback_swapped:
            notes.append("Payback range values were inverted in source text and were normalized.")
        if not payback_snippet:
            payback_snippet = payback_snippet_legacy
        payback_confidence = max(payback_confidence, payback_confidence_legacy)
    if payback_snippet:
        _add_evidence(
            "payback_raw_text",
            payback_snippet,
            payback_snippet,
            payback_confidence,
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=payback_snippet,
            source_section="terms_and_structure",
            source_scope=source_scope,
            method="deterministic_parser",
        )
        _add_evidence(
            "payback_term_min_months",
            payback_months_min,
            payback_snippet,
            payback_confidence,
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=payback_snippet,
            source_section="terms_and_structure",
            source_scope=source_scope,
            method="deterministic_parser",
        )
        _add_evidence(
            "payback_term_max_months",
            payback_months_max,
            payback_snippet,
            payback_confidence,
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=payback_snippet,
            source_section="terms_and_structure",
            source_scope=source_scope,
            method="deterministic_parser",
        )
        if payback_details.structure:
            _add_evidence(
                "payback_structure",
                payback_details.structure,
                payback_details.structure,
                payback_confidence,
                page_url,
                evidence_store,
                raw_text_snippets,
                extraction_confidence,
                raw_value=payback_details.structure,
                source_section="terms_and_structure",
                source_scope=source_scope,
                method="regex_from_prose",
            )
        if payback_details.grace_period_months is not None:
            _add_evidence(
                "grace_period_months",
                payback_details.grace_period_months,
                payback_snippet,
                payback_confidence,
                page_url,
                evidence_store,
                raw_text_snippets,
                extraction_confidence,
                raw_value=payback_snippet,
                source_section="terms_and_structure",
                source_scope=source_scope,
                method="regex_from_prose",
            )
        if payback_details.repayment_frequency != RepaymentFrequency.UNKNOWN:
            _add_evidence(
                "repayment_frequency",
                payback_details.repayment_frequency.value,
                payback_snippet,
                payback_confidence,
                page_url,
                evidence_store,
                raw_text_snippets,
                extraction_confidence,
                raw_value=payback_snippet,
                source_section="terms_and_structure",
                source_scope=source_scope,
                method="regex_from_prose",
            )

    raw_terms_data = _extract_raw_terms_data(block, combined_text)
    if raw_terms_data:
        _add_evidence(
            "raw_terms_data",
            raw_terms_data,
            take_best_snippet(raw_terms_data),
            0.7,
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=raw_terms_data,
            source_section="terms_and_structure",
            source_scope=source_scope,
            method="direct_page_evidence",
        )

    security_required, security_snippet, security_confidence = _classify_tristate(terms_text or combined_text, SECURITY_PATTERNS)
    if security_snippet:
        _add_evidence(
            "security_required",
            security_required.value,
            security_snippet,
            security_confidence,
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=security_snippet,
            source_section="terms_and_structure",
            source_scope=source_scope,
            method="regex_from_prose",
        )

    equity_required, equity_snippet, equity_confidence = _classify_tristate(terms_text or combined_text, EQUITY_PATTERNS)
    if equity_snippet:
        _add_evidence(
            "equity_required",
            equity_required.value,
            equity_snippet,
            equity_confidence,
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=equity_snippet,
            source_section="terms_and_structure",
            source_scope=source_scope,
            method="regex_from_prose",
        )

    interest_type, interest_snippet, interest_confidence = _classify_enum(terms_text or combined_text, INTEREST_PATTERNS, InterestType.UNKNOWN)
    if interest_snippet:
        _add_evidence(
            "interest_type",
            interest_type.value,
            interest_snippet,
            interest_confidence,
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=interest_snippet,
            source_section="terms_and_structure",
            source_scope=source_scope,
            method="regex_from_prose",
        )

    repayment_frequency, repayment_snippet, repayment_confidence = _classify_enum(
        terms_text or combined_text,
        REPAYMENT_PATTERNS,
        payback_details.repayment_frequency if payback_details.repayment_frequency != RepaymentFrequency.UNKNOWN else RepaymentFrequency.UNKNOWN,
    )
    if repayment_snippet:
        _add_evidence(
            "repayment_frequency",
            repayment_frequency.value,
            repayment_snippet,
            repayment_confidence,
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=repayment_snippet,
            source_section="terms_and_structure",
            source_scope=source_scope,
            method="regex_from_prose",
        )

    raw_eligibility_data = _extract_eligibility_items(block)
    if raw_eligibility_data:
        _add_evidence(
            "raw_eligibility_data",
            raw_eligibility_data,
            take_best_snippet(raw_eligibility_data),
            0.8,
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=raw_eligibility_data,
            source_section="eligibility",
            source_scope=source_scope,
            method="direct_page_evidence",
        )
    raw_eligibility_criteria = _extract_eligibility_criteria_items(block, raw_eligibility_data or [])
    if raw_eligibility_criteria:
        _add_evidence(
            "raw_eligibility_criteria",
            raw_eligibility_criteria,
            take_best_snippet(raw_eligibility_criteria),
            0.88,
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=raw_eligibility_criteria,
            source_section="eligibility",
            source_scope=source_scope,
            method="deterministic_parser",
        )

    exclusions = _extract_exclusions(block)
    if exclusions:
        _add_evidence(
            "exclusions",
            exclusions,
            take_best_snippet(exclusions),
            0.76,
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=exclusions,
            source_section="eligibility",
            source_scope=source_scope,
            method="regex_from_prose",
        )

    required_documents = _extract_required_documents(block)
    if required_documents:
        _add_evidence(
            "required_documents",
            required_documents,
            take_best_snippet(required_documents),
            0.74,
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=required_documents,
            source_section="related_documents",
            source_scope=source_scope,
            method="direct_page_evidence",
        )

    raw_documents_data = unique_preserve_order(required_documents + split_lines(related_documents_text))
    if raw_documents_data:
        _add_evidence(
            "raw_documents_data",
            raw_documents_data,
            take_best_snippet(raw_documents_data),
            0.72,
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=raw_documents_data,
            source_section="related_documents",
            source_scope=source_scope,
            method="direct_page_evidence",
        )

    application_channel, application_url, application_snippet, application_confidence = _pick_application_route(
        block,
        page_url,
        application_text or combined_text,
    )
    if application_snippet:
        _add_evidence(
            "application_route",
            {"application_channel": application_channel.value, "application_url": application_url},
            application_snippet,
            application_confidence,
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=application_snippet,
            source_section="application_route",
            source_scope=source_scope,
            method="direct_page_evidence" if block.application_links else "regex_from_prose",
        )

    related_documents = unique_preserve_order([*block.document_links, *extract_urls(combined_text)])
    contact_email, contact_phone = _extract_contact_details(combined_text)
    if contact_email:
        _add_evidence(
            "contact_email",
            contact_email,
            contact_email,
            0.9,
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=contact_email,
            source_section="application_route",
            source_scope=source_scope,
            method="deterministic_parser",
        )
    if contact_phone:
        _add_evidence(
            "contact_phone",
            contact_phone,
            contact_phone,
            0.9,
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=contact_phone,
            source_section="application_route",
            source_scope=source_scope,
            method="deterministic_parser",
        )

    raw_application_data = _extract_raw_application_data(block, combined_text)
    if raw_application_data:
        _add_evidence(
            "raw_application_data",
            raw_application_data,
            take_best_snippet(raw_application_data),
            0.74,
            page_url,
            evidence_store,
            raw_text_snippets,
            extraction_confidence,
            raw_value=raw_application_data,
            source_section="application_route",
            source_scope=source_scope,
            method="direct_page_evidence",
        )
    if (
        application_channel == ApplicationChannel.UNKNOWN
        and not application_url
        and (contact_email or contact_phone or raw_application_data)
    ):
        application_channel = ApplicationChannel.MANUAL_CONTACT_FIRST
        application_snippet = application_snippet or take_best_snippet(raw_application_data, default=contact_email or contact_phone or "")
        application_confidence = max(application_confidence, 0.62)
        if application_snippet:
            _add_evidence(
                "application_route",
                {"application_channel": application_channel.value, "application_url": application_url},
                application_snippet,
                application_confidence,
                page_url,
                evidence_store,
                raw_text_snippets,
                extraction_confidence,
                raw_value=application_snippet,
                source_section="application_route",
                source_scope=source_scope,
                method="regex_from_prose",
            )

    publication_signals = _publication_page_signals(page_url, page_title, combined_text)
    if publication_signals:
        notes.append("Page looks like an article/publication page: %s." % ", ".join(publication_signals))

    if detect_archive_signals(combined_text):
        notes.append("Page may describe an archived or closed funding programme.")
    if looks_expired(combined_text, deadline_info["deadline_date"]):
        notes.append("Programme may be closed or expired; verify before publishing.")
    if not industries and any(term in combined_text.lower() for term in ["sector", "industry", "focus areas"]):
        notes.append("Industry-specific wording detected but no taxonomy match was found.")

    if not any(
        [
            program_name,
            funding_lines,
            raw_eligibility_data,
            raw_eligibility_criteria,
            application_url,
            ticket_min,
            ticket_max,
            funding_type.value != "Unknown",
        ]
    ):
        support_programme_hint = any(
            term in combined_text.lower()
            for term in [
                "mentorship",
                "market linkage",
                "market linkages",
                "business management training",
                "voucher",
                "thusano",
                "sponsorship",
                "business support",
            ]
        )
        if not support_programme_hint:
            return None, evidence_store

    derived_status = _derive_programme_status(
        combined_text=combined_text,
        notes=notes,
        deadline_type=DeadlineType(str(deadline_info["deadline_type"])),
        deadline_date=deadline_info["deadline_date"],
    )

    evidence_map = _normalize_evidence_map(evidence_store)
    confidence_map = _confidence_map_from_evidence(evidence_map)
    raw_text_snippets = {
        field_name: [item.evidence_text for item in items if item.evidence_text]
        for field_name, items in evidence_map.items()
        if items
    }
    field_evidence = evidence_map

    record = FundingProgrammeRecord(
        program_name=program_name,
        funder_name=funder_name,
        source_url=page_url,
        source_urls=[page_url],
        source_domain=source_domain,
        source_page_title=page_title,
        source_scope=source_scope,
        scraped_at=datetime.now(timezone.utc),
        last_scraped_at=datetime.now(timezone.utc),
        raw_eligibility_data=raw_eligibility_data or None,
        raw_eligibility_criteria=raw_eligibility_criteria,
        raw_funding_offer_data=raw_funding_offer_data,
        raw_terms_data=raw_terms_data,
        raw_documents_data=raw_documents_data,
        raw_application_data=raw_application_data,
        evidence_by_field=raw_text_snippets,
        field_confidence=confidence_map,
        extraction_confidence=confidence_map,
        field_evidence=field_evidence,
        funding_type=funding_type,
        funding_lines=funding_lines,
        ticket_min=ticket_min,
        ticket_max=ticket_max,
        currency=currency,
        program_budget_total=budget_total,
        deadline_type=DeadlineType(str(deadline_info["deadline_type"])),
        deadline_date=deadline_info["deadline_date"],
        status=derived_status,
        funding_speed_days_min=funding_speed_days_min,
        funding_speed_days_max=funding_speed_days_max,
        geography_scope=geography["geography_scope"],
        provinces=geography["provinces"],
        municipalities=geography["municipalities"],
        postal_code_ranges=geography["postal_code_ranges"],
        industries=industries,
        use_of_funds=use_of_funds,
        business_stage_eligibility=business_stage,
        turnover_min=turnover_min,
        turnover_max=turnover_max,
        years_in_business_min=years_in_business_min,
        years_in_business_max=years_in_business_max,
        employee_min=employee_min,
        employee_max=employee_max,
        ownership_targets=ownership_targets,
        entity_types_allowed=entity_types_allowed,
        certifications_required=certifications_required,
        security_required=security_required,
        equity_required=equity_required,
        payback_months_min=payback_months_min,
        payback_months_max=payback_months_max,
        payback_raw_text=payback_details.raw_text or payback_snippet,
        payback_term_min_months=payback_details.term_min_months if payback_details.term_min_months is not None else payback_months_min,
        payback_term_max_months=payback_details.term_max_months if payback_details.term_max_months is not None else payback_months_max,
        payback_structure=payback_details.structure,
        grace_period_months=payback_details.grace_period_months,
        interest_type=interest_type,
        repayment_frequency=repayment_frequency,
        payback_confidence=payback_details.confidence or payback_confidence,
        exclusions=exclusions,
        required_documents=required_documents,
        application_channel=application_channel,
        application_url=application_url,
        contact_email=contact_email,
        contact_phone=contact_phone,
        raw_text_snippets=raw_text_snippets,
        related_documents=related_documents,
        notes=unique_preserve_order(notes),
    )
    debug_package = PageDebugPackage(
        page_url=page_url,
        final_url=page_url,
        page_title=page_title,
        cleaned_text=combined_text,
        section_tree=block.section_tree,
        extracted_evidence_map=evidence_map,
        confidence_map=confidence_map,
        records=[
            PageDebugRecord(
                program_name=record.program_name,
                parent_programme_name=record.parent_programme_name,
                source_scope=source_scope,
                evidence_map=evidence_map,
                confidence_map=confidence_map,
                notes=record.notes,
            )
        ],
    )
    final_record = FundingProgrammeRecord.model_validate(record.model_dump(mode="python"))
    return final_record, evidence_store


def classify_page_type(
    record_count: int,
    candidate_block_count: int,
    internal_link_count: int,
    detail_link_count: int,
    application_link_count: int,
    document_link_count: int,
    text: str,
) -> str:
    return classify_global_page_type(
        record_count=record_count,
        candidate_block_count=candidate_block_count,
        internal_link_count=internal_link_count,
        detail_link_count=detail_link_count,
        application_link_count=application_link_count,
        document_link_count=document_link_count,
        text=text,
    )
