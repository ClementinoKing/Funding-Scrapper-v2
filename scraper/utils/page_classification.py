"""Global page classification and persistence gates for funding pages."""

from __future__ import annotations

import re
from typing import Any, Iterable, Optional, Tuple
from urllib.parse import urlparse

from scraper.schemas import FundingProgrammeRecord, FundingType
from scraper.utils.text import clean_text, unique_preserve_order


PAGE_TYPE_FUNDING_PROGRAMME = "funding_programme"
PAGE_TYPE_FUNDING_LISTING = "funding_listing"
PAGE_TYPE_SUPPORT_PROGRAMME = "support_programme"
PAGE_TYPE_TECHNOLOGY_STATION = "technology_station"
PAGE_TYPE_OPEN_CALL = "open_call"
PAGE_TYPE_TENDER_PROCUREMENT = "tender_procurement"
PAGE_TYPE_NEWS_ARTICLE = "news_article"
PAGE_TYPE_GENERIC_CONTENT = "generic_content"

PERSISTABLE_PAGE_TYPES = {
    PAGE_TYPE_FUNDING_PROGRAMME,
    PAGE_TYPE_FUNDING_LISTING,
}

REVIEW_PAGE_TYPES = {
    PAGE_TYPE_FUNDING_LISTING,
    PAGE_TYPE_NEWS_ARTICLE,
    PAGE_TYPE_TENDER_PROCUREMENT,
}

FUNDABLE_SUPPORT_TERMS = (
    "grant",
    "loan",
    "equity",
    "investment",
    "finance",
    "funding",
    "funded",
    "fundable",
    "voucher",
    "prize money",
    "cash prize",
    "stipend",
    "startup capital",
    "start-up capital",
    "working capital",
    "capital support",
    "seed capital",
    "funded incubation",
    "funded acceleration",
    "matching funds",
)

TENDER_TITLE_TERMS = (
    "tender",
    "bid",
    "rfp",
    "rfq",
    "request for proposal",
    "request for quotation",
    "procurement",
    "supply and delivery",
    "appointment of",
)

PROCUREMENT_TEXT_TERMS = (
    "tender",
    "procurement",
    "bid number",
    "tender number",
    "rfp",
    "rfq",
    "request for proposal",
    "request for quotation",
    "compulsory briefing",
    "supply chain",
)

NEWS_TEXT_TERMS = (
    "news",
    "article",
    "press release",
    "media release",
    "published on",
    "read more",
    "story",
    "announced",
)

TECHNOLOGY_STATION_TERMS = (
    "technology station",
    "technology stations",
    "technology transfer",
    "prototype support",
    "product development support",
    "technical assistance",
)

SUPPORT_PROGRAMME_TERMS = (
    "mentorship",
    "training",
    "incubation",
    "acceleration",
    "business development support",
    "non-financial support",
    "technical support",
    "advisory support",
)


def normalize_page_type(value: Any) -> str:
    text = clean_text(str(value or "")).casefold().replace("-", "_").replace("/", "_").replace(" ", "_")
    aliases = {
        "funding_program": PAGE_TYPE_FUNDING_PROGRAMME,
        "funding_programme": PAGE_TYPE_FUNDING_PROGRAMME,
        "programme": PAGE_TYPE_FUNDING_PROGRAMME,
        "program": PAGE_TYPE_FUNDING_PROGRAMME,
        "detail": PAGE_TYPE_FUNDING_PROGRAMME,
        "product_page": PAGE_TYPE_FUNDING_PROGRAMME,
        "listing": PAGE_TYPE_FUNDING_LISTING,
        "programme_listing": PAGE_TYPE_FUNDING_LISTING,
        "program_listing": PAGE_TYPE_FUNDING_LISTING,
        "funding_listing": PAGE_TYPE_FUNDING_LISTING,
        "support": PAGE_TYPE_SUPPORT_PROGRAMME,
        "support_program": PAGE_TYPE_SUPPORT_PROGRAMME,
        "support_programme": PAGE_TYPE_SUPPORT_PROGRAMME,
        "technology_station": PAGE_TYPE_TECHNOLOGY_STATION,
        "open_call": PAGE_TYPE_OPEN_CALL,
        "call": PAGE_TYPE_OPEN_CALL,
        "call_for_applications": PAGE_TYPE_OPEN_CALL,
        "tender": PAGE_TYPE_TENDER_PROCUREMENT,
        "procurement": PAGE_TYPE_TENDER_PROCUREMENT,
        "tender_procurement": PAGE_TYPE_TENDER_PROCUREMENT,
        "news": PAGE_TYPE_NEWS_ARTICLE,
        "article": PAGE_TYPE_NEWS_ARTICLE,
        "news_article": PAGE_TYPE_NEWS_ARTICLE,
        "generic": PAGE_TYPE_GENERIC_CONTENT,
        "generic_content": PAGE_TYPE_GENERIC_CONTENT,
        "unknown": PAGE_TYPE_GENERIC_CONTENT,
        "mixed": PAGE_TYPE_FUNDING_LISTING,
    }
    return aliases.get(text, PAGE_TYPE_GENERIC_CONTENT)


def classify_global_page_type(
    *,
    record_count: int = 0,
    candidate_block_count: int = 0,
    internal_link_count: int = 0,
    detail_link_count: int = 0,
    application_link_count: int = 0,
    document_link_count: int = 0,
    text: str = "",
) -> str:
    lowered = clean_text(text or "").casefold()
    path = urlparse(lowered).path if "://" in lowered else ""
    haystack = " ".join([lowered, path])

    if any(term in haystack for term in PROCUREMENT_TEXT_TERMS):
        return PAGE_TYPE_TENDER_PROCUREMENT
    if any(term in haystack for term in TECHNOLOGY_STATION_TERMS):
        if not any(term in haystack for term in FUNDABLE_SUPPORT_TERMS):
            return PAGE_TYPE_TECHNOLOGY_STATION
    if any(term in haystack for term in SUPPORT_PROGRAMME_TERMS) and not any(term in haystack for term in FUNDABLE_SUPPORT_TERMS):
        return PAGE_TYPE_SUPPORT_PROGRAMME
    if any(term in haystack for term in NEWS_TEXT_TERMS) and not (_has_programme_detail_signals(haystack) or any(term in haystack for term in FUNDABLE_SUPPORT_TERMS)):
        return PAGE_TYPE_NEWS_ARTICLE
    if "open call" in haystack or "call for applications" in haystack:
        return PAGE_TYPE_OPEN_CALL
    if record_count > 1 or candidate_block_count > 1 or detail_link_count > 2 or (internal_link_count > 8 and record_count <= 1):
        return PAGE_TYPE_FUNDING_LISTING
    if any(term in haystack for term in FUNDABLE_SUPPORT_TERMS):
        return PAGE_TYPE_FUNDING_PROGRAMME
    if application_link_count or document_link_count or _has_programme_detail_signals(haystack):
        return PAGE_TYPE_FUNDING_PROGRAMME
    return PAGE_TYPE_GENERIC_CONTENT


def has_fundable_support(record: FundingProgrammeRecord) -> bool:
    if record.funding_type != FundingType.UNKNOWN:
        return True
    if record.ticket_min is not None or record.ticket_max is not None or record.program_budget_total is not None:
        return True
    haystack = _record_text(record)
    return any(term in haystack for term in FUNDABLE_SUPPORT_TERMS)


def should_persist_record(record: FundingProgrammeRecord) -> Tuple[bool, Optional[str]]:
    page_type = normalize_page_type(record.page_type)
    record.page_type = page_type
    if page_type in PERSISTABLE_PAGE_TYPES:
        return True, None
    if page_type == PAGE_TYPE_OPEN_CALL and has_fundable_support(record):
        return True, None
    return False, f"page_type {page_type} is not persistable funding programme content"


def mark_review_reasons(record: FundingProgrammeRecord) -> FundingProgrammeRecord:
    reasons = []
    page_type = normalize_page_type(record.page_type)
    record.page_type = page_type
    haystack = _record_text(record)
    if record.funding_type == FundingType.UNKNOWN:
        reasons.append("funding_type is Unknown")
    if (record.ticket_min is not None or record.ticket_max is not None) and record.extraction_confidence.get("ticket_range", 1.0) < 0.7:
        reasons.append("amount evidence is weak")
    if page_type in REVIEW_PAGE_TYPES:
        reasons.append(f"page_type {page_type} requires review")
    if looks_like_tender_title(record.program_name):
        reasons.append("programme_name looks like a tender title")
    if mostly_article_news_or_procurement(haystack):
        reasons.append("source page contains mostly article/news/procurement wording")
    if reasons:
        record.needs_review = True
        record.validation_errors = unique_preserve_order([*record.validation_errors, *reasons])
        record.notes = unique_preserve_order([*record.notes, *[f"Review flag: {reason}." for reason in reasons]])
    return record


def looks_like_tender_title(value: Optional[str]) -> bool:
    lowered = clean_text(value or "").casefold()
    if not lowered:
        return False
    if re.search(r"\b(?:bid|tender|rfp|rfq)[\s#:.-]*\d", lowered):
        return True
    return any(term in lowered for term in TENDER_TITLE_TERMS)


def mostly_article_news_or_procurement(text: str) -> bool:
    lowered = clean_text(text or "").casefold()
    if not lowered:
        return False
    risky_hits = sum(1 for term in (*PROCUREMENT_TEXT_TERMS, *NEWS_TEXT_TERMS) if term in lowered)
    funding_hits = sum(1 for term in FUNDABLE_SUPPORT_TERMS if term in lowered)
    return risky_hits >= 3 and risky_hits >= funding_hits


def _has_programme_detail_signals(text: str) -> bool:
    detail_terms = (
        "eligibility",
        "who can apply",
        "application",
        "apply now",
        "funding amount",
        "loan amount",
        "grant amount",
        "ticket size",
        "qualifying criteria",
        "repayment",
    )
    return sum(1 for term in detail_terms if term in text) >= 2


def _record_text(record: FundingProgrammeRecord) -> str:
    parts: Iterable[Any] = [
        record.program_name,
        record.funder_name,
        record.parent_programme_name,
        record.source_url,
        record.source_page_title,
        record.page_type,
        record.funding_type.value if hasattr(record.funding_type, "value") else record.funding_type,
        record.funding_lines,
        record.raw_eligibility_data,
        record.raw_eligibility_criteria,
        record.raw_funding_offer_data,
        record.raw_terms_data,
        record.raw_application_data,
        record.notes,
    ]
    flattened = []
    for part in parts:
        if isinstance(part, list):
            flattened.extend(str(item) for item in part)
        elif part is not None:
            flattened.append(str(part))
    return clean_text(" ".join(flattened)).casefold()
