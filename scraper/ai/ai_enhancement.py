"""AI-first classification for raw page content."""

from __future__ import annotations

import base64
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

import httpx
import structlog
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError, field_validator
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from scraper import __version__ as SCRAPER_VERSION
from scraper.classifiers.eligibility import extract_eligibility_criteria
from scraper.schemas import (
    CandidateBlockSnapshot,
    AIMergeDecisionResponse,
    AIClassificationResponse,
    AIProgrammeDraft,
    DocumentEvidenceSnapshot,
    ApprovalStatus,
    ApplicationChannel,
    DeadlineType,
    FundingProgrammeRecord,
    FundingType,
    GeographyScope,
    InterestType,
    PageContentDocument,
    PageContentSection,
    PageAIRecordSnapshot,
    ProgrammeStatus,
    RepaymentFrequency,
    TriState,
)
from scraper.classifiers.repayment import extract_payback_details
from scraper.utils.document_reader import compact_document_text, extract_local_document_text, infer_document_kind
from scraper.utils.dates import parse_deadline_info
from scraper.utils.money import extract_budget_total, extract_money_range, infer_default_currency
from scraper.utils.page_classification import (
    _has_programme_detail_signals,
    classify_global_page_type,
    PAGE_TYPE_FUNDING_LISTING,
    PAGE_TYPE_FUNDING_PROGRAMME,
    PAGE_TYPE_GENERIC_CONTENT,
    PAGE_TYPE_NEWS_ARTICLE,
    PAGE_TYPE_OPEN_CALL,
    PAGE_TYPE_SUPPORT_PROGRAMME,
    PAGE_TYPE_TECHNOLOGY_STATION,
    PAGE_TYPE_TENDER_PROCUREMENT,
    has_fundable_support,
    looks_like_tender_title,
    normalize_page_type,
)
from scraper.utils.text import (
    clean_text,
    extract_emails,
    extract_phone_numbers,
    extract_urls,
    looks_like_support_title,
    match_keyword_map,
    sentence_chunks,
    strip_leading_numbered_prefix,
    unique_preserve_order,
)
from scraper.utils.urls import canonicalize_url, document_link_matches_context, extract_domain


logger = structlog.get_logger()

PROMPT_KEYWORDS = ("fund", "eligibility", "criteria", "requirements", "investment", "loan", "repayment", "payback", "tenor", "moratorium")
MAX_SECTION_CHARS = 1800
MAX_BODY_CHARS = 8000
MAX_PROMPT_CHARS = 22000
MAX_DOCUMENT_SUMMARY_CHARS = 2400
PAGE_DECISION_FUNDING_PROGRAM = "funding_program"
PAGE_DECISION_NOT_FUNDING_PROGRAM = "not_funding_program"
PAGE_DECISION_UNCLEAR = "unclear"
COMMON_TLDS = {"com", "co", "org", "net", "za", "gov", "edu", "ac", "io", "biz", "info", "co.za", "org.za", "gov.za"}
DOMAIN_FUNDER_ALIASES = {
    "pic.gov.za": "Public Investment Corporation",
    "www.pic.gov.za": "Public Investment Corporation",
}
PROGRAMME_SIGNAL_TERMS = (
    "funding",
    "fund",
    "grant",
    "loan",
    "equity",
    "investment",
    "finance",
    "programme",
    "program",
    "eligibility",
    "criteria",
    "apply",
    "application",
    "who qualifies",
    "support for entrepreneurs",
)
FUNDER_SEPARATOR_PATTERN = re.compile(r"\s+(?:[-|:–—])\s+")
FUNDER_HINT_TERMS = (
    "fund",
    "foundation",
    "agency",
    "department",
    "corporation",
    "council",
    "bank",
    "trust",
    "enterprise",
    "investment",
    "development",
    "authority",
    "institute",
    "society",
    "group",
)
GENERIC_FUNDER_TOKENS = {
    "home",
    "products",
    "services",
    "support",
    "funding",
    "programme",
    "program",
    "page",
    "overview",
    "about",
    "apply",
    "application",
    "contact",
}
NON_PROGRAMME_SIGNAL_TERMS = (
    "news",
    "article",
    "blog",
    "press release",
    "media",
    "publication",
    "case study",
    "success story",
    "about us",
    "contact us",
    "privacy",
    "terms",
    "policy",
    "screenshot",
    "image",
    "gallery",
    "attachment",
)
PAGE_ROLE_OVERVIEW = "overview"
PAGE_ROLE_ELIGIBILITY = "eligibility"
PAGE_ROLE_APPLICATION = "application"
PAGE_ROLE_CHECKLIST = "checklist"
PAGE_ROLE_FUNDING_DETAIL = "funding_detail"
PAGE_ROLE_LISTING = "listing"
PAGE_ROLE_PROCUREMENT_NOTICE = "procurement_notice"
PAGE_ROLE_NEWS_ARTICLE = "news_article"
PAGE_ROLE_ABOUT_CONTACT = "about_contact"
PAGE_ROLE_SUPPORT_DETAIL = "support_detail"
PAGE_ROLE_TECHNOLOGY_STATION = "technology_station"
PAGE_ROLE_GENERIC = "generic"
REVIEW_REASON_UNKNOWN_FUNDING_TYPE = "unknown_funding_type"
REVIEW_REASON_WEAK_MONEY_EVIDENCE = "weak_money_evidence"
REVIEW_REASON_INVALID_MONEY_CONTEXT = "invalid_money_context"
REVIEW_REASON_NON_PROGRAMME_PAGE = "non_programme_page"
REVIEW_REASON_CONFLICTING_FIELD_VALUES = "conflicting_field_values"
REVIEW_REASON_MISSING_CORE_EVIDENCE = "missing_core_evidence"
REVIEW_REASON_WEAK_DUPLICATE_MATCH = "weak_duplicate_match"
REVIEW_REASON_MERGED_MULTI_PAGE = "merged_multi_page_record"
REVIEW_REASON_UNCONFIRMED_PAGE_TYPE = "unconfirmed_page_type"
REVIEW_REASON_INVALID_PROGRAM_NAME = "invalid_program_name"
REVIEW_REASON_INVALID_FUNDER_NAME = "invalid_funder_name"
REVIEW_REASON_LISTING_UNKNOWN_FUNDING_TYPE = "listing_unknown_funding_type"
REVIEW_REASON_SUPPORT_UNKNOWN_FUNDING_TYPE = "support_unknown_funding_type"
REVIEW_REASON_UNFUNDABLE_OPEN_CALL = "unfundable_open_call"
MONEY_INVALID_CONTEXT_RE = re.compile(
    r"\b(?:tender number|bid number|rfp|rfq|procurement|telephone|phone|fax|postal code|postcode|trl|technology readiness level)\b",
    re.I,
)
MONEY_INVALID_DATE_RE = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b")
MONEY_INVALID_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
MONEY_INVALID_PERCENT_RE = re.compile(r"\b\d{1,3}(?:\.\d+)?\s?%")
MONEY_INVALID_PHONE_RE = re.compile(r"(?:\+?\d[\s().-]*){7,}")
MONEY_INVALID_TRL_RE = re.compile(r"\btrl\s*\d+(?:\s*[-–]\s*\d+)?\b", re.I)
MONEY_POSITIVE_CONTEXT_RE = re.compile(r"\b(?:fund|funding|grant|loan|equity|investment|capital|ticket|amount|budget|finance)\b", re.I)
MONEY_SNIPPET_SIGNAL_RE = re.compile(
    r"(?:\b(?:zar|usd|eur|gbp)\b|(?:^|\s)[r$£]\s*\d|\b\d[\d\s,]*(?:\.\d+)?\s*(?:thousand|million|billion|mn|bn|k|m|b)\b)",
    re.I,
)
ABOUT_CONTACT_TERMS = ("about us", "about", "contact us", "contact", "privacy", "terms and conditions")
PAGE_ROLE_SUPPORT_SUFFIXES = (
    "apply",
    "application",
    "applications",
    "eligibility",
    "criteria",
    "checklist",
    "documents",
    "required-documents",
    "how-to-apply",
    "application-form",
    "overview",
    "terms",
    "funding",
    "register",
    "contact",
)
INVALID_PROGRAMME_NAME_TERMS = {
    "about",
    "about us",
    "apply",
    "application",
    "contact",
    "contact us",
    "eligibility",
    "eligibility criteria",
    "generic content",
    "funding",
    "funding opportunities",
    "funding programmes",
    "home",
    "latest news",
    "listing",
    "news",
    "news article",
    "open call",
    "overview",
    "products and services",
    "programme",
    "program",
    "required documents",
    "support",
}
INVALID_FUNDER_NAME_TERMS = GENERIC_FUNDER_TOKENS | {
    "about",
    "about us",
    "apply",
    "application",
    "contact",
    "contact us",
    "funding",
    "home",
    "listing",
    "news",
    "overview",
    "programme",
    "program",
    "support",
}
IMPORTANT_EVIDENCE_FIELDS = {
    "program_name",
    "funder_name",
    "funding_type",
    "ticket_min",
    "ticket_max",
    "program_budget_total",
    "deadline_type",
    "deadline_date",
    "application_url",
    "required_documents",
    "raw_eligibility_criteria",
}

ELIGIBILITY_STAGE_PATTERNS = {
    "startup": ("startup", "start-up", "new business", "early-stage business"),
    "seed": ("seed", "seed stage"),
    "early stage": ("early stage", "early-stage", "emerging business"),
    "growth stage": ("growth stage", "scale-up", "growth-focused"),
    "expansion": ("expansion", "expanding", "expand your business"),
    "established business": ("established business", "existing business", "trading for"),
}

CONTENT_BUCKET_TERMS = {
    "program": (
        "about",
        "overview",
        "summary",
        "programme",
        "program",
        "what is",
        "who we are",
    ),
    "eligibility": (
        "eligibility",
        "criteria",
        "requirements",
        "who can apply",
        "who qualifies",
        "qualifying",
        "applicant requirements",
        "funding requirements",
        "selection criteria",
    ),
    "funding": (
        "funding",
        "fund",
        "grant",
        "loan",
        "equity",
        "investment",
        "finance",
        "offer",
        "budget",
        "amount",
        "capital",
    ),
    "terms": (
        "terms",
        "conditions",
        "repayment",
        "payback",
        "interest",
        "tenor",
        "term",
        "moratorium",
        "grace period",
        "security",
        "collateral",
    ),
    "documents": (
        "document",
        "documents",
        "checklist",
        "guidelines",
        "brochure",
        "download",
        "certificate",
        "proof",
        "registration",
    ),
    "application": (
        "apply",
        "application",
        "portal",
        "submit",
        "submission",
        "register",
        "how to apply",
        "application process",
    ),
    "deadline": (
        "deadline",
        "closing date",
        "opening date",
        "intake",
        "applications close",
        "closing",
    ),
    "contact": (
        "contact",
        "email",
        "phone",
        "telephone",
        "whatsapp",
        "call us",
    ),
    "geography": (
        "national",
        "province",
        "municipality",
        "local",
        "south africa",
        "regional",
    ),
}

FIELD_EVIDENCE_SKIP_FIELDS = {
    "id",
    "program_id",
    "program_slug",
    "funder_slug",
    "created_at",
    "updated_at",
    "last_scraped_at",
    "last_verified_at",
    "scraped_at",
    "parser_version",
    "deleted_at",
    "field_evidence",
    "evidence_by_field",
    "extraction_confidence_by_field",
    "raw_text_snippets",
    "field_confidence",
    "validation_errors",
    "needs_review",
    "needs_review_reasons",
    "field_conflicts",
    "ai_enriched",
}

FIELD_EVIDENCE_CORE_FIELDS = {
    "program_name",
    "funder_name",
    "source_url",
    "source_urls",
    "source_domain",
    "source_page_title",
    "page_type",
    "page_role",
    "source_scope",
    "funding_type",
    "geography_scope",
    "application_channel",
    "application_url",
    "contact_email",
    "contact_phone",
    "deadline_type",
    "deadline_date",
    "ticket_min",
    "ticket_max",
    "program_budget_total",
    "payback_raw_text",
    "payback_structure",
    "payback_term_min_months",
    "payback_term_max_months",
    "payback_months_min",
    "payback_months_max",
    "grace_period_months",
    "interest_type",
    "repayment_frequency",
    "security_required",
    "equity_required",
    "required_documents",
    "related_documents",
    "raw_eligibility_data",
    "raw_eligibility_criteria",
    "raw_funding_offer_data",
    "raw_terms_data",
    "raw_documents_data",
    "raw_application_data",
    "funding_lines",
    "industries",
    "use_of_funds",
    "business_stage_eligibility",
    "turnover_min",
    "turnover_max",
    "years_in_business_min",
    "years_in_business_max",
    "employee_min",
    "employee_max",
    "ownership_targets",
    "entity_types_allowed",
    "certifications_required",
    "exclusions",
}


@dataclass(frozen=True)
class ContentItem:
    """One normalized text block extracted from the page payload."""

    item_type: str
    label: str
    content: str
    source_url: str
    source_section: Optional[str] = None
    source_scope: Optional[str] = None
    confidence_hint: float = 0.0
    order: int = 0


@dataclass
class FieldEvidenceBundle:
    """Aggregated field evidence collected from routed content items."""

    evidence_by_field: Dict[str, List[str]] = field(default_factory=dict)
    raw_text_snippets: Dict[str, List[str]] = field(default_factory=dict)
    field_confidence: Dict[str, float] = field(default_factory=dict)
    field_values: Dict[str, Any] = field(default_factory=dict)
    validation_errors: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class FallbackProgrammeCandidate:
    """One deterministic programme block found on a listing-like page."""

    label: str
    content: str
    source_scope: str
    source_section: Optional[str] = None


# Normalization helpers convert loose upstream values into compact text, numeric,
# and enum shapes before any AI prompt or record payload is assembled.
def _coerce_text(value: Any) -> str:
    return clean_text(str(value)) if value is not None else ""

# Optional text fields collapse to None instead of empty strings so the rest of
# the pipeline can treat "missing" consistently.
def _coerce_optional_text(value: Any) -> Optional[str]:
    text = _coerce_text(value)
    return text or None

# List-like inputs are normalized through the same cleaning path regardless of
# whether the caller passed a scalar, list, tuple, set, or dict.
def _coerce_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if isinstance(value, dict):
        value = list(value.values())
    if not isinstance(value, (list, tuple, set)):
        value = [value]
    cleaned = [clean_text(str(item)) for item in value if clean_text(str(item))]
    return unique_preserve_order(cleaned)

# Taxonomy configuration can arrive in several shapes; this flattens it into a
# stable mapping of label -> terms.
def _as_taxonomy(value: Any) -> Dict[str, List[str]]:
    if not isinstance(value, dict):
        return {}
    taxonomy: Dict[str, List[str]] = {}
    for key, terms in value.items():
        key_text = clean_text(str(key))
        if not key_text:
            continue
        if isinstance(terms, str):
            terms = [terms]
        if not isinstance(terms, (list, tuple, set)):
            terms = [terms]
        cleaned_terms = [clean_text(str(term)) for term in terms if clean_text(str(term))]
        if cleaned_terms:
            taxonomy[key_text] = unique_preserve_order(cleaned_terms)
    return taxonomy


# Numeric coercion first tries direct parsing, then falls back to money parsing
# when the text looks like a currency or amount phrase.
def _coerce_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = clean_text(str(value))
    if not text:
        return None
    numeric = re.sub(r"[^0-9.\-]", "", text)
    if numeric and numeric not in {"-", "."}:
        try:
            return float(numeric)
        except ValueError:
            pass
    if any(token in text.lower() for token in ["r", "zar", "usd", "eur", "gbp", "million", "thousand", "billion", "k", "m", "bn", "b"]):
        minimum, maximum, _currency, _snippet, _confidence = extract_money_range(text, default_currency=None)
        return minimum if minimum is not None else maximum
    return None


# Integers are derived from the float coercion path to keep the parsing rules
# identical for values that may include currency or formatting noise.
def _coerce_int(value: Any) -> Optional[int]:
    float_value = _coerce_float(value)
    if float_value is None:
        return None
    return int(float_value)


# Range extraction scans sentence-by-sentence so the first relevant term wins
# instead of pulling unrelated numbers from the same page.
def _extract_number_range_from_text(text: str, *, terms: Sequence[str]) -> Tuple[Optional[float], Optional[float]]:
    patterns = [
        re.compile(r"(\d+(?:\.\d+)?)\s*(?:to|-|and)\s*(\d+(?:\.\d+)?)", re.I),
        re.compile(r"(?:minimum of|min\.?|at least|not less than)\s*(\d+(?:\.\d+)?)", re.I),
        re.compile(r"(?:up to|maximum of|max\.?|no more than)\s*(\d+(?:\.\d+)?)", re.I),
    ]
    for sentence in sentence_chunks(text):
        lowered = sentence.lower()
        if not any(term in lowered for term in terms):
            continue
        for pattern in patterns:
            match = pattern.search(sentence)
            if not match:
                continue
            if len(match.groups()) == 2 and match.group(2):
                first = _coerce_float(match.group(1))
                second = _coerce_float(match.group(2))
                if first is not None or second is not None:
                    return first, second
            if len(match.groups()) == 1:
                value = _coerce_float(match.group(1))
                if value is not None:
                    if "minimum" in match.group(0).lower() or "at least" in match.group(0).lower():
                        return value, None
                    return None, value
    return None, None


# Eligibility stage labels are derived from keyword clusters rather than asking
# the model to infer the business maturity bucket.
def _extract_stage_labels(text: str) -> List[str]:
    lowered = (text or "").lower()
    labels: List[str] = []
    for label, terms in ELIGIBILITY_STAGE_PATTERNS.items():
        if any(term in lowered for term in terms):
            labels.append(label)
    return unique_preserve_order(labels)


# Enum coercion maps loose human language onto the strict schema values used by
# the records that leave this module.
def _coerce_enum(enum_cls, value: Any):
    text = _coerce_text(value).casefold()
    if not text:
        return None
    aliases = {
        FundingType: {
            "grant": FundingType.GRANT,
            "loan": FundingType.LOAN,
            "equity": FundingType.EQUITY,
            "guarantee": FundingType.GUARANTEE,
            "hybrid": FundingType.HYBRID,
            "other": FundingType.OTHER,
            "unknown": FundingType.UNKNOWN,
        },
        DeadlineType: {
            "fixeddate": DeadlineType.FIXED_DATE,
            "fixed date": DeadlineType.FIXED_DATE,
            "rolling": DeadlineType.ROLLING,
            "open": DeadlineType.OPEN,
            "unknown": DeadlineType.UNKNOWN,
        },
        GeographyScope: {
            "national": GeographyScope.NATIONAL,
            "province": GeographyScope.PROVINCE,
            "municipality": GeographyScope.MUNICIPALITY,
            "local": GeographyScope.LOCAL,
            "international": GeographyScope.INTERNATIONAL,
            "unknown": GeographyScope.UNKNOWN,
        },
        TriState: {
            "yes": TriState.YES,
            "no": TriState.NO,
            "maybe": TriState.MAYBE,
            "unknown": TriState.UNKNOWN,
        },
        InterestType: {
            "fixed": InterestType.FIXED,
            "prime-linked": InterestType.PRIME_LINKED,
            "primelinked": InterestType.PRIME_LINKED,
            "factor-rate": InterestType.FACTOR_RATE,
            "factorrate": InterestType.FACTOR_RATE,
            "unknown": InterestType.UNKNOWN,
        },
        RepaymentFrequency: {
            "weekly": RepaymentFrequency.WEEKLY,
            "monthly": RepaymentFrequency.MONTHLY,
            "quarterly": RepaymentFrequency.QUARTERLY,
            "annually": RepaymentFrequency.ANNUALLY,
            "annual": RepaymentFrequency.ANNUALLY,
            "once-off": RepaymentFrequency.ONCE_OFF,
            "once off": RepaymentFrequency.ONCE_OFF,
            "onceoff": RepaymentFrequency.ONCE_OFF,
            "flexible": RepaymentFrequency.FLEXIBLE,
            "variable": RepaymentFrequency.VARIABLE,
            "unknown": RepaymentFrequency.UNKNOWN,
        },
        ApplicationChannel: {
            "online form": ApplicationChannel.ONLINE_FORM,
            "email": ApplicationChannel.EMAIL,
            "branch": ApplicationChannel.BRANCH,
            "partner referral": ApplicationChannel.PARTNER_REFERRAL,
            "manual / contact first": ApplicationChannel.MANUAL_CONTACT_FIRST,
            "manual/contact first": ApplicationChannel.MANUAL_CONTACT_FIRST,
            "unknown": ApplicationChannel.UNKNOWN,
        },
    }
    enum_map = aliases.get(enum_cls, {})
    if text in enum_map:
        return enum_map[text]
    for member in enum_cls:
        if text == clean_text(member.value).casefold():
            return member
    return None


# Line trimming keeps the prompt compact while preserving the order of distinct
# lines that matter.
def _trim_lines(text: str, max_lines: int = 120) -> str:
    lines = [clean_text(line) for line in (text or "").splitlines()]
    deduped = unique_preserve_order([line for line in lines if line])
    return "\n".join(deduped[:max_lines])


# Only sections with funding-related signals are kept for the prompt; the
# fallback uses a small trimmed sample when no obvious signal is found.
def _keyword_section_filter(sections: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
    selected: List[Dict[str, str]] = []
    for section in sections:
        heading = clean_text(section.get("heading", ""))
        content = clean_text(section.get("content", ""))
        haystack = f"{heading} {content}".lower()
        if not haystack:
            continue
        if any(keyword in haystack for keyword in PROMPT_KEYWORDS):
            selected.append({"heading": heading, "content": content[:MAX_SECTION_CHARS]})
    if selected:
        return selected
    trimmed = []
    for section in list(sections)[:6]:
        heading = clean_text(section.get("heading", ""))
        content = clean_text(section.get("content", ""))
        if heading or content:
            trimmed.append({"heading": heading, "content": content[:MAX_SECTION_CHARS]})
    return trimmed


# Prompt content is built from the page metadata, selected sections, and a
# coarse decision hint so the model sees the page in a compact shape.
def _build_prompt_content(document: PageContentDocument) -> Dict[str, Any]:
    sections = [
        {"heading": section.heading, "content": section.content}
        for section in document.structured_sections
    ]
    selected_sections = _keyword_section_filter(sections)
    content_items = _build_content_items_from_document(document)
    field_bundle = _build_field_evidence_map(content_items)
    full_body_text = _trim_lines(document.full_body_text, max_lines=160)
    body_excerpt = full_body_text[:MAX_BODY_CHARS]
    if len(body_excerpt) < 150 and selected_sections:
        body_excerpt = "\n\n".join(
            f"{section['heading']}\n{section['content']}" for section in selected_sections
        )[:MAX_BODY_CHARS]
    page_decision, decision_reasons = _page_decision_hint(document)
    prompt_payload = {
        "page_url": document.page_url,
        "title": document.title,
        "source_content_type": document.source_content_type,
        "headings": document.headings,
        "structured_sections": selected_sections,
        "interactive_sections": [
            {"type": section.type, "label": section.label, "content": section.content}
            for section in document.interactive_sections
        ],
        "content_items": [
            {
                "item_type": item.item_type,
                "label": item.label,
                "content": compact_document_text(item.content, max_chars=900),
                "source_scope": item.source_scope,
                "source_section": item.source_section,
                "confidence_hint": item.confidence_hint,
            }
            for item in content_items[:12]
        ],
        "field_evidence_map": {
            field_name: snippets[:2]
            for field_name, snippets in field_bundle.evidence_by_field.items()
            if field_name in FIELD_EVIDENCE_CORE_FIELDS or field_name in {"raw_eligibility_data", "raw_funding_offer_data", "raw_terms_data", "raw_documents_data", "raw_application_data"}
        },
        "full_body_text": body_excerpt,
        "source_domain": document.source_domain,
        "main_content_hint": document.main_content_hint,
        "classification_hint": {
            "page_decision": page_decision,
            "reasons": decision_reasons,
        },
    }
    return {key: value for key, value in prompt_payload.items() if value not in (None, "", [], {})}


# Fields in an existing record that should never be sent back into the prompt
# are technical bookkeeping rather than business facts.
PROMPT_RECORD_FIELD_EXCLUSIONS = {
    "id",
    "program_id",
    "program_slug",
    "funder_slug",
    "created_at",
    "updated_at",
    "last_scraped_at",
    "last_verified_at",
    "parser_version",
    "deleted_at",
    "field_evidence",
    "evidence_by_field",
    "extraction_confidence_by_field",
}


# Prompt values are recursively compacted so nested empties do not bloat the
# JSON handed to the model.
def _compact_prompt_value(value: Any) -> Any:
    if value is None or value == "" or value == [] or value == {}:
        return None
    if isinstance(value, dict):
        compacted = {
            str(key): compacted_value
            for key, compacted_value in ((key, _compact_prompt_value(item)) for key, item in value.items())
            if compacted_value not in (None, "", [], {})
        }
        return compacted or None
    if isinstance(value, (list, tuple, set)):
        compacted_items = [_compact_prompt_value(item) for item in value]
        compacted = [item for item in compacted_items if item not in (None, "", [], {})]
        return compacted or None
    return value


# Existing record data is filtered through the exclusion list before it is fed
# back into the prompt as current state.
def _compact_record_prompt_data(record_data: Dict[str, Any]) -> Dict[str, Any]:
    prompt_data: Dict[str, Any] = {}
    for key, value in record_data.items():
        if key in PROMPT_RECORD_FIELD_EXCLUSIONS:
            continue
        compacted = _compact_prompt_value(value)
        if compacted not in (None, "", [], {}):
            prompt_data[key] = compacted
    return prompt_data


# Current record state is summarized into a small term list that the block
# scorer can use to pick the most relevant evidence block.
def _record_prompt_terms(record_data: Dict[str, Any]) -> List[str]:
    terms: List[str] = []
    for field_name in (
        "program_name",
        "funder_name",
        "parent_programme_name",
        "source_page_title",
        "application_channel",
        "geography_scope",
        "raw_eligibility_criteria",
        "payback_raw_text",
        "payback_structure",
        "repayment_frequency",
    ):
        value = record_data.get(field_name)
        if isinstance(value, str) and value.strip():
            terms.append(value.strip())
    for field_name in ("raw_eligibility_data", "raw_funding_offer_data", "raw_terms_data", "raw_documents_data", "raw_application_data"):
        value = record_data.get(field_name)
        if isinstance(value, list):
            terms.extend(item for item in value if isinstance(item, str) and item.strip())
        elif isinstance(value, str) and value.strip():
            terms.append(value.strip())
    return unique_preserve_order([clean_text(term) for term in terms if clean_text(term)])


# Candidate blocks are scored against the record terms so the most relevant
# section is surfaced to the model.
def _score_candidate_block(block: CandidateBlockSnapshot, prompt_terms: Sequence[str]) -> int:
    haystack = " ".join(
        [
            clean_text(block.heading),
            clean_text(block.text),
            clean_text(block.source_url),
            " ".join(clean_text(item) for item in block.detail_links),
            " ".join(clean_text(item) for item in block.application_links),
            " ".join(clean_text(item) for item in block.document_links),
        ]
    ).casefold()
    score = 0
    for term in prompt_terms:
        lowered = term.casefold()
        if not lowered:
            continue
        if lowered in haystack:
            score += 4
            continue
        term_parts = [part for part in lowered.split() if len(part) >= 4]
        score += sum(1 for part in term_parts if part in haystack)
    return score


# The highest-scoring candidate block is selected and compacted into a small
# prompt-friendly payload.
def _select_candidate_block(blocks: Sequence[CandidateBlockSnapshot], record_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not blocks:
        return None
    prompt_terms = _record_prompt_terms(record_data)
    ranked = sorted(
        ((block, _score_candidate_block(block, prompt_terms)) for block in blocks),
        key=lambda item: (item[1], len(item[0].text or ""), len(item[0].heading or "")),
        reverse=True,
    )
    selected_block, selected_score = ranked[0]
    if selected_score <= 0:
        selected_block = blocks[0]
    compact_block = {
        "heading": clean_text(selected_block.heading) or None,
        "text": clean_text(selected_block.text)[:MAX_BODY_CHARS] if selected_block.text else None,
        "source_url": clean_text(selected_block.source_url) or None,
        "detail_links": unique_preserve_order([clean_text(item) for item in selected_block.detail_links if clean_text(item)]),
        "application_links": unique_preserve_order([clean_text(item) for item in selected_block.application_links if clean_text(item)]),
        "document_links": unique_preserve_order([clean_text(item) for item in selected_block.document_links if clean_text(item)]),
    }
    return {key: value for key, value in compact_block.items() if value not in (None, "", [], {})}


# Record snapshots are converted into a prompt payload that keeps the current
# field values plus the best matching evidence block.
def _build_record_context_prompt(snapshot: PageAIRecordSnapshot | Dict[str, Any] | Any, blocks: Sequence[CandidateBlockSnapshot]) -> Dict[str, Any]:
    if isinstance(snapshot, PageAIRecordSnapshot):
        record_index = snapshot.record_index
        record_data = dict(snapshot.normalized_record or {})
    elif isinstance(snapshot, dict):
        record_index = int(snapshot.get("record_index", 0) or 0)
        record_data = dict(snapshot.get("normalized_record") or snapshot)
    else:
        record_index = int(getattr(snapshot, "record_index", 0) or 0)
        record_data = dict(getattr(snapshot, "normalized_record", {}) or {})
    compact_record = _compact_record_prompt_data(record_data)
    prompt_record = {
        "record_index": record_index,
        "filled_fields": list(compact_record.keys()),
        "current_record": compact_record,
        "selected_candidate_block": _select_candidate_block(blocks, record_data),
    }
    return {key: value for key, value in prompt_record.items() if value not in (None, "", [], {})}


# The full prompt payload combines the page content, current records, and any
# linked document evidence into the JSON body sent to the model.
def _build_context_prompt_payload(
    document: PageContentDocument,
    *,
    record_snapshots: Optional[Sequence[PageAIRecordSnapshot | Dict[str, Any] | Any]] = None,
) -> Dict[str, Any]:
    payload = _build_prompt_content(document)
    context = document.page_ai_context
    snapshots = list(record_snapshots or context.current_records)
    payload["current_records"] = [
        record_prompt
        for record_prompt in (
            _build_record_context_prompt(snapshot, context.candidate_blocks) for snapshot in snapshots
        )
        if record_prompt
    ]
    if document.document_evidence:
        payload["document_evidence"] = [
            {
                "document_url": item.document_url,
                "document_kind": item.document_kind,
                "content_type": item.content_type,
                "source_method": item.source_method,
                "summary": compact_document_text(item.summary or "", max_chars=600) or None,
                "key_points": item.key_points[:6],
                "extracted_text": compact_document_text(item.extracted_text or "", max_chars=1200) or None,
                "notes": item.notes,
            }
            for item in document.document_evidence
        ]
        payload["document_evidence_text"] = _document_evidence_text(document)
    return {key: value for key, value in payload.items() if value not in (None, "", [], {})}


def _document_evidence_text(document: PageContentDocument) -> str:
    return _document_evidence_context(document)["combined_text"]


def _interactive_sections_text(document: PageContentDocument) -> str:
    return " ".join(
        unique_preserve_order(
            [
                clean_text(part)
                for section in document.interactive_sections
                for part in (section.label, section.content)
                if clean_text(part)
            ]
        )
    )


def _content_item_signature(item: ContentItem) -> tuple[str, str, str]:
    return (
        clean_text(item.item_type).casefold(),
        clean_text(item.label).casefold(),
        compact_document_text(item.content or "", max_chars=240).casefold(),
    )


def _build_content_items_from_document(document: PageContentDocument) -> List[ContentItem]:
    """Flatten the scraped page into the text blocks the AI layer can route."""
    items: List[ContentItem] = []
    seen: set[tuple[str, str, str]] = set()

    def add_item(
        item_type: str,
        label: str,
        content: str,
        *,
        source_scope: Optional[str],
        source_section: Optional[str] = None,
        confidence_hint: float = 0.0,
    ) -> None:
        cleaned_label = clean_text(label)
        cleaned_content = clean_text(content)
        if not cleaned_label and not cleaned_content:
            return
        candidate = ContentItem(
            item_type=clean_text(item_type) or "content",
            label=cleaned_label,
            content=cleaned_content,
            source_url=document.page_url,
            source_section=cleaned_label if source_section is None else clean_text(source_section),
            source_scope=clean_text(source_scope or "") or None,
            confidence_hint=max(0.0, min(float(confidence_hint), 1.0)),
            order=len(items),
        )
        signature = _content_item_signature(candidate)
        if signature in seen:
            return
        seen.add(signature)
        items.append(candidate)

    if document.title:
        add_item("title", "title", document.title, source_scope="metadata", confidence_hint=0.95)
    if document.page_title and document.page_title != document.title:
        add_item("page_title", "page_title", document.page_title, source_scope="metadata", confidence_hint=0.92)
    for index, heading in enumerate(document.headings[:8]):
        add_item("heading", f"heading_{index + 1}", heading, source_scope="headings", confidence_hint=0.85)
    for section in document.structured_sections:
        add_item(
            "structured_section",
            section.heading,
            section.content,
            source_scope="structured_sections",
            source_section=section.heading,
            confidence_hint=0.88,
        )
    for section in document.interactive_sections:
        add_item(
            section.type or "interactive",
            section.label or section.type,
            section.content,
            source_scope="interactive_sections",
            source_section=section.label or section.type,
            confidence_hint=0.86,
        )
    for evidence in document.document_evidence:
        evidence_text = " ".join(
            unique_preserve_order(
                [
                    compact_document_text(evidence.summary or "", max_chars=600),
                    *[compact_document_text(point, max_chars=300) for point in evidence.key_points],
                    compact_document_text(evidence.extracted_text or "", max_chars=900),
                ]
            )
        )
        add_item(
            "document_evidence",
            evidence.document_kind or evidence.document_url,
            evidence_text or evidence.document_url,
            source_scope="document_evidence",
            source_section=evidence.document_kind,
            confidence_hint=0.76,
        )
    if document.full_body_text:
        add_item(
            "body",
            document.title or document.page_title or "full_body_text",
            compact_document_text(document.full_body_text, max_chars=MAX_BODY_CHARS),
            source_scope="full_body_text",
            confidence_hint=0.6,
        )
    return items


FALLBACK_CANDIDATE_SIGNAL_TERMS = (
    "fund",
    "funding",
    "grant",
    "loan",
    "finance",
    "financial",
    "equity",
    "investment",
    "facility",
    "incentive",
    "voucher",
    "working capital",
    "seed capital",
    "repayment",
    "interest",
    "eligibility",
    "qualifying",
    "apply",
    "application",
    "amount",
    "ticket",
)
FALLBACK_DIRECT_FUNDING_TERMS = (
    "fund",
    "funding",
    "grant",
    "loan",
    "finance",
    "equity",
    "investment",
    "facility",
    "incentive",
    "voucher",
    "capital",
)
FALLBACK_BLOCK_EXCLUDE_TERMS = (
    "career",
    "careers",
    "vacancy",
    "vacancies",
    "graduate",
    "internship",
    "internships",
    "bursary",
    "bursaries",
    "procurement",
    "tender",
    "rfp",
    "rfq",
    "news",
    "media",
    "press release",
    "privacy",
    "contact us",
)
FALLBACK_GENERIC_CANDIDATE_LABELS = INVALID_PROGRAMME_NAME_TERMS | {
    "applications",
    "application process",
    "criteria",
    "documents",
    "eligibility",
    "funding offer",
    "funding products",
    "funding solutions",
    "funding terms",
    "how to apply",
    "important information",
    "paperwork needed",
    "required documents",
    "repayment",
    "terms",
    "terms and conditions",
}


def _candidate_label_from_block(label: str, content: str) -> Optional[str]:
    cleaned = strip_leading_numbered_prefix(clean_text(label or ""))
    cleaned = re.sub(r"\s+(?:learn more|view facility|apply now|read more)\b.*$", "", cleaned, flags=re.I)
    cleaned = clean_text(cleaned)
    if not cleaned:
        return None
    lowered = cleaned.casefold()
    if lowered in FALLBACK_GENERIC_CANDIDATE_LABELS:
        return None
    if looks_like_support_title(cleaned):
        return None
    if len(cleaned) < 4 or len(cleaned) > 110:
        return None
    if len(cleaned.split()) > 12:
        return None
    return cleaned


def _fallback_candidate_has_fundable_signal(label: str, content: str) -> bool:
    haystack = clean_text(" ".join([label, content])).casefold()
    return any(term in haystack for term in FALLBACK_CANDIDATE_SIGNAL_TERMS)


def _fallback_candidate_is_excluded(label: str, content: str) -> bool:
    haystack = clean_text(" ".join([label, content])).casefold()
    if not any(term in haystack for term in FALLBACK_BLOCK_EXCLUDE_TERMS):
        return False
    return not any(term in haystack for term in FALLBACK_DIRECT_FUNDING_TERMS)


def _fallback_link_matches_label(link: str, label: str) -> bool:
    lowered_link = clean_text(link).casefold()
    tokens = [
        token
        for token in re.split(r"[^a-z0-9]+", clean_text(label).casefold())
        if len(token) >= 4 and token not in {"fund", "loan", "grant", "finance", "facility", "programme", "program"}
    ]
    if not tokens:
        return False
    return any(token in lowered_link for token in tokens)


def _document_for_fallback_candidate(document: PageContentDocument, candidate: FallbackProgrammeCandidate) -> PageContentDocument:
    related_links = unique_preserve_order(
        [
            link
            for link in [*document.discovered_links, *document.internal_links, *document.document_links]
            if _fallback_link_matches_label(link, candidate.label)
        ]
    )
    application_links = unique_preserve_order(
        [
            link
            for link in document.application_links
            if _fallback_link_matches_label(link, candidate.label)
        ]
    )
    original_title = document.title or document.page_title or ""
    title_suffix = ""
    if " - " in original_title:
        title_suffix = original_title.split(" - ", 1)[1].strip()
    elif " | " in original_title:
        title_suffix = original_title.split(" | ", 1)[1].strip()
    candidate_title = f"{candidate.label} - {title_suffix}" if title_suffix else candidate.label
    return PageContentDocument(
        page_url=document.page_url,
        title=candidate_title,
        page_title=candidate_title,
        source_content_type=document.source_content_type,
        headings=[candidate.label],
        full_body_text=candidate.content,
        structured_sections=[
            PageContentSection(
                heading=candidate.label,
                content=candidate.content,
            )
        ],
        interactive_sections=[],
        discovered_links=related_links,
        internal_links=related_links,
        application_links=application_links,
        document_links=[link for link in document.document_links if _fallback_link_matches_label(link, candidate.label)],
        document_evidence=document.document_evidence,
        main_content_hint=document.main_content_hint,
        source_domain=document.source_domain,
    )


def _collect_fallback_programme_candidates(document: PageContentDocument) -> List[FallbackProgrammeCandidate]:
    candidates: List[FallbackProgrammeCandidate] = []
    seen: set[tuple[str, str]] = set()

    def add(label: str, content: str, source_scope: str, source_section: Optional[str] = None) -> None:
        cleaned_content = clean_text(content)
        candidate_label = _candidate_label_from_block(label, cleaned_content)
        if not candidate_label or not cleaned_content:
            return
        if not _fallback_candidate_has_fundable_signal(candidate_label, cleaned_content):
            return
        if _fallback_candidate_is_excluded(candidate_label, cleaned_content):
            return
        signature = (candidate_label.casefold(), compact_document_text(cleaned_content, max_chars=280).casefold())
        if signature in seen:
            return
        seen.add(signature)
        candidates.append(
            FallbackProgrammeCandidate(
                label=candidate_label,
                content=cleaned_content,
                source_scope=source_scope,
                source_section=source_section or candidate_label,
            )
        )

    for section in document.structured_sections:
        add(section.heading, section.content, "structured_sections", section.heading)
    for section in document.interactive_sections:
        add(section.label, section.content, section.type or "interactive_sections", section.label)

    return candidates


def _normalized_candidate_name(value: Optional[str]) -> str:
    return strip_leading_numbered_prefix(clean_text(value or "")).casefold()


def _programme_name_matches_candidate(program_name: Optional[str], candidate_label: str) -> bool:
    program = _normalized_candidate_name(program_name)
    candidate = _normalized_candidate_name(candidate_label)
    if not program or not candidate:
        return False
    if program == candidate:
        return True
    generic_tokens = {"fund", "funding", "programme", "program", "facility", "finance", "investment"}
    program_tokens = {token for token in re.split(r"[^a-z0-9]+", program) if len(token) >= 4 and token not in generic_tokens}
    candidate_tokens = {token for token in re.split(r"[^a-z0-9]+", candidate) if len(token) >= 4 and token not in generic_tokens}
    if not program_tokens or not candidate_tokens:
        return False
    overlap = program_tokens & candidate_tokens
    return len(overlap) >= min(len(program_tokens), len(candidate_tokens))


def _is_listing_aggregate_record(record: FundingProgrammeRecord, document: PageContentDocument, candidates: Sequence[FallbackProgrammeCandidate]) -> bool:
    program_name = _normalized_candidate_name(record.program_name)
    if not program_name:
        return False
    if any(_programme_name_matches_candidate(record.program_name, candidate.label) for candidate in candidates):
        return False
    title = _normalized_candidate_name(document.title or document.page_title)
    listing_terms = {"funding", "funding opportunities", "programmes", "programs", "products", "isibaya"}
    if normalize_page_type(record.page_type) == PAGE_TYPE_FUNDING_LISTING:
        return True
    if title and (program_name == title or program_name in title or title in program_name):
        return True
    return program_name in listing_terms or any(term in program_name for term in ("listing", "funding products", "funding opportunities"))


def _is_domain_navigation_homepage(document: PageContentDocument) -> bool:
    path = urlparse(document.page_url).path.rstrip("/")
    if path not in {"", "/"}:
        return False
    domain = (document.source_domain or extract_domain(document.page_url) or "").lower().removeprefix("www.")
    return domain in {"pic.gov.za"}


def _merge_snippet_map(target: Dict[str, List[str]], source: Dict[str, List[str]]) -> Dict[str, List[str]]:
    merged = {key: list(value) for key, value in target.items()}
    for key, snippets in source.items():
        if not snippets:
            continue
        bucket = merged.setdefault(key, [])
        bucket.extend(snippets)
        merged[key] = unique_preserve_order([clean_text(item) for item in bucket if clean_text(item)])
    return merged


def _is_unknown_placeholder(value: Any) -> bool:
    if value in (None, "", [], {}):
        return True
    text = _coerce_text(getattr(value, "value", value)).casefold()
    return text in {"unknown", "unknowns", "none", "null"}


def _merge_scalar_value(existing: Any, candidate: Any) -> Any:
    if _is_unknown_placeholder(candidate):
        return existing
    if _is_unknown_placeholder(existing):
        return candidate
    if isinstance(existing, list) and isinstance(candidate, list):
        return unique_preserve_order([*existing, *candidate])
    return existing


def _append_bundle_value(bundle: FieldEvidenceBundle, field_name: str, value: Any) -> None:
    if value in (None, "", [], {}):
        return
    current = bundle.field_values.get(field_name)
    bundle.field_values[field_name] = _merge_scalar_value(current, value)


def _add_bundle_snippet(bundle: FieldEvidenceBundle, bucket: str, snippet: str) -> None:
    cleaned = clean_text(snippet)
    if not cleaned:
        return
    bundle.raw_text_snippets.setdefault(bucket, []).append(cleaned)


def _add_bundle_evidence(bundle: FieldEvidenceBundle, field_name: str, snippet: str, confidence: float) -> None:
    cleaned = clean_text(snippet)
    if not cleaned:
        return
    bundle.evidence_by_field.setdefault(field_name, []).append(cleaned)
    bundle.field_confidence[field_name] = max(bundle.field_confidence.get(field_name, 0.0), max(0.0, min(float(confidence), 1.0)))


def _route_content_item_to_fields(item: ContentItem) -> FieldEvidenceBundle:
    """Map one content item to the schema fields it most likely supports."""
    bundle = FieldEvidenceBundle()
    text = clean_text(" ".join([item.label, item.content]))
    lowered = text.lower()
    if not text:
        return bundle

    snippet = compact_document_text(text, max_chars=900) or text
    label_lower = clean_text(item.label).lower()
    content_lower = clean_text(item.content).lower()
    route_hits = [
        bucket
        for bucket, terms in CONTENT_BUCKET_TERMS.items()
        if any(term in lowered or term in label_lower or term in content_lower for term in terms)
    ]
    if not route_hits:
        if item.item_type in {"title", "page_title"}:
            route_hits = ["program"]
        elif item.item_type in {"heading", "structured_section", "tab", "accordion", "card", "table", "list", "document_evidence"}:
            route_hits = ["program"]
        else:
            route_hits = ["supporting"]

    source_confidence = max(0.0, min(item.confidence_hint, 1.0))
    if item.item_type in {"title", "page_title"}:
        program_name = strip_leading_numbered_prefix(text.split(" - ")[0].split(" | ")[0].strip() or text)
        if program_name:
            _append_bundle_value(bundle, "program_name", program_name)
            _add_bundle_evidence(bundle, "program_name", program_name, max(source_confidence, 0.95))
        funder_name = _extract_funder_name_from_title(text)
        if funder_name:
            _append_bundle_value(bundle, "funder_name", funder_name)
            _add_bundle_evidence(bundle, "funder_name", funder_name, max(source_confidence, 0.9))
        _add_bundle_snippet(bundle, "program_title", snippet)
        _add_bundle_evidence(bundle, "source_page_title", snippet, max(source_confidence, 0.9))
        _append_bundle_value(bundle, "source_page_title", text)

    for route_hit in route_hits:
        bundle.notes.append(f"Routed {item.item_type} into {route_hit}")
        _add_bundle_snippet(bundle, route_hit, snippet)

    if "eligibility" in route_hits:
        _add_bundle_evidence(bundle, "raw_eligibility_data", snippet, max(source_confidence, 0.84))
        extracted = extract_eligibility_criteria(text)
        if extracted:
            _append_bundle_value(bundle, "raw_eligibility_criteria", extracted)
        else:
            _append_bundle_value(bundle, "raw_eligibility_criteria", [snippet])
    if "funding" in route_hits:
        _add_bundle_evidence(bundle, "raw_funding_offer_data", snippet, max(source_confidence, 0.82))
        _append_bundle_value(bundle, "funding_lines", [snippet])
        money_min, money_max, currency, _money_snippet, money_confidence = extract_money_range(text, default_currency=None)
        if money_min is not None:
            _append_bundle_value(bundle, "ticket_min", money_min)
            bundle.field_confidence["ticket_min"] = max(bundle.field_confidence.get("ticket_min", 0.0), max(source_confidence, money_confidence))
        if money_max is not None:
            _append_bundle_value(bundle, "ticket_max", money_max)
            bundle.field_confidence["ticket_max"] = max(bundle.field_confidence.get("ticket_max", 0.0), max(source_confidence, money_confidence))
        if money_min is not None or money_max is not None:
            _append_bundle_value(bundle, "program_budget_total", money_max or money_min)
            bundle.field_confidence["program_budget_total"] = max(bundle.field_confidence.get("program_budget_total", 0.0), max(source_confidence, money_confidence))
        if currency:
            _append_bundle_value(bundle, "currency", currency)
            bundle.field_confidence["currency"] = max(bundle.field_confidence.get("currency", 0.0), max(source_confidence, money_confidence))
    if "terms" in route_hits:
        _add_bundle_evidence(bundle, "raw_terms_data", snippet, max(source_confidence, 0.82))
        payback = extract_payback_details(text)
        if payback.raw_text:
            _append_bundle_value(bundle, "payback_raw_text", payback.raw_text)
            bundle.field_confidence["payback_raw_text"] = max(bundle.field_confidence.get("payback_raw_text", 0.0), max(source_confidence, payback.confidence))
        if payback.structure:
            _append_bundle_value(bundle, "payback_structure", payback.structure)
            bundle.field_confidence["payback_structure"] = max(bundle.field_confidence.get("payback_structure", 0.0), max(source_confidence, payback.confidence))
        if payback.term_min_months is not None:
            _append_bundle_value(bundle, "payback_term_min_months", payback.term_min_months)
            bundle.field_confidence["payback_term_min_months"] = max(bundle.field_confidence.get("payback_term_min_months", 0.0), max(source_confidence, payback.confidence))
        if payback.term_max_months is not None:
            _append_bundle_value(bundle, "payback_term_max_months", payback.term_max_months)
            bundle.field_confidence["payback_term_max_months"] = max(bundle.field_confidence.get("payback_term_max_months", 0.0), max(source_confidence, payback.confidence))
        if payback.grace_period_months is not None:
            _append_bundle_value(bundle, "grace_period_months", payback.grace_period_months)
            bundle.field_confidence["grace_period_months"] = max(bundle.field_confidence.get("grace_period_months", 0.0), max(source_confidence, payback.confidence))
        interest_type = getattr(payback, "interest_type", None)
        if interest_type:
            _append_bundle_value(bundle, "interest_type", interest_type)
            bundle.field_confidence["interest_type"] = max(bundle.field_confidence.get("interest_type", 0.0), max(source_confidence, payback.confidence))
        if payback.repayment_frequency:
            _append_bundle_value(bundle, "repayment_frequency", payback.repayment_frequency)
            bundle.field_confidence["repayment_frequency"] = max(bundle.field_confidence.get("repayment_frequency", 0.0), max(source_confidence, payback.confidence))
        security_required = getattr(payback, "security_required", None)
        if security_required:
            _append_bundle_value(bundle, "security_required", security_required)
            bundle.field_confidence["security_required"] = max(bundle.field_confidence.get("security_required", 0.0), max(source_confidence, payback.confidence))
        equity_required = getattr(payback, "equity_required", None)
        if equity_required:
            _append_bundle_value(bundle, "equity_required", equity_required)
            bundle.field_confidence["equity_required"] = max(bundle.field_confidence.get("equity_required", 0.0), max(source_confidence, payback.confidence))
    if "documents" in route_hits:
        _add_bundle_evidence(bundle, "raw_documents_data", snippet, max(source_confidence, 0.8))
        document_terms = []
        document_source_text = item.content or text
        for sentence in sentence_chunks(document_source_text):
            lowered_sentence = sentence.lower()
            if any(term in lowered_sentence for term in ("document", "documents", "checklist", "certificate", "proof", "registration", "download")):
                document_terms.append(sentence)
        if document_terms:
            _append_bundle_value(bundle, "required_documents", document_terms)
            bundle.field_confidence["required_documents"] = max(bundle.field_confidence.get("required_documents", 0.0), max(source_confidence, 0.8))
    if "application" in route_hits:
        _add_bundle_evidence(bundle, "raw_application_data", snippet, max(source_confidence, 0.82))
        urls = [url for url in extract_urls(text) if any(term in url.lower() for term in ("apply", "application", "portal", "register", "submit"))]
        if urls:
            _append_bundle_value(bundle, "application_url", urls[0])
            bundle.field_confidence["application_url"] = max(bundle.field_confidence.get("application_url", 0.0), max(source_confidence, 0.86))
            _append_bundle_value(bundle, "application_channel", ApplicationChannel.ONLINE_FORM)
            bundle.field_confidence["application_channel"] = max(bundle.field_confidence.get("application_channel", 0.0), max(source_confidence, 0.82))
        emails = extract_emails(text)
        phones = extract_phone_numbers(text)
        if emails:
            _append_bundle_value(bundle, "contact_email", emails[0])
            bundle.field_confidence["contact_email"] = max(bundle.field_confidence.get("contact_email", 0.0), max(source_confidence, 0.84))
        if phones:
            _append_bundle_value(bundle, "contact_phone", phones[0])
            bundle.field_confidence["contact_phone"] = max(bundle.field_confidence.get("contact_phone", 0.0), max(source_confidence, 0.84))
        if not urls and not emails and not phones:
            _append_bundle_value(bundle, "application_channel", ApplicationChannel.MANUAL_CONTACT_FIRST)
            bundle.field_confidence["application_channel"] = max(bundle.field_confidence.get("application_channel", 0.0), max(source_confidence, 0.7))
    if "deadline" in route_hits:
        _add_bundle_evidence(bundle, "raw_terms_data", snippet, max(source_confidence, 0.8))
        deadline_info = parse_deadline_info(text)
        if deadline_info.get("deadline_date"):
            _append_bundle_value(bundle, "deadline_date", deadline_info["deadline_date"])
            bundle.field_confidence["deadline_date"] = max(bundle.field_confidence.get("deadline_date", 0.0), max(source_confidence, 0.88))
        if deadline_info.get("deadline_type"):
            _append_bundle_value(bundle, "deadline_type", _coerce_enum(DeadlineType, deadline_info.get("deadline_type")) or deadline_info.get("deadline_type"))
            bundle.field_confidence["deadline_type"] = max(bundle.field_confidence.get("deadline_type", 0.0), max(source_confidence, 0.8))
    if "contact" in route_hits:
        emails = extract_emails(text)
        phones = extract_phone_numbers(text)
        if emails:
            _append_bundle_value(bundle, "contact_email", emails[0])
            bundle.field_confidence["contact_email"] = max(bundle.field_confidence.get("contact_email", 0.0), max(source_confidence, 0.9))
        if phones:
            _append_bundle_value(bundle, "contact_phone", phones[0])
            bundle.field_confidence["contact_phone"] = max(bundle.field_confidence.get("contact_phone", 0.0), max(source_confidence, 0.9))
        _add_bundle_evidence(bundle, "raw_application_data", snippet, max(source_confidence, 0.75))
    if "geography" in route_hits:
        if any(term in lowered for term in ("national", "countrywide", "south africa")):
            _append_bundle_value(bundle, "geography_scope", GeographyScope.NATIONAL)
        elif any(term in lowered for term in ("province", "provincial")):
            _append_bundle_value(bundle, "geography_scope", GeographyScope.PROVINCE)
        elif any(term in lowered for term in ("municipality", "municipal")):
            _append_bundle_value(bundle, "geography_scope", GeographyScope.MUNICIPALITY)
        elif any(term in lowered for term in ("local", "regional")):
            _append_bundle_value(bundle, "geography_scope", GeographyScope.LOCAL)
        if bundle.field_values.get("geography_scope") is not None:
            bundle.field_confidence["geography_scope"] = max(bundle.field_confidence.get("geography_scope", 0.0), max(source_confidence, 0.72))

    if "supporting" in route_hits:
        _add_bundle_snippet(bundle, "supporting_text", snippet)
        bundle.notes.append(f"Supporting text retained from {item.item_type}")

    return bundle


def _build_field_evidence_map(content_items: Sequence[ContentItem]) -> FieldEvidenceBundle:
    """Aggregate the routed evidence from all page content items."""
    bundle = FieldEvidenceBundle()
    for item in content_items:
        routed = _route_content_item_to_fields(item)
        bundle.evidence_by_field = _merge_snippet_map(bundle.evidence_by_field, routed.evidence_by_field)
        bundle.raw_text_snippets = _merge_snippet_map(bundle.raw_text_snippets, routed.raw_text_snippets)
        for field_name, value in routed.field_values.items():
            _append_bundle_value(bundle, field_name, value)
        for field_name, confidence in routed.field_confidence.items():
            bundle.field_confidence[field_name] = max(bundle.field_confidence.get(field_name, 0.0), confidence)
        bundle.validation_errors.extend(routed.validation_errors)
        bundle.notes.extend(routed.notes)
    bundle.evidence_by_field = {
        field_name: unique_preserve_order([clean_text(item) for item in snippets if clean_text(item)])
        for field_name, snippets in bundle.evidence_by_field.items()
        if unique_preserve_order([clean_text(item) for item in snippets if clean_text(item)])
    }
    bundle.raw_text_snippets = {
        field_name: unique_preserve_order([clean_text(item) for item in snippets if clean_text(item)])
        for field_name, snippets in bundle.raw_text_snippets.items()
        if unique_preserve_order([clean_text(item) for item in snippets if clean_text(item)])
    }
    bundle.validation_errors = unique_preserve_order([clean_text(item) for item in bundle.validation_errors if clean_text(item)])
    bundle.notes = unique_preserve_order([clean_text(item) for item in bundle.notes if clean_text(item)])
    return bundle


def _document_content_annotation_bundle(document: PageContentDocument) -> FieldEvidenceBundle:
    """Convenience wrapper for the document-to-field evidence routing pass."""
    return _build_field_evidence_map(_build_content_items_from_document(document))


def _merge_content_bundle_into_payload(payload: Dict[str, Any], bundle: FieldEvidenceBundle) -> Dict[str, Any]:
    """Merge routed content evidence into a draft or record payload."""
    merged = dict(payload)

    list_fields = {
        "raw_eligibility_data",
        "raw_eligibility_criteria",
        "raw_funding_offer_data",
        "raw_terms_data",
        "raw_documents_data",
        "raw_application_data",
        "funding_lines",
        "required_documents",
        "related_documents",
        "exclusions",
        "notes",
    }
    scalar_fields = {
        "program_name",
        "funder_name",
        "source_page_title",
        "application_url",
        "contact_email",
        "contact_phone",
        "deadline_type",
        "deadline_date",
        "geography_scope",
        "ticket_min",
        "ticket_max",
        "program_budget_total",
        "payback_raw_text",
        "payback_structure",
        "payback_term_min_months",
        "payback_term_max_months",
        "grace_period_months",
        "interest_type",
        "repayment_frequency",
        "security_required",
        "equity_required",
        "application_channel",
        "currency",
    }

    for field_name, value in bundle.field_values.items():
        if field_name in list_fields:
            existing = _coerce_list(merged.get(field_name))
            candidate = _coerce_list(value)
            merged[field_name] = unique_preserve_order([*existing, *candidate])
            continue
        if field_name in scalar_fields:
            if _is_unknown_placeholder(merged.get(field_name)) or merged.get(field_name) in (None, "", [], {}):
                merged[field_name] = value
            continue
        if merged.get(field_name) in (None, "", [], {}):
            merged[field_name] = value

    merged["raw_text_snippets"] = _merge_snippet_map(
        dict(merged.get("raw_text_snippets") or {}),
        bundle.raw_text_snippets,
    )
    merged["evidence_by_field"] = _merge_snippet_map(
        dict(merged.get("evidence_by_field") or {}),
        bundle.evidence_by_field,
    )
    merged["extraction_confidence"] = {
        str(field_name): max(
            float(merged.get("extraction_confidence", {}).get(field_name, 0.0) or 0.0),
            float(bundle.field_confidence.get(field_name, 0.0) or 0.0),
        )
        for field_name in unique_preserve_order(
            [*dict(merged.get("extraction_confidence") or {}).keys(), *bundle.field_confidence.keys()]
        )
    }
    merged["field_confidence"] = {
        str(field_name): max(
            float(merged.get("field_confidence", {}).get(field_name, 0.0) or 0.0),
            float(bundle.field_confidence.get(field_name, 0.0) or 0.0),
        )
        for field_name in unique_preserve_order(
            [*dict(merged.get("field_confidence") or {}).keys(), *bundle.field_confidence.keys()]
        )
    }
    merged["validation_errors"] = unique_preserve_order(
        [*([clean_text(item) for item in merged.get("validation_errors") or [] if clean_text(item)]), *bundle.validation_errors]
    )
    merged["notes"] = unique_preserve_order(
        [*([clean_text(item) for item in merged.get("notes") or [] if clean_text(item)]), *bundle.notes]
    )
    return merged


def _validate_field_evidence(record: FundingProgrammeRecord, bundle: Optional[FieldEvidenceBundle] = None) -> FundingProgrammeRecord:
    """Ensure each populated business field has some traceable evidence."""
    payload = record.model_dump(mode="python")
    evidence_by_field = {
        field_name: list(snippets)
        for field_name, snippets in (payload.get("evidence_by_field") or {}).items()
        if snippets
    }
    raw_text_snippets = {
        field_name: list(snippets)
        for field_name, snippets in (payload.get("raw_text_snippets") or {}).items()
        if snippets
    }
    validation_errors = unique_preserve_order([clean_text(item) for item in payload.get("validation_errors") or [] if clean_text(item)])
    if bundle:
        evidence_by_field = _merge_snippet_map(evidence_by_field, bundle.evidence_by_field)
        raw_text_snippets = _merge_snippet_map(raw_text_snippets, bundle.raw_text_snippets)
        validation_errors.extend(bundle.validation_errors)
    for field_name, value in payload.items():
        if field_name in FIELD_EVIDENCE_SKIP_FIELDS:
            continue
        if value in (None, "", [], {}, False):
            continue
        snippets = evidence_by_field.get(field_name)
        if snippets:
            continue
        fallback = raw_text_snippets.get(field_name)
        if fallback:
            evidence_by_field[field_name] = unique_preserve_order(fallback)
            continue
        if isinstance(value, list):
            fallback_snippets = [clean_text(item) for item in value if clean_text(item)]
        else:
            fallback_snippets = [clean_text(str(value))] if clean_text(str(value)) else []
        if fallback_snippets:
            evidence_by_field[field_name] = unique_preserve_order(fallback_snippets)
        else:
            validation_errors.append(f"missing evidence for {field_name}")
    for field_name in IMPORTANT_EVIDENCE_FIELDS:
        value = payload.get(field_name)
        if value in (None, "", [], {}, False):
            continue
        snippets = [snippet for snippet in evidence_by_field.get(field_name, []) if clean_text(str(snippet))]
        if not snippets:
            validation_errors.append(f"missing important evidence for {field_name}")
    payload["evidence_by_field"] = evidence_by_field
    payload["raw_text_snippets"] = raw_text_snippets
    payload["validation_errors"] = unique_preserve_order(validation_errors)
    payload["needs_review"] = bool(payload.get("needs_review") or payload["validation_errors"])
    return FundingProgrammeRecord.model_validate(payload)


def _apply_field_confidence_rules(record: FundingProgrammeRecord, bundle: Optional[FieldEvidenceBundle] = None) -> FundingProgrammeRecord:
    """Promote or soften confidence values based on the routed evidence."""
    payload = record.model_dump(mode="python")
    field_confidence = {
        str(field_name): max(0.0, min(float(confidence), 1.0))
        for field_name, confidence in (payload.get("field_confidence") or {}).items()
        if confidence is not None
    }
    extraction_confidence = {
        str(field_name): max(0.0, min(float(confidence), 1.0))
        for field_name, confidence in (payload.get("extraction_confidence") or {}).items()
        if confidence is not None
    }
    if bundle:
        for field_name, confidence in bundle.field_confidence.items():
            field_confidence[field_name] = max(field_confidence.get(field_name, 0.0), confidence)
            extraction_confidence[field_name] = max(extraction_confidence.get(field_name, 0.0), confidence)
    for field_name, snippets in (payload.get("evidence_by_field") or {}).items():
        if field_name in FIELD_EVIDENCE_SKIP_FIELDS:
            continue
        snippet_count = len([snippet for snippet in snippets if clean_text(str(snippet))])
        if snippet_count:
            inferred_confidence = min(0.95, 0.45 + (snippet_count * 0.08))
            field_confidence[field_name] = max(field_confidence.get(field_name, 0.0), inferred_confidence)
            extraction_confidence[field_name] = max(extraction_confidence.get(field_name, 0.0), inferred_confidence)
    for field_name, value in payload.items():
        if field_name in FIELD_EVIDENCE_SKIP_FIELDS:
            continue
        if value in (None, "", [], {}, False):
            continue
        if field_name not in field_confidence:
            fallback_confidence = 0.72 if field_name in FIELD_EVIDENCE_CORE_FIELDS else 0.55
            field_confidence[field_name] = fallback_confidence
        if field_name not in extraction_confidence:
            extraction_confidence[field_name] = field_confidence[field_name]
    payload["field_confidence"] = field_confidence
    payload["extraction_confidence"] = extraction_confidence
    payload["extraction_confidence_by_field"] = extraction_confidence
    return FundingProgrammeRecord.model_validate(payload)

# Evidence context groups support-document content into categories that the
# prompt and fallback extractors can reuse without re-reading each file.
def _document_evidence_context(document: PageContentDocument) -> Dict[str, Any]:
    # Evidence from linked documents is flattened into one summary plus a few
    # targeted buckets so downstream steps can re-use it cheaply.
    evidence_lines: List[str] = []
    funding_lines: List[str] = []
    eligibility_lines: List[str] = []
    application_lines: List[str] = []
    required_documents: List[str] = []
    notes: List[str] = []
    for item in document.document_evidence:
        # Each evidence item is summarized once, then tagged into the buckets
        # that match the phrases it contains.
        fragments = [item.summary, *item.key_points, item.extracted_text]
        cleaned_fragments = unique_preserve_order([clean_text(fragment) for fragment in fragments if clean_text(fragment)])
        if not cleaned_fragments:
            continue
        tagged = f"{item.document_url}: {' '.join(cleaned_fragments)}"
        evidence_lines.append(tagged)
        lowered = tagged.lower()
        if any(term in lowered for term in ("fund", "funding", "grant", "loan", "finance", "investment", "amount", "budget", "offer")):
            funding_lines.append(tagged)
        if any(term in lowered for term in ("eligibility", "criteria", "requirements", "who can apply", "qualif", "turnover", "employee", "ownership")):
            eligibility_lines.append(tagged)
        if any(term in lowered for term in ("apply", "application", "portal", "register", "submission", "submit", "deadline", "closing date", "how to apply")):
            application_lines.append(tagged)
        if any(term in lowered for term in ("document", "documents", "checklist", "certificate", "proof", "registration", "required")):
            required_documents.append(tagged)
        notes.append(f"Document evidence read from {item.document_url}")

    # The combined text is the compact summary used by prompt builders and
    # deterministic fallback extractors.
    combined_text = compact_document_text("\n".join(evidence_lines), max_chars=MAX_DOCUMENT_SUMMARY_CHARS)
    combined_for_extraction = " ".join(
        [
            combined_text,
            " ".join(funding_lines),
            " ".join(eligibility_lines),
            " ".join(application_lines),
        ]
    ).strip()
    urls = unique_preserve_order(extract_urls(combined_for_extraction))
    emails = unique_preserve_order(extract_emails(combined_for_extraction))
    phones = unique_preserve_order(extract_phone_numbers(combined_for_extraction))
    return {
        "combined_text": combined_text,
        "evidence_lines": evidence_lines,
        "funding_lines": funding_lines,
        "eligibility_lines": eligibility_lines,
        "application_lines": application_lines,
        "required_documents": unique_preserve_order(required_documents),
        "urls": urls,
        "emails": emails,
        "phones": phones,
        "notes": unique_preserve_order(notes),
    }


def _payback_source_text(document: PageContentDocument, document_context: Dict[str, Any], derived: Dict[str, Any]) -> str:
    # Payback extraction looks across the main page, the document evidence, and
    # the already-derived raw text fields so repayment wording is not missed.
    parts: List[str] = [
        document.title or "",
        document.page_title or "",
        document.full_body_text or "",
        _interactive_sections_text(document),
        document_context.get("combined_text") or "",
        " ".join(derived.get("raw_terms_data") or []),
        " ".join(derived.get("raw_funding_offer_data") or []),
        " ".join(derived.get("raw_application_data") or []),
    ]
    return " ".join(unique_preserve_order([clean_text(part) for part in parts if clean_text(part)]))


def _eligibility_source_text(document: PageContentDocument, document_context: Dict[str, Any], derived: Dict[str, Any]) -> str:
    # Eligibility extraction reuses the broadest relevant text surface so the
    # structured criteria extractor sees the same wording the AI would see.
    parts: List[str] = [
        document.title or "",
        document.page_title or "",
        document.full_body_text or "",
        _interactive_sections_text(document),
        document_context.get("combined_text") or "",
        " ".join(derived.get("raw_eligibility_data") or []),
        " ".join(derived.get("raw_terms_data") or []),
    ]
    return " ".join(unique_preserve_order([clean_text(part) for part in parts if clean_text(part)]))


def _looks_like_funder_name(candidate: str) -> bool:
    # A funder name needs to look like an organization, not a navigation label
    # or other generic site text.
    text = clean_text(candidate or "")
    if not text:
        return False
    lowered = text.casefold()
    if lowered in GENERIC_FUNDER_TOKENS:
        return False
    if any(term in lowered for term in FUNDER_HINT_TERMS):
        return True
    return len(text.split()) >= 2


def _extract_funder_name_from_title(title: Optional[str]) -> Optional[str]:
    # Some titles encode "page title - funder name"; this pulls the likely
    # organization part off the right side of the separator.
    cleaned = clean_text(title or "")
    if not cleaned:
        return None
    parts = FUNDER_SEPARATOR_PATTERN.split(cleaned, maxsplit=1)
    if len(parts) < 2:
        return None
    candidate = clean_text(parts[-1])
    return candidate if _looks_like_funder_name(candidate) else None


def _humanize_source_domain(domain: Optional[str]) -> Optional[str]:
    # When no explicit funder is available, the source domain is used as a
    # human-readable fallback.
    cleaned = clean_text(domain or "")
    if not cleaned:
        return None
    alias = DOMAIN_FUNDER_ALIASES.get(cleaned.lower().removeprefix("https://").removeprefix("http://").strip("/"))
    if alias:
        return alias
    host = cleaned.lower().removeprefix("www.")
    alias = DOMAIN_FUNDER_ALIASES.get(host)
    if alias:
        return alias
    parts = [part for part in host.split(".") if part]
    while parts and parts[-1] in COMMON_TLDS:
        parts.pop()
    while parts and parts[0] == "www":
        parts.pop(0)
    if not parts:
        return None
    candidate = parts[0]
    return candidate.replace("-", " ").replace("_", " ").title()


def _infer_funder_name(document: PageContentDocument, payload: Dict[str, Any]) -> Optional[str]:
    # Funder inference prefers explicit extracted text, then title patterns, then
    # a cleaned-up domain fallback.
    explicit = _coerce_optional_text(payload.get("funder_name"))
    if explicit and not re.fullmatch(r"(?:www\.)?[a-z0-9.-]+\.[a-z]{2,}(?:\.[a-z]{2,})*", explicit.casefold() or ""):
        return explicit

    for title_candidate in (
        _extract_funder_name_from_title(document.title),
        _extract_funder_name_from_title(document.page_title),
        _extract_funder_name_from_title(_coerce_optional_text(payload.get("source_page_title"))),
    ):
        if title_candidate:
            return title_candidate

    source_domain = _coerce_optional_text(payload.get("source_domain")) or document.source_domain or extract_domain(document.page_url)
    return _humanize_source_domain(source_domain)


def _estimate_prompt_size(payload: Dict[str, Any]) -> int:
    # The size estimate is intentionally approximate; it is only used for guardrails.
    return len(json.dumps(payload, ensure_ascii=False)) // 4


def _normalize_page_decision(value: Any) -> str:
    # The model can phrase the page decision several ways, so normalize them to
    # the small enum the rest of the code expects.
    text = _coerce_text(value).casefold().replace("-", "_").replace(" ", "_")
    if text in {
        PAGE_DECISION_FUNDING_PROGRAM,
        PAGE_TYPE_FUNDING_PROGRAMME,
        "funding_listing",
        PAGE_TYPE_OPEN_CALL,
        "fundingprogramme",
        "funding_programme",
        "programme",
        "program",
        "programme_page",
        "program_page",
    }:
        return PAGE_DECISION_FUNDING_PROGRAM
    if text in {
        PAGE_DECISION_NOT_FUNDING_PROGRAM,
        PAGE_TYPE_SUPPORT_PROGRAMME,
        PAGE_TYPE_TECHNOLOGY_STATION,
        PAGE_TYPE_TENDER_PROCUREMENT,
        PAGE_TYPE_NEWS_ARTICLE,
        PAGE_TYPE_GENERIC_CONTENT,
        "not_program",
        "not_programme",
        "non_program",
        "non_programme",
        "not_fundingprogramme",
        "not_funding_programme",
        "notfundingprogram",
        "not_program_page",
        "no",
        "false",
    }:
        return PAGE_DECISION_NOT_FUNDING_PROGRAM
    if text in {PAGE_DECISION_UNCLEAR, "unknown", "unsure", "maybe", "uncertain"}:
        return PAGE_DECISION_UNCLEAR
    return PAGE_DECISION_UNCLEAR


def normalize_page_role(value: Any) -> str:
    text = _coerce_text(value).casefold().replace("-", "_").replace("/", "_").replace(" ", "_")
    aliases = {
        "overview": PAGE_ROLE_OVERVIEW,
        "programme_detail": PAGE_ROLE_OVERVIEW,
        "program_detail": PAGE_ROLE_OVERVIEW,
        "eligibility": PAGE_ROLE_ELIGIBILITY,
        "criteria": PAGE_ROLE_ELIGIBILITY,
        "application": PAGE_ROLE_APPLICATION,
        "apply": PAGE_ROLE_APPLICATION,
        "checklist": PAGE_ROLE_CHECKLIST,
        "documents": PAGE_ROLE_CHECKLIST,
        "funding_detail": PAGE_ROLE_FUNDING_DETAIL,
        "funding": PAGE_ROLE_FUNDING_DETAIL,
        "listing": PAGE_ROLE_LISTING,
        "procurement": PAGE_ROLE_PROCUREMENT_NOTICE,
        "procurement_notice": PAGE_ROLE_PROCUREMENT_NOTICE,
        "news": PAGE_ROLE_NEWS_ARTICLE,
        "news_article": PAGE_ROLE_NEWS_ARTICLE,
        "about": PAGE_ROLE_ABOUT_CONTACT,
        "contact": PAGE_ROLE_ABOUT_CONTACT,
        "about_contact": PAGE_ROLE_ABOUT_CONTACT,
        "support": PAGE_ROLE_SUPPORT_DETAIL,
        "support_detail": PAGE_ROLE_SUPPORT_DETAIL,
        "technology_station": PAGE_ROLE_TECHNOLOGY_STATION,
        "generic": PAGE_ROLE_GENERIC,
    }
    return aliases.get(text, PAGE_ROLE_GENERIC)


def _canonical_programme_path_key(urls: Sequence[str]) -> str:
    for url in urls:
        path = urlparse(url or "").path.casefold().strip("/")
        if not path:
            continue
        parts = [part for part in path.split("/") if part]
        if not parts:
            continue
        last = parts[-1]
        for suffix in PAGE_ROLE_SUPPORT_SUFFIXES:
            if last == suffix:
                parts = parts[:-1]
                break
            if last.endswith("-" + suffix):
                parts[-1] = last[: -(len(suffix) + 1)]
                break
        cleaned = "/".join(part for part in parts if part)
        if cleaned:
            return cleaned
    return ""


def _record_canonical_group_key(record: FundingProgrammeRecord) -> str:
    normalized_program = clean_text(record.program_name or record.parent_programme_name or "").casefold()
    normalized_funder = clean_text(record.funder_name or "").casefold()
    path_key = _canonical_programme_path_key(record.source_urls or [record.source_url])
    if normalized_program and normalized_funder:
        return f"{record.source_domain}:{normalized_funder}:{normalized_program}"
    if path_key:
        return f"{record.source_domain}:{path_key}"
    return f"{record.source_domain}:{clean_text(record.source_url).casefold()}"


def _infer_page_role(document: PageContentDocument, page_type: str, existing_role: Any = None) -> str:
    normalized_existing = normalize_page_role(existing_role)
    if normalized_existing != PAGE_ROLE_GENERIC:
        return normalized_existing
    normalized_page_type = normalize_page_type(page_type)
    haystack = " ".join(
        [
            document.page_url or "",
            document.title or "",
            document.page_title or "",
            document.full_body_text or "",
            " ".join(document.headings or []),
        ]
    ).casefold()
    if normalized_page_type == PAGE_TYPE_FUNDING_LISTING:
        return PAGE_ROLE_LISTING
    if normalized_page_type == PAGE_TYPE_TENDER_PROCUREMENT:
        return PAGE_ROLE_PROCUREMENT_NOTICE
    if normalized_page_type == PAGE_TYPE_NEWS_ARTICLE:
        return PAGE_ROLE_NEWS_ARTICLE
    if normalized_page_type == PAGE_TYPE_TECHNOLOGY_STATION:
        return PAGE_ROLE_TECHNOLOGY_STATION
    if normalized_page_type == PAGE_TYPE_SUPPORT_PROGRAMME:
        return PAGE_ROLE_SUPPORT_DETAIL
    if any(term in haystack for term in ABOUT_CONTACT_TERMS):
        return PAGE_ROLE_ABOUT_CONTACT
    if any(term in haystack for term in ("checklist", "required documents", "supporting documents", "paperwork needed")):
        return PAGE_ROLE_CHECKLIST
    if any(term in haystack for term in ("apply", "application", "register", "submission portal", "how to apply")):
        return PAGE_ROLE_APPLICATION
    if any(term in haystack for term in ("eligibility", "criteria", "who qualifies", "requirements")):
        return PAGE_ROLE_ELIGIBILITY
    if any(term in haystack for term in ("funding amount", "ticket size", "loan amount", "grant amount", "repayment", "interest rate")):
        return PAGE_ROLE_FUNDING_DETAIL
    return PAGE_ROLE_OVERVIEW


def _page_decision_hint(document: PageContentDocument) -> Tuple[str, List[str]]:
    # This is the cheap pre-model heuristic that guesses whether the page is a
    # real funding programme or just generic site content.
    text = " ".join(
        [
            document.page_url or "",
            document.title or "",
            document.page_title or "",
            " ".join(document.headings or []),
            document.main_content_hint or "",
            (document.full_body_text or "")[:2000],
            _interactive_sections_text(document),
        ]
    ).casefold()
    inferred_page_type = _classify_enhancer_page_type(
        record_count=max(1, len(document.headings) // 2) if document.headings else 0,
        candidate_block_count=max(1, len(document.structured_sections) or len(document.headings) or 1),
        internal_link_count=len(document.internal_links),
        detail_link_count=len(document.discovered_links),
        application_link_count=len(document.application_links),
        document_link_count=len(document.document_links),
        text=text,
    )
    program_hits = [term for term in PROGRAMME_SIGNAL_TERMS if term in text]
    non_program_hits = [term for term in NON_PROGRAMME_SIGNAL_TERMS if term in text]
    file_like = bool(re.search(r"\bimg[-_ ]?\d|\.(?:jpe?g|png|gif|webp|pdf)(?:\b|$)", text))
    if inferred_page_type in {
        PAGE_TYPE_TENDER_PROCUREMENT,
        PAGE_TYPE_NEWS_ARTICLE,
        PAGE_TYPE_TECHNOLOGY_STATION,
        PAGE_TYPE_SUPPORT_PROGRAMME,
        PAGE_TYPE_GENERIC_CONTENT,
    }:
        return PAGE_DECISION_NOT_FUNDING_PROGRAM, [f"inferred page_type {inferred_page_type}"]
    if file_like and len(program_hits) < 2:
        # File-like URLs without enough programme evidence are treated as
        # non-program pages because they are usually attachments or media.
        return PAGE_DECISION_NOT_FUNDING_PROGRAM, ["title or URL looks like a file or media asset"]
    if len(non_program_hits) >= 2 and len(program_hits) == 0:
        # Generic article/news/privacy signals override weak funding language.
        return PAGE_DECISION_NOT_FUNDING_PROGRAM, ["page matches generic article/media/policy signals"]
    if len(program_hits) >= 2:
        # Multiple programme signals are enough to treat the page as a likely
        # funding page even before the model sees it.
        return PAGE_DECISION_FUNDING_PROGRAM, [f"contains programme signals: {', '.join(program_hits[:4])}"]
    if len(program_hits) == 1 and len(non_program_hits) == 0 and len((document.full_body_text or "").strip()) >= 600:
        # A single strong funding signal can still be enough if the page body is
        # substantial and otherwise clean.
        return PAGE_DECISION_FUNDING_PROGRAM, [f"contains funding signal: {program_hits[0]}"]
    return PAGE_DECISION_UNCLEAR, []


def _source_scope_for_page_type(page_type: str) -> str:
    normalized = normalize_page_type(page_type)
    if normalized == "funding_listing":
        return "listing_page"
    if normalized in {"support_programme", "technology_station"}:
        return "support_page"
    if normalized in {"news_article", "tender_procurement", "generic_content"}:
        return "non_programme_page"
    return "product_page"


def _classify_enhancer_page_type(
    *,
    record_count: int,
    candidate_block_count: int,
    internal_link_count: int,
    detail_link_count: int,
    application_link_count: int,
    document_link_count: int,
    text: str,
) -> str:
    page_type = normalize_page_type(
        classify_global_page_type(
            record_count=record_count,
            candidate_block_count=candidate_block_count,
            internal_link_count=internal_link_count,
            detail_link_count=detail_link_count,
            application_link_count=application_link_count,
            document_link_count=document_link_count,
            text=text,
        )
    )
    lowered = clean_text(text or "").casefold()
    detail_term_hits = sum(
        1
        for term in (
            "eligibility",
            "application",
            "apply",
            "submit",
            "funding amount",
            "loan amount",
            "grant amount",
            "finance is available",
            "available up to",
            "repayment",
            "repayment term",
            "trading history",
            "collateral",
            "supporting documents",
            "required documents",
        )
        if term in lowered
    )
    if (
        page_type == PAGE_TYPE_FUNDING_LISTING
        and record_count <= 1
        and candidate_block_count <= 8
        and detail_link_count <= 2
        and internal_link_count <= 8
        and (_has_programme_detail_signals(lowered) or detail_term_hits >= 2)
    ):
        return PAGE_TYPE_FUNDING_PROGRAMME
    return page_type


def _add_review_reason(record: FundingProgrammeRecord, code: str, note: Optional[str] = None) -> FundingProgrammeRecord:
    if code:
        record.needs_review_reasons = unique_preserve_order([*record.needs_review_reasons, code])
        record.needs_review = True
    if note:
        record.notes = unique_preserve_order([*record.notes, note])
    return record


def _looks_like_valid_programme_name(value: Optional[str]) -> bool:
    text = clean_text(value or "")
    if not text or len(text) < 4:
        return False
    lowered = text.casefold()
    if lowered in INVALID_PROGRAMME_NAME_TERMS:
        return False
    if looks_like_tender_title(text):
        return False
    if looks_like_support_title(text) and not any(term in lowered for term in ("grant", "loan", "equity", "fund", "capital")):
        return False
    if re.fullmatch(r"(?:page|detail|details|listing|mixed|generic)", lowered):
        return False
    if re.fullmatch(r"(?:\d+|[ivxlcdm]+)", lowered, re.I):
        return False
    return True


def _looks_like_valid_funder_name(value: Optional[str]) -> bool:
    text = clean_text(value or "")
    if not text:
        return False
    lowered = text.casefold()
    if lowered in INVALID_FUNDER_NAME_TERMS:
        return False
    if re.fullmatch(r"(?:www\.)?[a-z0-9.-]+\.[a-z]{2,}(?:\.[a-z]{2,})*", lowered):
        return False
    return _looks_like_funder_name(text)


def _money_context_is_invalid(text: str) -> bool:
    lowered = clean_text(text or "").casefold()
    if not lowered:
        return False
    positive_context = bool(MONEY_POSITIVE_CONTEXT_RE.search(lowered))
    if MONEY_INVALID_CONTEXT_RE.search(lowered) or MONEY_INVALID_PERCENT_RE.search(lowered):
        return True
    if MONEY_INVALID_TRL_RE.search(lowered):
        return True
    if MONEY_INVALID_PHONE_RE.fullmatch(lowered):
        return True
    if not positive_context and (MONEY_INVALID_DATE_RE.search(lowered) or MONEY_INVALID_YEAR_RE.fullmatch(lowered)):
        return True
    return False


def _money_evidence_snippets(record: FundingProgrammeRecord) -> List[str]:
    snippets = []
    for key in ("ticket_range", "ticket_min", "ticket_max", "program_budget_total", "raw_funding_offer_data"):
        snippets.extend(record.evidence_by_field.get(key, []))
        snippets.extend(record.raw_text_snippets.get(key, []))
    snippets.extend(record.raw_funding_offer_data)
    return unique_preserve_order([clean_text(snippet) for snippet in snippets if clean_text(snippet)])


def _looks_like_money_snippet(text: str) -> bool:
    snippet = clean_text(text or "")
    if not snippet:
        return False
    return bool(MONEY_SNIPPET_SIGNAL_RE.search(snippet))


def _validate_post_ai_money_fields(record: FundingProgrammeRecord, document: PageContentDocument) -> FundingProgrammeRecord:
    snippets = _money_evidence_snippets(record)
    money_snippets = [snippet for snippet in snippets if _looks_like_money_snippet(snippet)]
    has_amount_fields = any(
        value is not None for value in (record.ticket_min, record.ticket_max, record.program_budget_total)
    )
    invalid_numeric_snippets = [
        snippet
        for snippet in snippets
        if any(
            pattern.search(snippet)
            for pattern in (
                MONEY_INVALID_CONTEXT_RE,
                MONEY_INVALID_DATE_RE,
                MONEY_INVALID_YEAR_RE,
                MONEY_INVALID_PERCENT_RE,
                MONEY_INVALID_PHONE_RE,
                MONEY_INVALID_TRL_RE,
            )
        )
    ]
    combined_text = " ".join(
        [
            document.title or "",
            document.page_title or "",
            " ".join(money_snippets or snippets),
        ]
    )
    invalid_snippets = [
        snippet
        for snippet in money_snippets
        if _money_context_is_invalid(snippet)
        and extract_money_range(snippet, default_currency=record.currency)[3] is None
    ]
    if has_amount_fields and not money_snippets:
        record.ticket_min = None
        record.ticket_max = None
        if record.program_budget_total is not None:
            record.program_budget_total = None
        reason = REVIEW_REASON_INVALID_MONEY_CONTEXT if invalid_numeric_snippets else REVIEW_REASON_WEAK_MONEY_EVIDENCE
        note = (
            "Rejected AI money values because evidence matched invalid numeric context."
            if invalid_numeric_snippets
            else "Removed unsupported AI amount because no trustworthy money evidence was found."
        )
        record = _add_review_reason(record, reason, note)
        record.validation_errors = unique_preserve_order(
            [
                *record.validation_errors,
                "invalid money evidence context" if invalid_numeric_snippets else "money amount could not be validated from evidence",
            ]
        )
        return record
    deterministic_min, deterministic_max, deterministic_currency, _snippet, deterministic_confidence = extract_money_range(
        combined_text,
        default_currency=record.currency,
    )
    if invalid_snippets:
        record.ticket_min = None
        record.ticket_max = None
        if record.program_budget_total is not None and not any("budget" in snippet.casefold() for snippet in snippets):
            record.program_budget_total = None
        record = _add_review_reason(record, REVIEW_REASON_INVALID_MONEY_CONTEXT, "Rejected AI money values because evidence matched invalid numeric context.")
        record.validation_errors = unique_preserve_order([*record.validation_errors, "invalid money evidence context"])
        return record
    if (record.ticket_min is not None or record.ticket_max is not None) and deterministic_min is None and deterministic_max is None:
        record.ticket_min = None
        record.ticket_max = None
        record = _add_review_reason(record, REVIEW_REASON_WEAK_MONEY_EVIDENCE, "Removed unsupported AI amount because deterministic validation found no valid money evidence.")
        record.validation_errors = unique_preserve_order([*record.validation_errors, "money amount could not be validated from evidence"])
        return record
    if deterministic_confidence and deterministic_confidence < 0.7 and (record.ticket_min is not None or record.ticket_max is not None):
        record = _add_review_reason(record, REVIEW_REASON_WEAK_MONEY_EVIDENCE, "Money evidence exists but remains weak after deterministic validation.")
    if deterministic_currency and not record.currency:
        record.currency = deterministic_currency
    if record.program_budget_total is not None:
        budget_text = str(int(record.program_budget_total)) if isinstance(record.program_budget_total, float) and record.program_budget_total.is_integer() else str(record.program_budget_total)
        if MONEY_INVALID_YEAR_RE.fullmatch(budget_text):
            record.program_budget_total = None
            record = _add_review_reason(record, REVIEW_REASON_INVALID_MONEY_CONTEXT, "Rejected budget-like value because it looked like a year.")
    return record


def _record_money_fields_are_valid(record: FundingProgrammeRecord) -> bool:
    has_amount_fields = any(value is not None for value in (record.ticket_min, record.ticket_max, record.program_budget_total))
    if not has_amount_fields:
        return True
    if any(
        reason in record.needs_review_reasons
        for reason in (REVIEW_REASON_INVALID_MONEY_CONTEXT, REVIEW_REASON_WEAK_MONEY_EVIDENCE)
    ):
        return False
    snippets = [snippet for snippet in _money_evidence_snippets(record) if _looks_like_money_snippet(snippet)]
    if not snippets:
        return False
    minimum, maximum, _currency, _snippet, _confidence = extract_money_range(" ".join(snippets), default_currency=record.currency)
    if record.ticket_min is not None and minimum is None and maximum is None:
        return False
    if record.ticket_max is not None and minimum is None and maximum is None:
        return False
    return True


def _finalize_record_acceptance(record: FundingProgrammeRecord) -> Optional[FundingProgrammeRecord]:
    page_type = normalize_page_type(record.page_type)
    record.page_type = page_type

    if page_type in {
        PAGE_TYPE_TENDER_PROCUREMENT,
        PAGE_TYPE_NEWS_ARTICLE,
        PAGE_TYPE_TECHNOLOGY_STATION,
        PAGE_TYPE_SUPPORT_PROGRAMME,
        PAGE_TYPE_GENERIC_CONTENT,
    }:
        logger.info("ai_record_rejected_page_type", source_url=record.source_url, page_type=page_type, program_name=record.program_name)
        return None

    if page_type == PAGE_TYPE_OPEN_CALL and not has_fundable_support(record):
        record = _add_review_reason(record, REVIEW_REASON_UNFUNDABLE_OPEN_CALL, "Rejected open call because no explicit fundable support was confirmed.")
        logger.info("ai_record_rejected_unfundable_open_call", source_url=record.source_url, program_name=record.program_name)
        return None

    if page_type == PAGE_TYPE_FUNDING_LISTING and record.funding_type == FundingType.UNKNOWN:
        record = _add_review_reason(record, REVIEW_REASON_LISTING_UNKNOWN_FUNDING_TYPE, "Rejected listing-derived record because funding type remained Unknown.")
        logger.info("ai_record_rejected_listing_unknown_funding_type", source_url=record.source_url, program_name=record.program_name)
        return None

    path = urlparse(record.source_url).path.casefold()
    if record.funding_type == FundingType.UNKNOWN and re.search(r"(?:^|/)(?:faq|faqs|frequently-asked-questions)(?:-|/|$)", path):
        record = _add_review_reason(record, REVIEW_REASON_SUPPORT_UNKNOWN_FUNDING_TYPE, "Rejected support/FAQ record because funding type remained Unknown.")
        logger.info("ai_record_rejected_support_unknown_funding_type", source_url=record.source_url, program_name=record.program_name)
        return None

    valid_program_name = _looks_like_valid_programme_name(record.program_name)
    valid_funder_name = _looks_like_valid_funder_name(record.funder_name)
    valid_money_fields = _record_money_fields_are_valid(record)
    confirmed_final_page_type = page_type in {PAGE_TYPE_FUNDING_PROGRAMME, PAGE_TYPE_OPEN_CALL}

    if not valid_program_name:
        record = _add_review_reason(record, REVIEW_REASON_INVALID_PROGRAM_NAME, "Programme name did not look like a specific funding programme title.")
    if not valid_funder_name:
        record = _add_review_reason(record, REVIEW_REASON_INVALID_FUNDER_NAME, "Funder name did not look like a specific organization.")
    if not confirmed_final_page_type:
        record = _add_review_reason(record, REVIEW_REASON_UNCONFIRMED_PAGE_TYPE, f"Page type {page_type} is not a confirmed final programme detail page.")

    can_clear_review = (
        confirmed_final_page_type
        and valid_program_name
        and valid_funder_name
        and record.funding_type != FundingType.UNKNOWN
        and valid_money_fields
        and not record.validation_errors
        and not record.needs_review_reasons
    )
    record.needs_review = not can_clear_review
    return FundingProgrammeRecord.model_validate(record.model_dump(mode="python"))


def _apply_record_review_flags(record: FundingProgrammeRecord) -> FundingProgrammeRecord:
    if record.funding_type == FundingType.UNKNOWN:
        record = _add_review_reason(record, REVIEW_REASON_UNKNOWN_FUNDING_TYPE, "Funding type remains Unknown after AI normalization.")
    if record.field_conflicts:
        record = _add_review_reason(record, REVIEW_REASON_CONFLICTING_FIELD_VALUES, "Multiple sources disagreed on one or more important fields.")
    missing_core_evidence = [
        field_name for field_name in IMPORTANT_EVIDENCE_FIELDS if getattr(record, field_name, None) not in (None, "", [], {}) and not record.evidence_by_field.get(field_name)
    ]
    if missing_core_evidence:
        record.validation_errors = unique_preserve_order(
            [*record.validation_errors, *[f"missing evidence for {field_name}" for field_name in missing_core_evidence]]
        )
        record = _add_review_reason(record, REVIEW_REASON_MISSING_CORE_EVIDENCE, "Important extracted fields were missing direct traceable evidence.")
    if record.page_type and normalize_page_type(record.page_type) in {
        PAGE_TYPE_TENDER_PROCUREMENT,
        PAGE_TYPE_NEWS_ARTICLE,
        PAGE_TYPE_TECHNOLOGY_STATION,
        PAGE_TYPE_SUPPORT_PROGRAMME,
        PAGE_TYPE_GENERIC_CONTENT,
    }:
        record = _add_review_reason(record, REVIEW_REASON_NON_PROGRAMME_PAGE, f"Source page classified as {record.page_type}.")
    return record


def _collect_section_snippets(
    document: PageContentDocument,
    heading_terms: Sequence[str],
    body_terms: Sequence[str],
    *,
    fallback_chars: int = 1200,
    max_sentences: int = 4,
) -> List[str]:
    # This helper pulls sentence-sized snippets from the sections most likely to
    # contain the requested terms, then falls back to the body text if needed.
    snippets: List[str] = []
    for section in document.structured_sections:
        heading = clean_text(section.heading).lower()
        content = clean_text(section.content)
        lowered_content = content.lower()
        if not content:
            continue
        if any(term in heading for term in heading_terms) or any(term in lowered_content for term in body_terms):
            snippets.extend(sentence_chunks(content) or [content])
    if not snippets and document.full_body_text:
        for sentence in sentence_chunks(document.full_body_text):
            lowered_sentence = sentence.lower()
            if any(term in lowered_sentence for term in body_terms):
                snippets.append(sentence)
                if len(snippets) >= max_sentences:
                    break
    if not snippets and document.full_body_text:
        snippets.append(document.full_body_text[:fallback_chars])
    cleaned = [clean_text(item) for item in snippets if clean_text(item)]
    return unique_preserve_order(cleaned)


def _derive_page_evidence(document: PageContentDocument) -> Dict[str, Any]:
    # This is the deterministic evidence extractor: it scans the page body and
    # grouped sections for funding, eligibility, document, and application text.
    funding_offer = _collect_section_snippets(
        document,
        heading_terms=("fund", "funding", "finance", "loan", "grant", "offer", "investment"),
        body_terms=("fund", "funding", "finance", "loan", "grant", "equity", "investment"),
    )
    eligibility = _collect_section_snippets(
        document,
        heading_terms=(
            "eligibility",
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
        ),
        body_terms=(
            "eligibility",
            "criteria",
            "requirement",
            "qualify",
            "ownership",
            "stage",
            "compliance",
            "condition",
            "mandatory",
            "selection",
            "application criteria",
            "funding criteria",
            "investment criteria",
        ),
    )
    terms = unique_preserve_order(
        [
            *eligibility,
            *_collect_section_snippets(
                document,
                heading_terms=("terms", "conditions", "deadline", "timing", "structure", "repayment", "interest"),
                body_terms=("terms", "conditions", "deadline", "repayment", "interest", "security", "equity"),
            ),
        ]
    )
    documents = _collect_section_snippets(
        document,
        heading_terms=("document", "documents", "checklist", "paperwork", "required documents"),
        body_terms=("document", "documents", "checklist", "paperwork", "certificate", "registration"),
    )
    application = _collect_section_snippets(
        document,
        heading_terms=("apply", "application", "portal", "register", "how to apply", "submission"),
        body_terms=("apply", "application", "portal", "register", "submit", "submission"),
    )
    # The raw snippet groups are kept separate so later stages can reuse the
    # exact supporting text they need without rescanning the page.
    snippets: Dict[str, List[str]] = {
        "title": [document.title] if document.title else [],
        "full_body_text": [document.full_body_text[:MAX_BODY_CHARS]] if document.full_body_text else [],
        "structured_sections": [
            clean_text(f"{section.heading}: {section.content}")
            for section in document.structured_sections
            if clean_text(section.heading) or clean_text(section.content)
        ],
        "funding_offer_data": funding_offer,
        "eligibility_data": eligibility,
        "terms_data": terms,
        "documents_data": documents,
        "application_data": application,
    }
    raw_snippets = {key: value for key, value in snippets.items() if value}
    confidence = {}
    for key, values in raw_snippets.items():
        if key in {"title", "full_body_text"}:
            confidence[key] = 0.7
        elif values:
            confidence[key] = min(0.95, 0.55 + min(len(values), 4) * 0.08)
    return {
        "raw_eligibility_data": eligibility or None,
        "raw_eligibility_criteria": extract_eligibility_criteria(" ".join(eligibility)),
        "raw_funding_offer_data": funding_offer or [],
        "raw_terms_data": terms or [],
        "raw_documents_data": documents or [],
        "raw_application_data": application or [],
        "raw_text_snippets": raw_snippets,
        "extraction_confidence": confidence,
    }


def _derive_eligibility_profile(
    text: str,
    *,
    industry_taxonomy: Dict[str, List[str]],
    use_of_funds_taxonomy: Dict[str, List[str]],
    ownership_target_keywords: Dict[str, List[str]],
    entity_type_keywords: Dict[str, List[str]],
    certification_keywords: Dict[str, List[str]],
) -> Dict[str, Any]:
    # This function turns plain eligibility text into structured schema fields
    # without relying on the AI model to infer obvious eligibility constraints.
    lowered = (text or "").lower()
    industries = unique_preserve_order(match_keyword_map(text, industry_taxonomy)[0]) if industry_taxonomy else []
    use_of_funds = unique_preserve_order(match_keyword_map(text, use_of_funds_taxonomy)[0]) if use_of_funds_taxonomy else []
    ownership_targets = unique_preserve_order(match_keyword_map(text, ownership_target_keywords)[0]) if ownership_target_keywords else []
    entity_types_allowed = unique_preserve_order(match_keyword_map(text, entity_type_keywords)[0]) if entity_type_keywords else []
    certifications_required = unique_preserve_order(match_keyword_map(text, certification_keywords)[0]) if certification_keywords else []
    business_stage_eligibility = _extract_stage_labels(text)
    turnover_min = turnover_max = None
    for sentence in sentence_chunks(text):
        # Turnover is extracted sentence-by-sentence so unrelated amounts do not
        # leak into the eligibility profile.
        lowered_sentence = sentence.lower()
        if not any(term in lowered_sentence for term in ("turnover", "revenue", "sales", "annual turnover", "annual revenue")):
            continue
        minimum, maximum, _currency, _snippet, _confidence = extract_money_range(sentence, default_currency=None)
        if minimum is not None or maximum is not None:
            turnover_min, turnover_max = minimum, maximum
            break
    years_in_business_min = years_in_business_max = None
    employee_min = employee_max = None
    years_patterns = [
        re.compile(r"(?:at least|min(?:imum)?(?: of)?|not less than)\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?)", re.I),
        re.compile(r"(\d+(?:\.\d+)?)\s*(?:to|-)\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?)", re.I),
        re.compile(r"(\d+(?:\.\d+)?)\s*(?:years?|yrs?)\s*(?:in business|of trading|trading|operating)", re.I),
    ]
    employee_patterns = [
        re.compile(r"(?:at least|min(?:imum)?(?: of)?|not less than)\s*(\d+(?:\.\d+)?)\s*(?:employees|staff|workers|headcount)", re.I),
        re.compile(r"(\d+(?:\.\d+)?)\s*(?:to|-)\s*(\d+(?:\.\d+)?)\s*(?:employees|staff|workers|headcount)", re.I),
        re.compile(r"(\d+(?:\.\d+)?)\s*(?:employees|staff|workers|headcount)", re.I),
    ]
    for sentence in sentence_chunks(text):
        # Business age and staff-count requirements follow the same targeted
        # sentence scan as turnover.
        lowered_sentence = sentence.lower()
        if years_in_business_min is None and any(term in lowered_sentence for term in ("years in business", "trading for", "in operation for", "operating for", "established for", "business age")):
            for pattern in years_patterns:
                match = pattern.search(sentence)
                if not match:
                    continue
                if len(match.groups()) == 2 and match.group(2):
                    years_in_business_min = _coerce_float(match.group(1))
                    years_in_business_max = _coerce_float(match.group(2))
                    break
                if len(match.groups()) == 1:
                    value = _coerce_float(match.group(1))
                    if value is not None:
                        years_in_business_min = value
                        years_in_business_max = None
                        break
        if employee_min is None and any(term in lowered_sentence for term in ("employees", "staff", "workers", "full-time employees", "headcount", "employees in total")):
            for pattern in employee_patterns:
                match = pattern.search(sentence)
                if not match:
                    continue
                if len(match.groups()) == 2 and match.group(2):
                    employee_min = _coerce_float(match.group(1))
                    employee_max = _coerce_float(match.group(2))
                    break
                if len(match.groups()) == 1:
                    value = _coerce_float(match.group(1))
                    if value is not None:
                        employee_min = value
                        employee_max = None
                        break
        if years_in_business_min is not None and employee_min is not None:
            break
    return {
        "industries": industries,
        "use_of_funds": use_of_funds,
        "business_stage_eligibility": business_stage_eligibility,
        "turnover_min": turnover_min,
        "turnover_max": turnover_max,
        "years_in_business_min": years_in_business_min,
        "years_in_business_max": years_in_business_max,
        "employee_min": int(employee_min) if employee_min is not None else None,
        "employee_max": int(employee_max) if employee_max is not None else None,
        "ownership_targets": ownership_targets,
        "entity_types_allowed": entity_types_allowed,
        "certifications_required": certifications_required,
        "raw_eligibility_data": unique_preserve_order([clean_text(item) for item in sentence_chunks(text) if clean_text(item)]),
    }


def _combine_eligibility_text(
    document: PageContentDocument,
    eligibility_items: Sequence[str],
    extra_items: Sequence[str] = (),
) -> str:
    # Combine every eligibility-adjacent source into one deduplicated string so
    # the extractor sees a single coherent evidence surface.
    parts = [
        *[clean_text(item) for item in eligibility_items if clean_text(item)],
        *[clean_text(item) for item in extra_items if clean_text(item)],
        *[section.content for section in document.structured_sections if clean_text(section.content)],
        _interactive_sections_text(document),
        document.full_body_text or "",
        document.title or "",
    ]
    return " ".join(unique_preserve_order([part for part in parts if part]))


def _merge_drafts(drafts: Sequence[AIProgrammeDraft]) -> List[AIProgrammeDraft]:
    # Duplicated AI drafts are merged by normalized program name plus source URL
    # so repeated model output does not create duplicate records.
    merged: Dict[Tuple[str, str], AIProgrammeDraft] = {}
    fallback: List[AIProgrammeDraft] = []
    for draft in drafts:
        program_name = _coerce_text(draft.program_name)
        source_url = _coerce_text(draft.source_url)
        if program_name and source_url:
            key = (program_name.casefold(), source_url)
            current = merged.get(key)
            if current is None:
                merged[key] = draft
                continue
            merged[key] = _merge_two_drafts(current, draft)
        else:
            fallback.append(draft)
    return [*merged.values(), *fallback]


def _merge_two_drafts(left: AIProgrammeDraft, right: AIProgrammeDraft) -> AIProgrammeDraft:
    # Draft merge favors the left-hand record and only fills gaps from the right
    # unless the field is a list or evidence map that should be unioned.
    payload = left.model_dump(mode="python")
    candidate = right.model_dump(mode="python")
    for key, value in candidate.items():
        if value in (None, "", [], {}):
            continue
        if key in {"notes", "funding_lines", "related_documents", "required_documents", "exclusions"}:
            payload[key] = unique_preserve_order([*(payload.get(key) or []), *value])
            continue
        if key in {"raw_text_snippets", "extraction_confidence"}:
            merged = dict(payload.get(key) or {})
            merged.update(value)
            payload[key] = merged
            continue
        if payload.get(key) in (None, "", [], {}):
            payload[key] = value
    return AIProgrammeDraft.model_validate(payload)


def _is_missing_required_fields(draft: AIProgrammeDraft) -> List[str]:
    # The classifier only insists on a small core of fields; this check reports
    # which of those are still empty after normalization.
    missing: List[str] = []
    if not _coerce_text(draft.program_name):
        missing.append("program_name")
    if not _coerce_text(draft.funder_name):
        missing.append("funder_name")
    if not _coerce_text(draft.funding_type):
        missing.append("funding_type")
    return missing


def _normalize_draft(
    draft: AIProgrammeDraft,
    document: PageContentDocument,
    *,
    industry_taxonomy: Dict[str, List[str]],
    use_of_funds_taxonomy: Dict[str, List[str]],
    ownership_target_keywords: Dict[str, List[str]],
    entity_type_keywords: Dict[str, List[str]],
    certification_keywords: Dict[str, List[str]],
) -> AIProgrammeDraft:
    # Normalization is the last deterministic pass before a draft becomes a
    # FundingProgrammeRecord: it fills gaps, fixes types, and merges evidence.
    derived = _derive_page_evidence(document)
    document_context = _document_evidence_context(document)
    content_bundle = _document_content_annotation_bundle(document)
    payload = draft.model_dump(mode="python")
    ai_eligibility_items = _coerce_list(payload.get("raw_eligibility_data"))
    # Eligibility text is rebuilt from the page evidence so structured fields can
    # be derived consistently even when the model omits some detail.
    eligibility_text = _combine_eligibility_text(
        document,
        ai_eligibility_items or derived["raw_eligibility_data"] or [],
        [*derived["raw_terms_data"], document_context["combined_text"]] if document_context["combined_text"] else derived["raw_terms_data"],
    )
    eligibility_profile = _derive_eligibility_profile(
        eligibility_text,
        industry_taxonomy=industry_taxonomy,
        use_of_funds_taxonomy=use_of_funds_taxonomy,
        ownership_target_keywords=ownership_target_keywords,
        entity_type_keywords=entity_type_keywords,
        certification_keywords=certification_keywords,
    )
    eligibility_criteria = extract_eligibility_criteria(
        _eligibility_source_text(document, document_context, derived)
    )
    payback_profile = extract_payback_details(_payback_source_text(document, document_context, derived))
    # Source fields are anchored to the current page, not to whatever the model
    # guessed, because this function is normalizing output rather than rethinking it.
    payload["source_url"] = document.page_url
    payload["source_urls"] = [document.page_url]
    payload["source_page_title"] = _coerce_optional_text(payload.get("source_page_title")) or document.title
    payload["program_name"] = strip_leading_numbered_prefix(_coerce_optional_text(payload.get("program_name")) or "")
    if not payload["program_name"] and document.title:
        payload["program_name"] = strip_leading_numbered_prefix(document.title)
    payload["funder_name"] = _infer_funder_name(document, payload) or _coerce_optional_text(payload.get("funder_name"))
    payload["parent_programme_name"] = _coerce_optional_text(payload.get("parent_programme_name"))
    payload["page_type"] = normalize_page_type(
        payload.get("page_type")
        or _classify_enhancer_page_type(
            record_count=1,
            candidate_block_count=max(1, len(document.structured_sections) or len(document.headings) or 1),
            internal_link_count=len(document.internal_links),
            detail_link_count=len(document.discovered_links),
            application_link_count=len(document.application_links),
            document_link_count=len(document.document_links),
            text=" ".join([document.title or "", document.full_body_text or ""]),
        )
    )
    payload["page_role"] = _infer_page_role(document, payload["page_type"], payload.get("page_role"))
    payload["source_scope"] = _coerce_optional_text(payload.get("source_scope")) or _source_scope_for_page_type(payload["page_type"])
    # All enum-like fields are normalized to schema values so the downstream
    # record validator receives exactly one representation.
    payload["funding_type"] = (_coerce_enum(FundingType, payload.get("funding_type")) or FundingType.UNKNOWN).value
    payload["deadline_type"] = (_coerce_enum(DeadlineType, payload.get("deadline_type")) or DeadlineType.UNKNOWN).value
    payload["geography_scope"] = (_coerce_enum(GeographyScope, payload.get("geography_scope")) or GeographyScope.UNKNOWN).value
    payload["security_required"] = (_coerce_enum(TriState, payload.get("security_required")) or TriState.UNKNOWN).value
    payload["equity_required"] = (_coerce_enum(TriState, payload.get("equity_required")) or TriState.UNKNOWN).value
    payload["interest_type"] = (_coerce_enum(InterestType, payload.get("interest_type")) or InterestType.UNKNOWN).value
    payload["repayment_frequency"] = (
        _coerce_enum(RepaymentFrequency, payload.get("repayment_frequency")) or RepaymentFrequency.UNKNOWN
    ).value
    payload["application_channel"] = (
        _coerce_enum(ApplicationChannel, payload.get("application_channel")) or ApplicationChannel.UNKNOWN
    ).value
    # The record keeps both AI-provided and deterministic evidence lines.
    base_funding_lines = _coerce_list(payload.get("funding_lines")) or list(derived["raw_funding_offer_data"])
    payload["funding_lines"] = unique_preserve_order(
        [*base_funding_lines, *document_context["funding_lines"]]
    )
    payload["raw_eligibility_data"] = ai_eligibility_items or derived["raw_eligibility_data"]
    payload["raw_eligibility_criteria"] = _coerce_list(payload.get("raw_eligibility_criteria")) or eligibility_criteria
    payload["provinces"] = _coerce_list(payload.get("provinces"))
    payload["municipalities"] = _coerce_list(payload.get("municipalities"))
    payload["postal_code_ranges"] = _coerce_list(payload.get("postal_code_ranges"))
    payload["industries"] = _coerce_list(payload.get("industries")) or eligibility_profile["industries"]
    payload["use_of_funds"] = _coerce_list(payload.get("use_of_funds")) or eligibility_profile["use_of_funds"]
    payload["business_stage_eligibility"] = _coerce_list(payload.get("business_stage_eligibility")) or eligibility_profile["business_stage_eligibility"]
    payload["ownership_targets"] = _coerce_list(payload.get("ownership_targets")) or eligibility_profile["ownership_targets"]
    payload["entity_types_allowed"] = _coerce_list(payload.get("entity_types_allowed")) or eligibility_profile["entity_types_allowed"]
    payload["certifications_required"] = _coerce_list(payload.get("certifications_required")) or eligibility_profile["certifications_required"]
    payload["exclusions"] = _coerce_list(payload.get("exclusions"))
    payload["required_documents"] = unique_preserve_order(
        [
            *_coerce_list(payload.get("required_documents")),
            *document_context["required_documents"],
        ]
    )
    payload["related_documents"] = unique_preserve_order([*document.document_links, *_coerce_list(payload.get("related_documents"))])
    payload["notes"] = unique_preserve_order([*_coerce_list(payload.get("notes")), *document_context["notes"]])
    payload["ticket_min"] = _coerce_float(payload.get("ticket_min"))
    payload["ticket_max"] = _coerce_float(payload.get("ticket_max"))
    payload["program_budget_total"] = _coerce_float(payload.get("program_budget_total"))
    payload["funding_speed_days_min"] = _coerce_int(payload.get("funding_speed_days_min"))
    payload["funding_speed_days_max"] = _coerce_int(payload.get("funding_speed_days_max"))
    payload["turnover_min"] = _coerce_float(payload.get("turnover_min")) or eligibility_profile["turnover_min"]
    payload["turnover_max"] = _coerce_float(payload.get("turnover_max")) or eligibility_profile["turnover_max"]
    payload["years_in_business_min"] = _coerce_float(payload.get("years_in_business_min")) or eligibility_profile["years_in_business_min"]
    payload["years_in_business_max"] = _coerce_float(payload.get("years_in_business_max")) or eligibility_profile["years_in_business_max"]
    payload["employee_min"] = _coerce_int(payload.get("employee_min")) or eligibility_profile["employee_min"]
    payload["employee_max"] = _coerce_int(payload.get("employee_max")) or eligibility_profile["employee_max"]
    payload["payback_months_min"] = _coerce_int(payload.get("payback_months_min"))
    payload["payback_months_max"] = _coerce_int(payload.get("payback_months_max"))
    payload["payback_raw_text"] = _coerce_optional_text(payload.get("payback_raw_text")) or payback_profile.raw_text
    payload["payback_term_min_months"] = _coerce_int(payload.get("payback_term_min_months"))
    payload["payback_term_max_months"] = _coerce_int(payload.get("payback_term_max_months"))
    if payload["payback_term_min_months"] is None:
        payload["payback_term_min_months"] = payback_profile.term_min_months
    if payload["payback_term_max_months"] is None:
        payload["payback_term_max_months"] = payback_profile.term_max_months
    if payload["payback_months_min"] is None:
        payload["payback_months_min"] = payload["payback_term_min_months"]
    if payload["payback_months_max"] is None:
        payload["payback_months_max"] = payload["payback_term_max_months"]
    payload["payback_structure"] = _coerce_optional_text(payload.get("payback_structure")) or payback_profile.structure
    payload["grace_period_months"] = _coerce_int(payload.get("grace_period_months"))
    if payload["grace_period_months"] is None:
        payload["grace_period_months"] = payback_profile.grace_period_months
    # Payback confidence should reflect the strongest trustworthy signal from
    # either the AI output or the deterministic extractor.
    payload["payback_confidence"] = max(
        payback_profile.confidence,
        float(payload.get("payback_confidence") or 0.0),
    )
    payload["repayment_frequency"] = (
        _coerce_enum(RepaymentFrequency, payload.get("repayment_frequency"))
        or payback_profile.repayment_frequency
        or RepaymentFrequency.UNKNOWN
    ).value
    payload["application_url"] = _coerce_optional_text(payload.get("application_url"))
    payload["contact_email"] = _coerce_optional_text(payload.get("contact_email"))
    payload["contact_phone"] = _coerce_optional_text(payload.get("contact_phone"))
    base_raw_funding_offer_data = _coerce_list(payload.get("raw_funding_offer_data")) or list(derived["raw_funding_offer_data"])
    base_raw_terms_data = _coerce_list(payload.get("raw_terms_data")) or list(derived["raw_terms_data"])
    base_raw_documents_data = _coerce_list(payload.get("raw_documents_data")) or list(derived["raw_documents_data"])
    base_raw_application_data = _coerce_list(payload.get("raw_application_data")) or list(derived["raw_application_data"])
    payload["raw_funding_offer_data"] = unique_preserve_order([*base_raw_funding_offer_data, *document_context["funding_lines"]])
    payload["raw_terms_data"] = unique_preserve_order([*base_raw_terms_data, *document_context["eligibility_lines"]])
    payload["raw_documents_data"] = unique_preserve_order([*base_raw_documents_data, *document_context["evidence_lines"]])
    payload["raw_application_data"] = unique_preserve_order([*base_raw_application_data, *document_context["application_lines"]])
    # Raw snippets preserve the exact evidence fragments that justified the
    # normalized fields.
    payload["raw_text_snippets"] = {
        key: _coerce_list(value)
        for key, value in {
            **derived["raw_text_snippets"],
            **dict(payload.get("raw_text_snippets") or {}),
            "raw_eligibility_criteria": payload.get("raw_eligibility_criteria") or [],
            "payback_raw_text": [payload["payback_raw_text"]] if payload.get("payback_raw_text") else [],
            "payback_structure": [payload["payback_structure"]] if payload.get("payback_structure") else [],
            "document_evidence": document_context["evidence_lines"],
        }.items()
    }
    # Confidence values are clamped to [0, 1] so the record cannot carry invalid
    # scores into storage.
    payload["extraction_confidence"] = {
        str(key): max(0.0, min(float(value), 1.0))
        for key, value in {**derived["extraction_confidence"], **dict(payload.get("extraction_confidence") or {})}.items()
        if value is not None
    }
    if payload.get("payback_confidence") is not None:
        payload["extraction_confidence"]["payback_confidence"] = max(
            payload["extraction_confidence"].get("payback_confidence", 0.0),
            float(payload["payback_confidence"]),
        )
    if payload.get("raw_eligibility_criteria"):
        payload["extraction_confidence"]["raw_eligibility_criteria"] = max(
            payload["extraction_confidence"].get("raw_eligibility_criteria", 0.0),
            0.88,
        )
    # Approval status is sanitized to a known enum member before the final model
    # validation call.
    payload["approval_status"] = (
        _coerce_text(payload.get("approval_status")).casefold() if payload.get("approval_status") else ApprovalStatus.PENDING.value
    )
    if payload["approval_status"] not in {member.value for member in ApprovalStatus}:
        payload["approval_status"] = ApprovalStatus.PENDING.value
    # The default country remains ZA unless the model or source says otherwise.
    payload["country_code"] = _coerce_text(payload.get("country_code")) or "ZA"
    payload["status"] = _coerce_text(payload.get("status")) or "unknown"
    payload["ai_enriched"] = True
    payload["source_domain"] = document.source_domain or extract_domain(document.page_url)
    payload["program_name"] = payload["program_name"] or strip_leading_numbered_prefix(document.title or "") or (
        document.title if document.title and len(document.title.split()) <= 12 else None
    )
    payload["funder_name"] = payload["funder_name"] or _infer_funder_name(document, payload)

    # Money values are backfilled from the combined document evidence when the
    # model did not provide clear amounts.
    if not payload["ticket_min"] or not payload["ticket_max"] or not payload["program_budget_total"]:
        doc_money_min, doc_money_max, doc_currency, _snippet, _confidence = extract_money_range(
            document_context["combined_text"],
            default_currency=None,
        )
        if payload["ticket_min"] is None:
            payload["ticket_min"] = doc_money_min
        if payload["ticket_max"] is None:
            payload["ticket_max"] = doc_money_max
        if payload["program_budget_total"] is None:
            payload["program_budget_total"] = doc_money_max or doc_money_min
        if not payload.get("currency"):
            payload["currency"] = doc_currency
    # Application/contact details are filled from the linked evidence when the
    # model leaves them blank.
    if not payload["application_url"]:
        application_urls = [url for url in document_context["urls"] if any(term in url.lower() for term in ["apply", "application", "portal", "register"])]
        payload["application_url"] = application_urls[0] if application_urls else None
    if not payload["contact_email"] and document_context["emails"]:
        payload["contact_email"] = document_context["emails"][0]
    if not payload["contact_phone"] and document_context["phones"]:
        payload["contact_phone"] = document_context["phones"][0]
    payload = _merge_content_bundle_into_payload(payload, content_bundle)
    return AIProgrammeDraft.model_validate(payload)


def _draft_to_record(
    draft: AIProgrammeDraft,
    document: PageContentDocument,
    *,
    parser_version: Optional[str] = None,
    industry_taxonomy: Dict[str, List[str]],
    use_of_funds_taxonomy: Dict[str, List[str]],
    ownership_target_keywords: Dict[str, List[str]],
    entity_type_keywords: Dict[str, List[str]],
    certification_keywords: Dict[str, List[str]],
) -> FundingProgrammeRecord:
    # This is the final normalization step: it turns the draft plus supporting
    # evidence into the canonical FundingProgrammeRecord object.
    now = datetime.now(timezone.utc)
    derived = _derive_page_evidence(document)
    document_context = _document_evidence_context(document)
    content_bundle = _document_content_annotation_bundle(document)
    payload = draft.model_dump(mode="python")
    payload = _merge_content_bundle_into_payload(payload, content_bundle)
    ai_eligibility_items = _coerce_list(payload.get("raw_eligibility_data"))
    # Rebuild eligibility text from the current page so deterministic extraction
    # can supplement or override incomplete model output.
    eligibility_text = _combine_eligibility_text(
        document,
        ai_eligibility_items or derived["raw_eligibility_data"] or [],
        [*derived["raw_terms_data"], document_context["combined_text"]] if document_context["combined_text"] else derived["raw_terms_data"],
    )
    eligibility_profile = _derive_eligibility_profile(
        eligibility_text,
        industry_taxonomy=industry_taxonomy,
        use_of_funds_taxonomy=use_of_funds_taxonomy,
        ownership_target_keywords=ownership_target_keywords,
        entity_type_keywords=entity_type_keywords,
        certification_keywords=certification_keywords,
    )
    eligibility_criteria = extract_eligibility_criteria(
        _eligibility_source_text(document, document_context, derived)
    )
    payback_profile = extract_payback_details(_payback_source_text(document, document_context, derived))
    # Pull the basic schema enums out first so the rest of the field population
    # can rely on stable values.
    source_url = document.page_url
    source_domain = payload.get("source_domain") or extract_domain(source_url)
    funding_type = _coerce_enum(FundingType, payload.get("funding_type")) or FundingType.UNKNOWN
    deadline_type = _coerce_enum(DeadlineType, payload.get("deadline_type")) or DeadlineType.UNKNOWN
    geography_scope = _coerce_enum(GeographyScope, payload.get("geography_scope")) or GeographyScope.UNKNOWN
    security_required = _coerce_enum(TriState, payload.get("security_required")) or TriState.UNKNOWN
    equity_required = _coerce_enum(TriState, payload.get("equity_required")) or TriState.UNKNOWN
    interest_type = _coerce_enum(InterestType, payload.get("interest_type")) or InterestType.UNKNOWN
    repayment_frequency = _coerce_enum(RepaymentFrequency, payload.get("repayment_frequency")) or RepaymentFrequency.UNKNOWN
    application_channel = _coerce_enum(ApplicationChannel, payload.get("application_channel")) or ApplicationChannel.UNKNOWN
    approval_status = _coerce_enum(ApprovalStatus, payload.get("approval_status")) or ApprovalStatus.PENDING

    # Lists are merged from AI output, deterministic extraction, and linked
    # evidence so the final record keeps the richest available source text.
    raw_eligibility_data = ai_eligibility_items or eligibility_profile["raw_eligibility_data"] or derived["raw_eligibility_data"]
    raw_eligibility_criteria = _coerce_list(payload.get("raw_eligibility_criteria")) or eligibility_criteria
    base_funding_lines = _coerce_list(payload.get("funding_lines")) or list(derived["raw_funding_offer_data"])
    funding_lines = unique_preserve_order([*base_funding_lines, *document_context["funding_lines"]])
    provinces = _coerce_list(payload.get("provinces"))
    municipalities = _coerce_list(payload.get("municipalities"))
    postal_code_ranges = _coerce_list(payload.get("postal_code_ranges"))
    industries = _coerce_list(payload.get("industries")) or eligibility_profile["industries"]
    use_of_funds = _coerce_list(payload.get("use_of_funds")) or eligibility_profile["use_of_funds"]
    business_stage_eligibility = _coerce_list(payload.get("business_stage_eligibility")) or eligibility_profile["business_stage_eligibility"]
    ownership_targets = _coerce_list(payload.get("ownership_targets")) or eligibility_profile["ownership_targets"]
    entity_types_allowed = _coerce_list(payload.get("entity_types_allowed")) or eligibility_profile["entity_types_allowed"]
    certifications_required = _coerce_list(payload.get("certifications_required")) or eligibility_profile["certifications_required"]
    exclusions = _coerce_list(payload.get("exclusions"))
    required_documents = unique_preserve_order([*_coerce_list(payload.get("required_documents")), *document_context["required_documents"]])
    related_documents = unique_preserve_order([*document.document_links, *_coerce_list(payload.get("related_documents"))])
    notes = unique_preserve_order([*_coerce_list(payload.get("notes")), *document_context["notes"]])
    source_urls = [source_url]

    # Amount fields are normalized before any backfill logic runs.
    ticket_min = _coerce_float(payload.get("ticket_min"))
    ticket_max = _coerce_float(payload.get("ticket_max"))
    if ticket_min is not None and ticket_max is not None and ticket_min > ticket_max:
        ticket_min, ticket_max = ticket_max, ticket_min

    program_budget_total = _coerce_float(payload.get("program_budget_total"))
    funding_speed_days_min = _coerce_int(payload.get("funding_speed_days_min"))
    funding_speed_days_max = _coerce_int(payload.get("funding_speed_days_max"))
    turnover_min = _coerce_float(payload.get("turnover_min")) or eligibility_profile["turnover_min"]
    turnover_max = _coerce_float(payload.get("turnover_max")) or eligibility_profile["turnover_max"]
    years_in_business_min = _coerce_float(payload.get("years_in_business_min")) or eligibility_profile["years_in_business_min"]
    years_in_business_max = _coerce_float(payload.get("years_in_business_max")) or eligibility_profile["years_in_business_max"]
    employee_min = _coerce_int(payload.get("employee_min")) or eligibility_profile["employee_min"]
    employee_max = _coerce_int(payload.get("employee_max")) or eligibility_profile["employee_max"]
    # Repayment fields are populated from the model first, then from the
    # deterministic repayment extractor where the model left gaps.
    payback_months_min = _coerce_int(payload.get("payback_months_min"))
    payback_months_max = _coerce_int(payload.get("payback_months_max"))
    payback_raw_text = _coerce_optional_text(payload.get("payback_raw_text")) or payback_profile.raw_text
    payback_term_min_months = _coerce_int(payload.get("payback_term_min_months"))
    payback_term_max_months = _coerce_int(payload.get("payback_term_max_months"))
    if payback_term_min_months is None:
        payback_term_min_months = payback_profile.term_min_months
    if payback_term_max_months is None:
        payback_term_max_months = payback_profile.term_max_months
    if payback_months_min is None:
        payback_months_min = payback_term_min_months
    if payback_months_max is None:
        payback_months_max = payback_term_max_months
    payback_structure = _coerce_optional_text(payload.get("payback_structure")) or payback_profile.structure
    grace_period_months = _coerce_int(payload.get("grace_period_months"))
    if grace_period_months is None:
        grace_period_months = payback_profile.grace_period_months
    payback_confidence = max(payback_profile.confidence, float(payload.get("payback_confidence") or 0.0))
    repayment_frequency = _coerce_enum(RepaymentFrequency, payload.get("repayment_frequency")) or payback_profile.repayment_frequency or RepaymentFrequency.UNKNOWN
    currency = _coerce_text(payload.get("currency")) or None
    if not currency:
        currency = infer_default_currency(
            " ".join([document.full_body_text or "", document_context["combined_text"], document.title or ""]),
            source_domain=source_domain or "",
        )
    if not currency and any(text for text in (ticket_min, ticket_max, program_budget_total) if text is not None):
        currency = "ZAR" if (source_domain or "").endswith(".za") else None

    # Deadline parsing is recomputed from the full page and document evidence so
    # the record does not depend entirely on the model's interpretation.
    deadline_info = parse_deadline_info(
        " ".join(
            [
                document.title or "",
                document.full_body_text or "",
                document_context["combined_text"],
                " ".join(section.content for section in document.structured_sections),
            ]
        )
    )
    deadline_date = payload.get("deadline_date")
    if isinstance(deadline_date, str):
        try:
            deadline_date = datetime.fromisoformat(deadline_date).date()
        except ValueError:
            deadline_date = None
    if deadline_date is None and deadline_info.get("deadline_date"):
        deadline_date = deadline_info.get("deadline_date")

    # Keep the exact supporting fragments around for debugging and later review.
    raw_text_snippets = {
        key: _coerce_list(value)
        for key, value in {
            **derived["raw_text_snippets"],
            **dict(payload.get("raw_text_snippets") or {}),
            "raw_eligibility_criteria": raw_eligibility_criteria,
            "payback_raw_text": [payback_raw_text] if payback_raw_text else [],
            "payback_structure": [payback_structure] if payback_structure else [],
            "document_evidence": document_context["evidence_lines"],
        }.items()
    }

    if not ticket_min or not ticket_max or not program_budget_total:
        doc_money_min, doc_money_max, doc_currency, _snippet, _confidence = extract_money_range(document_context["combined_text"], default_currency=None)
        if ticket_min is None:
            ticket_min = doc_money_min
        if ticket_max is None:
            ticket_max = doc_money_max
        if program_budget_total is None:
            program_budget_total = doc_money_max or doc_money_min
        if not currency:
            currency = doc_currency

    if not payload.get("application_url"):
        application_urls = [url for url in document_context["urls"] if any(term in url.lower() for term in ["apply", "application", "portal", "register"])]
    else:
        application_urls = []
    application_url = _coerce_optional_text(payload.get("application_url")) or (application_urls[0] if application_urls else None)
    contact_email = _coerce_optional_text(payload.get("contact_email")) or (document_context["emails"][0] if document_context["emails"] else None)
    contact_phone = _coerce_optional_text(payload.get("contact_phone")) or (document_context["phones"][0] if document_context["phones"] else None)

    # Confidence scores are merged from all sources and clamped to a valid range.
    extraction_confidence = {
        str(key): max(0.0, min(float(value), 1.0))
        for key, value in {**derived["extraction_confidence"], **dict(payload.get("extraction_confidence") or {})}.items()
        if value is not None
    }
    if payback_confidence is not None:
        extraction_confidence["payback_confidence"] = max(
            extraction_confidence.get("payback_confidence", 0.0),
            float(payback_confidence),
        )
    if raw_eligibility_criteria:
        extraction_confidence["raw_eligibility_criteria"] = max(
            extraction_confidence.get("raw_eligibility_criteria", 0.0),
            0.88,
        )
    if not extraction_confidence and _coerce_text(payload.get("program_name")):
        extraction_confidence["program_name"] = 0.65

    # Build the final record with every normalized and backfilled field in place.
    record = FundingProgrammeRecord(
        program_name=_coerce_optional_text(payload.get("program_name")) or None,
        funder_name=_coerce_optional_text(payload.get("funder_name")) or None,
        parent_programme_name=_coerce_optional_text(payload.get("parent_programme_name")) or None,
        source_url=source_url,
        source_urls=source_urls,
        source_domain=source_domain,
        source_page_title=_coerce_optional_text(payload.get("source_page_title")) or document.title,
        scraped_at=now,
        created_at=now,
        updated_at=now,
        last_scraped_at=now,
        raw_eligibility_data=raw_eligibility_data,
        raw_eligibility_criteria=raw_eligibility_criteria,
        raw_funding_offer_data=unique_preserve_order([*derived["raw_funding_offer_data"], *document_context["funding_lines"]]),
        raw_terms_data=unique_preserve_order([*derived["raw_terms_data"], *document_context["eligibility_lines"]]),
        raw_documents_data=unique_preserve_order([*derived["raw_documents_data"], *document_context["evidence_lines"]]),
        raw_application_data=unique_preserve_order([*derived["raw_application_data"], *document_context["application_lines"]]),
        funding_type=funding_type,
        funding_lines=funding_lines,
        ticket_min=ticket_min,
        ticket_max=ticket_max,
        currency=currency,
        program_budget_total=program_budget_total,
        deadline_type=_coerce_enum(DeadlineType, payload.get("deadline_type")) or (
            _coerce_enum(DeadlineType, deadline_info.get("deadline_type")) or DeadlineType.UNKNOWN
        ),
        deadline_date=deadline_date,
        funding_speed_days_min=funding_speed_days_min,
        funding_speed_days_max=funding_speed_days_max,
        geography_scope=geography_scope,
        provinces=provinces,
        municipalities=municipalities,
        postal_code_ranges=postal_code_ranges,
        industries=industries,
        use_of_funds=use_of_funds,
        business_stage_eligibility=business_stage_eligibility,
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
        payback_raw_text=payback_raw_text,
        payback_term_min_months=payback_term_min_months,
        payback_term_max_months=payback_term_max_months,
        payback_structure=payback_structure,
        grace_period_months=grace_period_months,
        interest_type=interest_type,
        repayment_frequency=repayment_frequency,
        payback_confidence=payback_confidence,
        exclusions=exclusions,
        required_documents=required_documents,
        application_channel=application_channel,
        application_url=application_url,
        contact_email=contact_email,
        contact_phone=contact_phone,
        raw_text_snippets=raw_text_snippets,
        extraction_confidence=extraction_confidence,
        evidence_by_field=dict(payload.get("evidence_by_field") or {}),
        field_confidence=dict(payload.get("field_confidence") or extraction_confidence),
        related_documents=related_documents,
        parser_version=parser_version or SCRAPER_VERSION,
        ai_enriched=True,
        approval_status=approval_status,
        country_code=_coerce_text(payload.get("country_code")) or "ZA",
        status=_coerce_enum(ProgrammeStatus, payload.get("status")) or ProgrammeStatus.UNKNOWN,
        notes=notes or [f"AI classification applied to {document.page_url}"],
        page_type=normalize_page_type(payload.get("page_type")),
        page_role=normalize_page_role(payload.get("page_role")),
        source_scope=_coerce_optional_text(payload.get("source_scope")) or _source_scope_for_page_type(normalize_page_type(payload.get("page_type"))),
    )
    record = FundingProgrammeRecord.model_validate(record.model_dump(mode="python"))
    record = _validate_field_evidence(record, content_bundle)
    record = _apply_field_confidence_rules(record, content_bundle)
    record = _validate_post_ai_money_fields(record, document)
    record = _apply_record_review_flags(record)
    return FundingProgrammeRecord.model_validate(record.model_dump(mode="python"))


class AIClassifier:
    """Classify cleaned page content into the funding-programme schema."""

    def __init__(self, config: Dict[str, Any], storage: Optional[Any] = None) -> None:
        # Configuration is split between runtime flags, model/provider selection,
        # and optional extraction limits for linked support documents.
        self.config = config
        self.storage = storage
        self.disable_remote_ai = bool(config.get("disableRemoteAi") or config.get("offline"))
        self.require_remote_ai = bool(config.get("requireRemoteAi") or config.get("require_remote_ai"))
        self.ai_provider = (config.get("aiProvider") or os.getenv("AI_PROVIDER") or "openai").strip().lower()
        self.model = config.get("aiModel") or os.getenv("SCRAPER_AI_MODEL") or "gpt-4o-mini"
        self.document_ai_max_documents_per_page = int(config.get("documentAiMaxDocumentsPerPage") or config.get("document_ai_max_documents_per_page") or 4)
        self.document_ai_max_extracted_chars = int(config.get("documentAiMaxExtractedChars") or config.get("document_ai_max_extracted_chars") or 5000)
        self.document_ai_timeout_seconds = float(config.get("documentAiTimeoutSeconds") or config.get("document_ai_timeout_seconds") or 45)
        self.document_ai_skip_content_types = {
            clean_text(value).lower()
            for value in (config.get("documentAiSkipContentTypes") or config.get("document_ai_skip_content_types") or [])
            if clean_text(value)
        }
        self.document_ai_skip_url_terms = [
            clean_text(value).lower()
            for value in (config.get("documentAiSkipUrlTerms") or config.get("document_ai_skip_url_terms") or [])
            if clean_text(value)
        ]
        if self.disable_remote_ai:
            self.api_key = None
        else:
            self.api_key = (
                config.get("openaiKey")
                or os.getenv("OPENAI_API_KEY")
                if self.ai_provider == "openai"
                else config.get("groqKey") or os.getenv("GROQ_API_KEY")
            )
        self.min_confidence = float(config.get("aiMinConfidence", 0.55))
        self.max_retries = int(config.get("aiMaxRetries", 2))
        self.industry_taxonomy = _as_taxonomy(config.get("industry_taxonomy"))
        self.use_of_funds_taxonomy = _as_taxonomy(config.get("use_of_funds_taxonomy"))
        self.ownership_target_keywords = _as_taxonomy(config.get("ownership_target_keywords"))
        self.entity_type_keywords = _as_taxonomy(config.get("entity_type_keywords"))
        self.certification_keywords = _as_taxonomy(config.get("certification_keywords"))

    def _document_headers(self) -> Dict[str, str]:
        # Remote document requests use a simple browser-like header set.
        return {
            "User-Agent": "Mozilla/5.0 (compatible; Scrapper/1.0; +https://example.org)",
            "Accept": "*/*",
        }

    def _artifact_slug(self, document: PageContentDocument) -> str:
        # Artifact filenames are derived from the URL so each page gets a stable
        # storage key.
        return re.sub(r"[^a-zA-Z0-9]+", "-", document.page_url.lower()).strip("-")[:120] or "page"

    def _write_artifact(self, kind: str, document: PageContentDocument, payload: Any) -> None:
        # If storage is configured, persist the prompt or response for debugging.
        if not self.storage:
            return
        method_name = {
            "input": "write_ai_input",
            "output": "write_ai_output",
            "error": "write_ai_error",
        }.get(kind)
        if method_name and hasattr(self.storage, method_name):
            try:
                getattr(self.storage, method_name)(document, payload)
            except Exception:
                logger.debug("ai_artifact_write_failed", kind=kind, page_url=document.page_url)

    def _should_skip_document_source(self, url: str, content_type: Optional[str]) -> bool:
        # Some document types and URL patterns are intentionally skipped because
        # they are noisy, unsupported, or not useful as AI evidence.
        lowered_url = (url or "").lower()
        lowered_content_type = clean_text(content_type or "").lower()
        if lowered_content_type and any(lowered_content_type.startswith(item) for item in self.document_ai_skip_content_types):
            return True
        if any(term and term in lowered_url for term in self.document_ai_skip_url_terms):
            return True
        return False

    def _read_remote_document(self, url: str) -> tuple[Optional[bytes], Optional[str], List[str]]:
        # Linked support files are fetched over HTTP so they can be read locally
        # and summarized into evidence snapshots.
        with httpx.Client(timeout=self.document_ai_timeout_seconds, follow_redirects=True) as client:
            response = client.get(url, headers=self._document_headers())
            response.raise_for_status()
            return response.content, response.headers.get("content-type"), []

    def _build_document_summary_prompt(
        self,
        url: str,
        kind: str,
        content_type: Optional[str],
        source_kind: str,
        *,
        programme_context: Optional[Dict[str, str]] = None,
    ) -> str:
        # The document summary prompt tells the model to summarize support files
        # without inventing facts or overriding the page itself.
        programme_context = programme_context or {}
        return (
            "You are reading a funding-programme support document.\n"
            "Return JSON only with keys: summary, key_points, confidence, notes.\n"
            "Keep the summary short and factual.\n"
            "Extract only evidence visible in the supplied document text or image.\n"
            "Do not invent missing details.\n"
            "Use the programme context only to interpret which programme the document belongs to; do not import facts that are not present in the document.\n"
            f"Programme name: {programme_context.get('programme_name') or 'unknown'}\n"
            f"Programme page title: {programme_context.get('page_title') or 'unknown'}\n"
            f"Programme page URL: {programme_context.get('page_url') or 'unknown'}\n"
            f"Programme source domain: {programme_context.get('source_domain') or 'unknown'}\n"
            f"Document URL: {url}\n"
            f"Document kind: {kind}\n"
            f"Content type: {content_type or 'unknown'}\n"
            f"Reading mode: {source_kind}\n"
        )

    def _parse_document_summary_response(self, raw: str) -> Dict[str, Any]:
        # The summary response is parsed as strict JSON, with a small fallback for
        # models that wrap the object in extra text.
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", raw)
            if not match:
                raise
            payload = json.loads(match.group(0))
        if not isinstance(payload, dict):
            raise ValueError("Document summary response must be a JSON object.")
        return payload

    def _summarize_document_with_openai(
        self,
        *,
        document_url: str,
        kind: str,
        content_type: Optional[str],
        extracted_text: str = "",
        raw_bytes: Optional[bytes] = None,
        programme_context: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        # OpenAI-only summary mode is used when the linked document itself needs a
        # compact evidence summary before the classifier sees it.
        if not self.api_key or self.ai_provider != "openai":
            return {}

        client = OpenAI(api_key=self.api_key)
        prompt = self._build_document_summary_prompt(
            document_url,
            kind,
            content_type,
            "openai",
            programme_context=programme_context,
        )
        content: List[Dict[str, Any]] = [{"type": "input_text", "text": "Read this document and extract the useful programme evidence."}]

        if extracted_text:
            # If text extraction worked, send the cleaned text instead of the raw
            # binary file so the response stays focused.
            content.append(
                {
                    "type": "input_text",
                    "text": compact_document_text(extracted_text, max_chars=self.document_ai_max_extracted_chars),
                }
            )
        elif kind == "image":
            # Images are sent directly when no text layer is available.
            content.append({"type": "input_image", "image_url": document_url, "detail": "high"})
        elif raw_bytes:
            # Binary documents are embedded as a file payload when supported.
            content.append(
                {
                    "type": "input_file",
                    "file_data": base64.b64encode(raw_bytes).decode("ascii"),
                    "filename": document_url.rsplit("/", 1)[-1] or "document",
                    "detail": "high",
                }
            )
        else:
            content.append({"type": "input_text", "text": "No machine-readable text was extracted. Read the document metadata and any visible text carefully."})

        # The response is forced to JSON so the summary payload can be parsed
        # deterministically.
        response = client.responses.create(
            model=self.model,
            instructions=prompt,
            input=[{"role": "user", "content": content}],
            temperature=0.1,
            max_output_tokens=500,
            text={"format": {"type": "json_object"}},
        )
        output_text = getattr(response, "output_text", "") or ""
        if not output_text:
            return {}
        return self._parse_document_summary_response(output_text)

    def _build_document_evidence_snapshot(
        self,
        *,
        document_url: str,
        content_type: Optional[str],
        raw_bytes: Optional[bytes],
        source_method: str,
        existing_text: str = "",
        programme_context: Optional[Dict[str, str]] = None,
    ) -> Optional[DocumentEvidenceSnapshot]:
        # Each linked file is converted into a compact evidence snapshot that
        # carries both a summary and the cleaned text that was actually read.
        if self._should_skip_document_source(document_url, content_type):
            return None
        kind = infer_document_kind(document_url, content_type)
        if kind == "unsupported":
            return None

        if existing_text:
            # When the page itself already contains text, use it directly instead
            # of fetching the source again.
            text = compact_document_text(existing_text, max_chars=self.document_ai_max_extracted_chars)
            notes = []
        else:
            # Otherwise read the remote file and run local text extraction.
            local_result = extract_local_document_text(raw_bytes or b"", document_url, content_type)
            text = compact_document_text(local_result.text, max_chars=self.document_ai_max_extracted_chars)
            notes = list(local_result.notes)
        summary_payload: Dict[str, Any] = {}
        if self.api_key and self.ai_provider == "openai":
            try:
                # A second AI pass can summarize the file when OpenAI is the
                # configured provider.
                summary_payload = self._summarize_document_with_openai(
                    document_url=document_url,
                    kind=kind,
                    content_type=content_type,
                    extracted_text=text,
                    raw_bytes=raw_bytes if not text and kind != "image" else None,
                    programme_context=programme_context,
                )
            except Exception as exc:
                notes.append(f"OpenAI document read failed: {exc}")

        summary = clean_text(str(summary_payload.get("summary") or "")) or None
        key_points = summary_payload.get("key_points") or []
        if isinstance(key_points, str):
            key_points = [key_points]
        if not summary and text:
            summary = compact_document_text(text, max_chars=600)
        if not key_points and text:
            key_points = sentence_chunks(text)[:5]
        extracted_text = text or None
        if summary_payload.get("notes"):
            notes.extend([clean_text(str(item)) for item in summary_payload.get("notes") or [] if clean_text(str(item))])
        # The final snapshot keeps the summary, short key points, cleaned text,
        # and any notes about how the file was processed.
        return DocumentEvidenceSnapshot(
            document_url=document_url,
            document_kind=kind,
            content_type=content_type,
            source_method=source_method,
            summary=summary,
            key_points=[clean_text(str(item)) for item in key_points if clean_text(str(item))],
            extracted_text=extracted_text,
            notes=notes,
        )

    def _prepare_document_context(self, document: PageContentDocument) -> PageContentDocument:
        # This enriches the main page with linked PDFs/docs/images so the model
        # can use supporting evidence without replacing the page's own facts.
        if document.document_evidence:
            return document

        programme_context = {
            "programme_name": clean_text(document.title or document.page_title or "") or "",
            "page_title": clean_text(document.page_title or document.title or "") or "",
            "page_url": document.page_url or "",
            "source_domain": document.source_domain or extract_domain(document.page_url) or "",
        }
        context_text = " ".join(
            [
                programme_context["programme_name"],
                programme_context["page_title"],
                document.page_url or "",
                document.source_domain or "",
                " ".join(document.headings[:8]),
            ]
        )

        candidate_urls: List[str] = []
        source_domain = extract_domain(document.page_url)
        source_kind = infer_document_kind(document.page_url, document.source_content_type)
        if source_kind in {"pdf", "docx", "xlsx", "image"}:
            candidate_urls.append(document.page_url)

        for link in document.document_links[: self.document_ai_max_documents_per_page]:
            if extract_domain(link) != source_domain:
                continue
            if not document_link_matches_context(link, context_text=context_text):
                continue
            if link not in candidate_urls:
                candidate_urls.append(link)

        evidence: List[DocumentEvidenceSnapshot] = []
        for document_url in candidate_urls[: self.document_ai_max_documents_per_page]:
            if self._should_skip_document_source(document_url, None):
                continue
            try:
                if document_url == document.page_url and source_kind in {"pdf", "docx", "xlsx"} and document.full_body_text:
                    snapshot = self._build_document_evidence_snapshot(
                        document_url=document_url,
                        content_type=document.source_content_type,
                        raw_bytes=None,
                        source_method="page",
                        existing_text=document.full_body_text,
                        programme_context=programme_context,
                    )
                    if snapshot:
                        evidence.append(snapshot)
                    continue
                raw_bytes, content_type, _notes = self._read_remote_document(document_url)
            except Exception as exc:
                logger.debug("document_read_failed", page_url=document.page_url, document_url=document_url, error=str(exc))
                continue
            snapshot = self._build_document_evidence_snapshot(
                document_url=document_url,
                content_type=content_type,
                raw_bytes=raw_bytes,
                source_method="page" if document_url == document.page_url else "linked_document",
                existing_text=document.full_body_text if document_url == document.page_url and source_kind in {"pdf", "docx", "xlsx"} else "",
                programme_context=programme_context,
            )
            if snapshot:
                evidence.append(snapshot)

        document.document_evidence = evidence
        return document

    def _build_system_prompt(self) -> str:
        # The system prompt defines the strict contract: JSON only, conservative
        # extraction, and explicit rules for page classification and repayment fields.
        return (
            "You are a strict JSON classifier for funding programme pages.\n"
            "Return JSON only. Do not add markdown, comments, or explanations.\n"
            "Use only evidence present in the supplied page content.\n"
            "Document evidence from linked or source files is supplemental: use it to fill gaps, but do not override clear page evidence unless the document is the source page itself.\n"
            "Existing extracted values are included in current_records; treat them as the starting record state and preserve any populated field unless the page evidence clearly supports a correction.\n"
            "Do not invent missing values. If a value is absent, use null, an empty array, or Unknown.\n"
            "Prefer exact wording for eligibility and requirements.\n"
            "Scan repayment wording carefully. Look for repayment, repay, repayable, pay back, payback, loan term, tenor, tenure, duration, period, months, years, instalments, installments, moratorium, grace period, deferred payment, repayment holiday, bullet repayment, monthly repayments, and quarterly repayments.\n"
            "Preserve the original repayment wording in payback_raw_text, convert years to months where possible, keep payback_term_min_months and payback_term_max_months aligned with the wording, and summarize the structure in payback_structure.\n"
            "If the page says up to a term, keep only payback_term_max_months. If it says between two periods, capture both bounds. If no repayment information is present, return null payback fields, repayment_frequency as Unknown, and payback_confidence as 0.\n"
            "Normalize money values to plain numbers only when the amount is directly attached to currency or funding context. Never extract standalone numbers, phone numbers, years, tender numbers, dates, postal codes, percentages, or TRL ranges as ticket_min or ticket_max.\n"
            "First classify page_type as exactly one of: funding_programme, funding_listing, support_programme, technology_station, open_call, tender_procurement, news_article, generic_content.\n"
            "Also classify page_role separately as one of: overview, eligibility, application, checklist, funding_detail, listing, procurement_notice, news_article, about_contact, support_detail, technology_station, generic.\n"
            "Set page_decision to funding_program only for page_type funding_programme, funding_listing, or open_call with fundable financial or capital support. Otherwise set page_decision to not_funding_program and return records as an empty array.\n"
            "Use tender_procurement for tender, bid, RFQ, RFP, procurement, supply-chain, and appointment notices even when they mention funding.\n"
            "Use news_article for news, press releases, media releases, stories, announcements, and articles that are not the canonical programme page.\n"
            "Use technology_station for technical assistance or technology station pages without explicit fundable support.\n"
            "Use support_programme for mentorship, training, incubation, acceleration, advisory, or technical support without explicit fundable support.\n"
            "Before extracting records, classify each candidate block or heading-based section independently. If one page contains multiple distinct fundable programme headings, return one record per programme section. If a section only supports a programme described elsewhere on the page, do not create a duplicate record; include that evidence in the relevant record.\n"
            "A child or sub-programme is still a real programme record if it has its own distinct name, rules, or funding terms.\n"
            "Do not collapse sibling programmes just because they share a parent fund or similar numbered naming.\n"
            "When raw_eligibility_data or raw_eligibility_criteria is present, extract it into industries, use_of_funds, business_stage_eligibility, turnover_min/max, years_in_business_min/max, employee_min/max, ownership_targets, entity_types_allowed, and certifications_required whenever supported.\n"
            "Prefer short list values for those fields and do not leave them blank if the eligibility text clearly supports them.\n"
            "Always capture eligibility statements as a clean list in raw_eligibility_criteria, using headings such as Eligibility Criteria, Qualifying Criteria, Who can apply, Applicant Requirements, Funding Requirements, Minimum Requirements, Compliance Requirements, Mandatory Requirements, Requirements, Criteria, Conditions, Terms and Conditions, Selection Criteria, Application Criteria, Funding Criteria, and Investment Criteria.\n"
            "If the page is ambiguous, use unclear and keep records empty unless the page clearly supports a programme record.\n"
            "Return an object with keys: page_decision, page_type, page_decision_confidence, records, and notes.\n"
            "records must be an array of 0 or more programme objects.\n"
            "Set source_url and source_urls to the current page URL only unless the page clearly references another canonical source page.\n"
            "Each programme object may contain only funding-programme fields and must omit technical DB fields such as program_id, id, created_at, updated_at, scraped_at, source_domain, parser_version, approval_status, and ai_enriched.\n"
            "Allowed business fields include program_name, funder_name, source_url, source_urls, source_page_title, page_type, page_role, source_scope, raw_eligibility_data, raw_eligibility_criteria, raw_funding_offer_data, raw_terms_data, raw_documents_data, raw_application_data, funding_type, funding_lines, ticket_min, ticket_max, currency, program_budget_total, deadline_type, deadline_date, funding_speed_days_min, funding_speed_days_max, geography_scope, provinces, municipalities, postal_code_ranges, industries, use_of_funds, business_stage_eligibility, turnover_min, turnover_max, years_in_business_min, years_in_business_max, employee_min, employee_max, ownership_targets, entity_types_allowed, certifications_required, security_required, equity_required, payback_months_min, payback_months_max, payback_raw_text, payback_term_min_months, payback_term_max_months, payback_structure, grace_period_months, payback_confidence, interest_type, repayment_frequency, exclusions, required_documents, application_channel, application_url, contact_email, contact_phone, raw_text_snippets, extraction_confidence, related_documents, notes, status, country_code, and parent_programme_name."
        )

    def _build_user_prompt(
        self,
        document: PageContentDocument,
        *,
        record_snapshots: Optional[Sequence[PageAIRecordSnapshot | Dict[str, Any] | Any]] = None,
    ) -> str:
        # The user prompt sends a compact JSON payload so the model sees only
        # the fields relevant to the current page and any current record state.
        payload = _build_context_prompt_payload(document, record_snapshots=record_snapshots)
        prompt = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        if len(prompt) > MAX_PROMPT_CHARS:
            prompt = prompt[: MAX_PROMPT_CHARS - 3] + "..."
        return (
            "Map the page content into zero or more funding-programme records.\n"
            "Classify page_type first, then classify each candidate block/heading section independently.\n"
            "If the page is not persistable funding content, return {\"page_decision\": \"not_funding_program\", \"page_type\": \"...\", \"records\": [], \"notes\": [...]}.\n"
            "If the page is a sub-programme with its own name and terms, keep it as an independent programme record.\n"
            "If a listing contains multiple fundable programme sections, return multiple records, one per section.\n"
            "Use the values already present under current_records as the baseline record state and only change them when the page evidence supports a better value.\n"
            "Treat document evidence as supporting context; do not replace clear page facts unless the document is the page itself.\n"
            "Keep all extracted wording close to the source text.\n"
            "Return only JSON.\n\n"
            f"PAGE CONTENT:\n{prompt}"
        )

    def _build_missing_fields_prompt(
        self,
        document: PageContentDocument,
        missing_fields: Sequence[str],
        *,
        record_snapshots: Optional[Sequence[PageAIRecordSnapshot | Dict[str, Any] | Any]] = None,
    ) -> str:
        # When the model omits required fields, this follow-up prompt narrows the
        # correction request to only the missing pieces.
        payload = _build_context_prompt_payload(document, record_snapshots=record_snapshots)
        payload["missing_fields"] = list(missing_fields)
        prompt = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        if len(prompt) > MAX_PROMPT_CHARS:
            prompt = prompt[: MAX_PROMPT_CHARS - 3] + "..."
        return (
            "The previous JSON response was missing required fields.\n"
            "Return JSON only and fill the missing fields only when supported by the page.\n"
            f"Missing fields: {', '.join(missing_fields)}\n\n"
            f"PAGE CONTENT:\n{prompt}"
        )

    def _build_decision_reprompt(
        self,
        document: PageContentDocument,
        *,
        record_snapshots: Optional[Sequence[PageAIRecordSnapshot | Dict[str, Any] | Any]] = None,
    ) -> str:
        # If the classifier is uncertain, this prompt asks only for the page
        # decision before trying to fill record fields again.
        payload = _build_context_prompt_payload(document, record_snapshots=record_snapshots)
        prompt = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        if len(prompt) > MAX_PROMPT_CHARS:
            prompt = prompt[: MAX_PROMPT_CHARS - 3] + "..."
        return (
            "Classify this page into the exact page_type vocabulary first.\n"
            "If it is not persistable funding content, return page_decision as not_funding_program, page_type, and records as an empty array.\n"
            "If it is persistable, return page_decision as funding_program, page_type, and include only records directly supported by the page.\n"
            "Do not guess.\n\n"
            f"PAGE CONTENT:\n{prompt}"
        )

    def _merge_record_payload(self, record: FundingProgrammeRecord) -> Dict[str, Any]:
        # Merge decisions need a concise record view, so this strips each record
        # down to the fields that matter for deduplication.
        parsed_url = urlparse(record.source_url or "")
        source_path = parsed_url.path or ""
        return {
            "program_name": record.program_name,
            "funder_name": record.funder_name,
            "parent_programme_name": record.parent_programme_name,
            "source_url": record.source_url,
            "source_urls": list(record.source_urls),
            "source_path": source_path,
            "source_page_title": record.source_page_title,
            "page_type": record.page_type,
            "page_role": record.page_role,
            "source_scope": record.source_scope,
            "canonical_group_key": _record_canonical_group_key(record),
            "funding_type": record.funding_type.value if hasattr(record.funding_type, "value") else record.funding_type,
            "funding_lines": list(record.funding_lines),
            "raw_eligibility_data": list(record.raw_eligibility_data or []),
            "raw_eligibility_criteria": list(record.raw_eligibility_criteria),
            "raw_funding_offer_data": list(record.raw_funding_offer_data),
            "raw_terms_data": list(record.raw_terms_data),
            "raw_documents_data": list(record.raw_documents_data),
            "raw_application_data": list(record.raw_application_data),
            "payback_raw_text": record.payback_raw_text,
            "payback_term_min_months": record.payback_term_min_months,
            "payback_term_max_months": record.payback_term_max_months,
            "payback_structure": record.payback_structure,
            "grace_period_months": record.grace_period_months,
            "payback_confidence": record.payback_confidence,
            "application_url": record.application_url,
            "contact_email": record.contact_email,
            "contact_phone": record.contact_phone,
            "related_documents": list(record.related_documents),
            "notes": list(record.notes),
        }

    def _build_merge_decision_prompt(self, left: FundingProgrammeRecord, right: FundingProgrammeRecord) -> str:
        # The merge prompt compares two compact record payloads and asks the model
        # to decide whether they describe the same underlying programme.
        payload = {
            "left_record": self._merge_record_payload(left),
            "right_record": self._merge_record_payload(right),
        }
        prompt = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        if len(prompt) > MAX_PROMPT_CHARS:
            prompt = prompt[: MAX_PROMPT_CHARS - 3] + "..."
        return (
            "Decide whether these two records refer to the same underlying funding programme.\n"
            "Return JSON only.\n"
            "Use merge_decision = merge only when at least one of these is clearly true:\n"
            "1) the canonical source_url or source_path is the same page, or\n"
            "2) the records clearly describe the same child page under the same parent programme context.\n"
            "If the URLs differ and the parent programme context does not clearly match, use merge_decision = separate.\n"
            "Sibling programmes under different parent funds must stay separate.\n"
            "Same program_name alone is never enough to merge.\n"
            "When in doubt, use merge_decision = separate rather than unclear.\n"
            "Return confidence as a number from 0 to 1 and a short reason.\n\n"
            f"RECORDS:\n{prompt}"
        )

    def _normalize_merge_decision(self, value: Any) -> str:
        # Merge decisions can come back in several phrasing variants, so they are
        # normalized before the confidence threshold is applied.
        text = _coerce_text(value).casefold().replace("-", "_").replace(" ", "_")
        if text in {"merge", "same", "same_program", "same_programme", "duplicate", "duplicates"}:
            return "merge"
        if text in {"separate", "different", "different_program", "different_programme", "no_merge"}:
            return "separate"
        return "unclear"

    def score_duplicate_records(self, left: FundingProgrammeRecord, right: FundingProgrammeRecord) -> Dict[str, Any]:
        reasons: List[str] = []
        score = 0
        if left.source_domain != right.source_domain:
            return {"decision": "separate", "score": 0, "reasons": ["different_source_domain"]}

        left_key = _record_canonical_group_key(left)
        right_key = _record_canonical_group_key(right)
        if left_key == right_key:
            score += 40
            reasons.append("same_canonical_group_key")

        left_name = clean_text(left.program_name or "").casefold()
        right_name = clean_text(right.program_name or "").casefold()
        left_funder = clean_text(left.funder_name or "").casefold()
        right_funder = clean_text(right.funder_name or "").casefold()
        left_parent = clean_text(left.parent_programme_name or "").casefold()
        right_parent = clean_text(right.parent_programme_name or "").casefold()
        if left_name and right_name and left_name == right_name:
            score += 18
            reasons.append("same_program_name")
        if left_funder and right_funder and left_funder == right_funder:
            score += 14
            reasons.append("same_funder_name")
        if left_parent and right_parent and left_parent == right_parent:
            score += 10
            reasons.append("same_parent_programme")

        shared_urls = set(left.source_urls) & set(right.source_urls)
        if shared_urls:
            score += 35
            reasons.append("shared_source_url")
        shared_docs = set(left.related_documents) & set(right.related_documents)
        if shared_docs:
            score += 10
            reasons.append("shared_related_document")
        if left.application_url and right.application_url and left.application_url == right.application_url:
            score += 12
            reasons.append("shared_application_url")

        complementary_roles = {normalize_page_role(left.page_role), normalize_page_role(right.page_role)}
        if complementary_roles <= {PAGE_ROLE_OVERVIEW, PAGE_ROLE_ELIGIBILITY, PAGE_ROLE_APPLICATION, PAGE_ROLE_CHECKLIST, PAGE_ROLE_FUNDING_DETAIL}:
            score += 10
            reasons.append("complementary_programme_roles")

        if normalize_page_type(left.page_type) != normalize_page_type(right.page_type):
            score += 4
        if normalize_page_type(left.page_type) in {PAGE_TYPE_NEWS_ARTICLE, PAGE_TYPE_TENDER_PROCUREMENT, PAGE_TYPE_GENERIC_CONTENT}:
            score -= 30
            reasons.append("left_non_programme_page_type")
        if normalize_page_type(right.page_type) in {PAGE_TYPE_NEWS_ARTICLE, PAGE_TYPE_TENDER_PROCUREMENT, PAGE_TYPE_GENERIC_CONTENT}:
            score -= 30
            reasons.append("right_non_programme_page_type")
        if left_name and right_name and left_name != right_name and left_parent != right_parent:
            score -= 35
            reasons.append("different_program_name")
        if left_funder and right_funder and left_funder != right_funder:
            score -= 20
            reasons.append("different_funder_name")

        if score >= 65:
            decision = "merge"
        elif score <= 15:
            decision = "separate"
        else:
            decision = "unclear"
        return {"decision": decision, "score": score, "reasons": reasons, "canonical_group_key": left_key}

    def should_merge_records(self, left: FundingProgrammeRecord, right: FundingProgrammeRecord) -> Optional[bool]:
        # The merge judge is only invoked for records that already look like the
        # same programme by name and funder.
        if not self.api_key:
            return None
        deterministic = self.score_duplicate_records(left, right)
        if deterministic["decision"] == "merge":
            return True
        if deterministic["decision"] == "separate":
            return False
        same_name = clean_text(left.program_name or "").casefold() == clean_text(right.program_name or "").casefold()
        same_funder = clean_text(left.funder_name or "").casefold() == clean_text(right.funder_name or "").casefold()
        if not (same_name and same_funder):
            return None
        # The judge prompt is intentionally conservative because sibling
        # programmes should stay separate unless the evidence is clear.
        system_prompt = (
            "You are a strict JSON judge for funding programme deduplication.\n"
            "Return JSON only.\n"
            "Do not invent details.\n"
            "Be conservative: if two records could be sibling programmes, prefer separate.\n"
            "Merge only when they clearly refer to the same underlying programme.\n"
        )
        user_prompt = self._build_merge_decision_prompt(left, right)
        try:
            raw = self._call_model(system_prompt, user_prompt)
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                match = re.search(r"\{[\s\S]*\}", raw)
                if not match:
                    raise
                payload = json.loads(match.group(0))
            parsed = AIMergeDecisionResponse.model_validate(payload)
        except Exception as exc:
            logger.warning(
                "ai_merge_decision_failed",
                left_program=left.program_name,
                right_program=right.program_name,
                error=str(exc),
            )
            return None
        decision = self._normalize_merge_decision(parsed.merge_decision)
        confidence = parsed.confidence or 0.0
        if decision == "merge" and confidence >= 0.75:
            return True
        if decision == "separate" and confidence >= 0.55:
            return False
        return None

    def _call_openai(self, system_prompt: str, user_prompt: str) -> str:
        # OpenAI is called through the chat completions API with JSON output
        # forced at the transport layer.
        client = OpenAI(api_key=self.api_key)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content or "{}"

    def _call_groq(self, system_prompt: str, user_prompt: str) -> str:
        # Groq uses the OpenAI-compatible HTTP endpoint directly.
        with httpx.Client(timeout=45.0) as client:
            response = client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

    def _call_model(self, system_prompt: str, user_prompt: str) -> str:
        # Route the request to the configured provider and fail fast if no key is
        # available.
        if not self.api_key:
            raise RuntimeError("Missing AI API key.")
        if self.ai_provider == "openai":
            return self._call_openai(system_prompt, user_prompt)
        if self.ai_provider == "groq":
            return self._call_groq(system_prompt, user_prompt)
        raise ValueError(f"Unsupported AI provider: {self.ai_provider}")

    def _parse_response(self, raw: str) -> AIClassificationResponse:
        # The classifier response must be strict JSON; a small regex fallback is
        # used when the model wraps the object in extra text.
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", raw)
            if not match:
                raise
            payload = json.loads(match.group(0))
        if not isinstance(payload, dict):
            raise ValueError("AI response must be a JSON object.")
        return AIClassificationResponse.model_validate(payload)

    def _fallback_classify_single(
        self,
        document: PageContentDocument,
        *,
        forced_page_type: Optional[str] = None,
        fallback_note: str = "Fallback classification used because no AI key was configured.",
    ) -> List[FundingProgrammeRecord]:
        # If remote AI is unavailable, fall back to deterministic heuristics so
        # the pipeline still produces a best-effort record instead of failing.
        document = self._prepare_document_context(document)
        if not forced_page_type:
            page_decision, decision_reasons = _page_decision_hint(document)
            if page_decision == PAGE_DECISION_NOT_FUNDING_PROGRAM:
                logger.info("fallback_rejected_non_program_page", page_url=document.page_url, reasons=decision_reasons)
                return []
        derived = _derive_page_evidence(document)
        document_context = _document_evidence_context(document)
        content_bundle = _document_content_annotation_bundle(document)
        title = document.title or document.page_title or ""
        title_candidate = strip_leading_numbered_prefix(title.split(" - ")[0].split(" | ")[0].strip() or "")
        heading_candidate = strip_leading_numbered_prefix(document.headings[0]) if document.headings else None
        generic_title = bool(title_candidate) and any(term in title_candidate.lower() for term in ["page", "custom", "funding products", "products and services"])
        if title_candidate and not looks_like_support_title(title_candidate) and not generic_title:
            program_name = title_candidate
        else:
            program_name = heading_candidate or title_candidate
        section_text = " ".join(section.content for section in document.structured_sections)
        document_text = _document_evidence_text(document)
        interactive_text = _interactive_sections_text(document)
        body = document.full_body_text or section_text or interactive_text or document_text
        source_domain = document.source_domain or extract_domain(document.page_url)
        funding_type = FundingType.UNKNOWN
        lowered = body.lower()
        if "grant" in lowered:
            funding_type = FundingType.GRANT
        elif "loan" in lowered or "debt" in lowered:
            funding_type = FundingType.LOAN
        elif "equity" in lowered or "shareholding" in lowered or "investment" in lowered:
            funding_type = FundingType.EQUITY
        elif "guarantee" in lowered:
            funding_type = FundingType.GUARANTEE

        combined_text = " ".join([title, body, section_text, interactive_text, document_text])
        money_min, money_max, currency, _snippet, _confidence = extract_money_range(combined_text, default_currency=None)
        budget_total, budget_currency, _budget_snippet, _budget_confidence = extract_budget_total(combined_text)
        if not currency:
            currency = budget_currency
        deadline_info = parse_deadline_info(combined_text)
        eligibility_texts = list(derived["raw_eligibility_data"] or [])
        funding_texts = unique_preserve_order([*derived["raw_funding_offer_data"], *document_context["funding_lines"]])
        documents_texts = unique_preserve_order([*derived["raw_documents_data"], *document_context["evidence_lines"]])
        application_texts = unique_preserve_order([*derived["raw_application_data"], *document_context["application_lines"]])
        eligibility_profile = _derive_eligibility_profile(
            _combine_eligibility_text(document, eligibility_texts, funding_texts),
            industry_taxonomy=self.industry_taxonomy,
            use_of_funds_taxonomy=self.use_of_funds_taxonomy,
            ownership_target_keywords=self.ownership_target_keywords,
            entity_type_keywords=self.entity_type_keywords,
            certification_keywords=self.certification_keywords,
        )
        eligibility_criteria = extract_eligibility_criteria(
            _eligibility_source_text(document, document_context, derived)
        )

        application_urls = [
            url
            for url in unique_preserve_order(
                [*document.application_links, *extract_urls(" ".join([*application_texts, document_context["combined_text"]]))]
            )
            if any(term in url.lower() for term in ["apply", "application", "portal", "register"])
        ]
        contact_source_text = " ".join([*application_texts, document_context["combined_text"]]) or combined_text
        contact_emails = extract_emails(contact_source_text)
        contact_phones = extract_phone_numbers(contact_source_text)
        geography_scope = GeographyScope.UNKNOWN
        if "national" in lowered:
            geography_scope = GeographyScope.NATIONAL
        elif "province" in lowered or "provincial" in lowered:
            geography_scope = GeographyScope.PROVINCE
        elif "municipality" in lowered or "local" in lowered:
            geography_scope = GeographyScope.MUNICIPALITY

        application_channel = ApplicationChannel.UNKNOWN
        if application_urls:
            application_channel = ApplicationChannel.ONLINE_FORM
        elif contact_emails:
            application_channel = ApplicationChannel.EMAIL
        elif "apply" in lowered or "application" in lowered:
            application_channel = ApplicationChannel.MANUAL_CONTACT_FIRST

        required_document_terms = ("document", "documents", "checklist", "certificate", "proof", "registration", "paperwork", "required")
        required_document_sources = [*documents_texts, *document.document_links, *document_context["required_documents"]]
        required_documents = unique_preserve_order(
            [
                clean_text(text)
                for text in required_document_sources
                if clean_text(text) and any(term in clean_text(text).lower() for term in required_document_terms)
            ]
        )

        page_type = forced_page_type or _classify_enhancer_page_type(
            record_count=1,
            candidate_block_count=max(1, len(document.structured_sections) or len(document.headings) or 1),
            internal_link_count=len(document.internal_links),
            detail_link_count=len(document.discovered_links),
            application_link_count=len(document.application_links),
            document_link_count=len(document.document_links),
            text=" ".join([document.title or "", document.full_body_text or ""]),
        )
        source_scope = _source_scope_for_page_type(page_type)

        record = FundingProgrammeRecord(
            program_name=program_name,
            funder_name=_infer_funder_name(document, {"source_domain": source_domain, "source_page_title": document.title}) or None,
            source_url=document.page_url,
            source_urls=[document.page_url],
            source_domain=source_domain,
            source_page_title=document.title,
            scraped_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            last_scraped_at=datetime.now(timezone.utc),
            funding_type=funding_type,
            raw_eligibility_data=eligibility_texts or eligibility_profile["raw_eligibility_data"] or None,
            raw_eligibility_criteria=eligibility_criteria,
            raw_funding_offer_data=funding_texts,
            raw_terms_data=unique_preserve_order([*eligibility_texts, *funding_texts]),
            raw_documents_data=documents_texts,
            raw_application_data=application_texts,
            funding_lines=unique_preserve_order([*funding_texts, *[section.heading for section in document.structured_sections if section.heading]]),
            ticket_min=money_min,
            ticket_max=money_max,
            currency=currency,
            program_budget_total=budget_total,
            deadline_type=(
                DeadlineType.FIXED_DATE
                if deadline_info.get("deadline_date")
                else DeadlineType.OPEN
                if "open" in lowered or "rolling" in lowered
                else DeadlineType.UNKNOWN
            ),
            deadline_date=deadline_info.get("deadline_date"),
            geography_scope=geography_scope,
            related_documents=unique_preserve_order([*document.document_links, *document_context["urls"]]),
            raw_text_snippets={
                **derived["raw_text_snippets"],
                "raw_eligibility_criteria": eligibility_criteria,
                "document_evidence": document_context["evidence_lines"],
            },
            extraction_confidence={
                **derived["extraction_confidence"],
                **({"raw_eligibility_criteria": 0.88} if eligibility_criteria else {}),
            },
            application_channel=application_channel,
            application_url=application_urls[0] if application_urls else None,
            contact_email=contact_emails[0] if contact_emails else None,
            contact_phone=contact_phones[0] if contact_phones else None,
            page_type=page_type,
            page_role=_infer_page_role(document, page_type),
            source_scope=source_scope,
            industries=eligibility_profile["industries"],
            use_of_funds=eligibility_profile["use_of_funds"],
            business_stage_eligibility=eligibility_profile["business_stage_eligibility"],
            turnover_min=eligibility_profile["turnover_min"],
            turnover_max=eligibility_profile["turnover_max"],
            years_in_business_min=eligibility_profile["years_in_business_min"],
            years_in_business_max=eligibility_profile["years_in_business_max"],
            employee_min=eligibility_profile["employee_min"],
            employee_max=eligibility_profile["employee_max"],
            ownership_targets=eligibility_profile["ownership_targets"],
            entity_types_allowed=eligibility_profile["entity_types_allowed"],
            certifications_required=eligibility_profile["certifications_required"],
            required_documents=required_documents,
            notes=unique_preserve_order(
                [
                    *document_context["notes"],
                    fallback_note,
                ]
            ),
            ai_enriched=False,
        )
        payload = record.model_dump(mode="python")
        payload = _merge_content_bundle_into_payload(payload, content_bundle)
        record = FundingProgrammeRecord.model_validate(payload)
        record = _validate_field_evidence(record, content_bundle)
        record = _apply_field_confidence_rules(record, content_bundle)
        record = _validate_post_ai_money_fields(record, document)
        record = _apply_record_review_flags(record)
        finalized = _finalize_record_acceptance(record)
        return [finalized] if finalized else []

    def _fallback_classify(self, document: PageContentDocument) -> List[FundingProgrammeRecord]:
        document = self._prepare_document_context(document)
        page_decision, decision_reasons = _page_decision_hint(document)
        if page_decision == PAGE_DECISION_NOT_FUNDING_PROGRAM:
            logger.info("fallback_rejected_non_program_page", page_url=document.page_url, reasons=decision_reasons)
            return []

        candidates = _collect_fallback_programme_candidates(document)
        if len(candidates) > 1:
            records: List[FundingProgrammeRecord] = []
            for candidate in candidates:
                candidate_document = _document_for_fallback_candidate(document, candidate)
                records.extend(
                    self._fallback_classify_single(
                        candidate_document,
                        forced_page_type=PAGE_TYPE_FUNDING_LISTING,
                        fallback_note="Fallback multi-program candidate classification used because no AI key was configured.",
                    )
                )
            if records:
                return records

        return self._fallback_classify_single(document)

    def _recover_missing_listing_records(
        self,
        document: PageContentDocument,
        records: Sequence[FundingProgrammeRecord],
    ) -> List[FundingProgrammeRecord]:
        if urlparse(document.page_url).path.rstrip("/") in {"", "/"}:
            return list(records)
        candidates = _collect_fallback_programme_candidates(document)
        if len(candidates) <= 1:
            return list(records)

        recovered_records: List[FundingProgrammeRecord] = []
        existing_records = list(records)
        for candidate in candidates:
            if any(_programme_name_matches_candidate(record.program_name, candidate.label) for record in existing_records):
                continue
            candidate_document = _document_for_fallback_candidate(document, candidate)
            recovered_records.extend(
                self._fallback_classify_single(
                    candidate_document,
                    forced_page_type=PAGE_TYPE_FUNDING_LISTING,
                    fallback_note="Deterministic multi-program recovery used because AI omitted a fundable listing section.",
                )
            )

        if not recovered_records:
            return existing_records

        specific_records = [
            record
            for record in existing_records
            if not _is_listing_aggregate_record(record, document, candidates)
        ]
        combined = [*specific_records, *recovered_records]
        logger.info(
            "ai_multi_program_recovery_added_records",
            page_url=document.page_url,
            original_records=len(existing_records),
            recovered_records=len(recovered_records),
            final_records=len(combined),
        )
        return combined

    def classify_document(self, document: PageContentDocument) -> List[FundingProgrammeRecord]:
        # This is the main AI path: prepare context, call the model, retry on
        # malformed or incomplete responses, and fall back if everything fails.
        if not document.page_url:
            return []
        document = self._prepare_document_context(document)
        if not self.api_key:
            if self.require_remote_ai:
                raise RuntimeError("Remote AI classification is required but no AI API key is configured.")
            return self._fallback_classify(document)

        start = time.time()
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(document)
        self._write_artifact("input", document, {"system_prompt": system_prompt, "user_prompt": user_prompt})

        last_error: Optional[Exception] = None
        raw_response = ""
        response: Optional[AIClassificationResponse] = None
        for attempt in range(self.max_retries + 1):
            try:
                raw_response = self._call_model(system_prompt, user_prompt)
                parsed = self._parse_response(raw_response)
                parsed.page_decision = _normalize_page_decision(parsed.page_decision)
                parsed.page_type = normalize_page_type(parsed.page_type) if _coerce_optional_text(parsed.page_type) else None
                if parsed.records:
                    response = parsed
                    break
                response = parsed
                if parsed.page_decision == PAGE_DECISION_NOT_FUNDING_PROGRAM:
                    break
                missing = ["program_name", "funder_name", "funding_type"]
                if attempt < self.max_retries:
                    user_prompt = (
                        self._build_decision_reprompt(document)
                        if parsed.page_decision == PAGE_DECISION_UNCLEAR
                        else self._build_missing_fields_prompt(document, missing)
                    )
                    continue
                break
            except Exception as exc:
                last_error = exc
                logger.warning("ai_classification_attempt_failed", page_url=document.page_url, attempt=attempt + 1, error=str(exc))
                if attempt >= self.max_retries:
                    break
                system_prompt = system_prompt + "\nThe previous response was invalid. Return stricter JSON only."
                user_prompt = self._build_decision_reprompt(document)
                continue

        if response is None:
            self._write_artifact("error", document, {"error": str(last_error) if last_error else "unknown"})
            return self._fallback_classify(document)

        self._write_artifact("output", document, {"raw_response": raw_response, "parsed": response.model_dump(mode="python")})

        if response.page_decision == PAGE_DECISION_NOT_FUNDING_PROGRAM:
            logger.info("ai_classification_rejected_non_program_page", page_url=document.page_url)
            return []
        if _is_domain_navigation_homepage(document):
            logger.info("ai_classification_rejected_navigation_homepage", page_url=document.page_url)
            return []

        records: List[FundingProgrammeRecord] = []
        for draft in _merge_drafts(response.records):
            normalized = _normalize_draft(
                draft,
                document,
                industry_taxonomy=self.industry_taxonomy,
                use_of_funds_taxonomy=self.use_of_funds_taxonomy,
                ownership_target_keywords=self.ownership_target_keywords,
                entity_type_keywords=self.entity_type_keywords,
                certification_keywords=self.certification_keywords,
            )
            missing = _is_missing_required_fields(normalized)
            if missing and response.records and len(missing) >= 3:
                logger.info("ai_classification_missing_fields", page_url=document.page_url, missing=missing)
            records.append(
                _draft_to_record(
                    normalized,
                    document,
                    parser_version="ai-first-v1",
                    industry_taxonomy=self.industry_taxonomy,
                    use_of_funds_taxonomy=self.use_of_funds_taxonomy,
                    ownership_target_keywords=self.ownership_target_keywords,
                    entity_type_keywords=self.entity_type_keywords,
                    certification_keywords=self.certification_keywords,
                )
            )

        if not records:
            logger.info(
                "ai_classification_returned_no_records",
                page_url=document.page_url,
                page_decision=response.page_decision,
                notes=response.notes,
            )
            return []

        inferred_page_type = _classify_enhancer_page_type(
            record_count=len(records),
            candidate_block_count=max(1, len(document.structured_sections) or len(document.headings) or 1),
            internal_link_count=len(document.internal_links),
            detail_link_count=len(document.discovered_links),
            application_link_count=len(document.application_links),
            document_link_count=len(document.document_links),
            text=" ".join([document.title or "", document.full_body_text or ""]),
        )
        explicit_page_type = _coerce_optional_text(response.page_type)
        page_type = normalize_page_type(explicit_page_type or inferred_page_type)
        if not explicit_page_type and page_type == PAGE_TYPE_GENERIC_CONTENT and records:
            page_type = PAGE_TYPE_FUNDING_LISTING if len(records) > 1 else PAGE_TYPE_FUNDING_PROGRAMME
        source_scope = _source_scope_for_page_type(page_type)
        if page_type in {
            PAGE_TYPE_TENDER_PROCUREMENT,
            PAGE_TYPE_NEWS_ARTICLE,
            PAGE_TYPE_TECHNOLOGY_STATION,
            PAGE_TYPE_SUPPORT_PROGRAMME,
            PAGE_TYPE_GENERIC_CONTENT,
        }:
            logger.info("ai_classification_rejected_page_type", page_url=document.page_url, page_type=page_type)
            return []
        finalized_records: List[FundingProgrammeRecord] = []
        for record in records:
            record.page_type = page_type if explicit_page_type else normalize_page_type(record.page_type or page_type)
            record.page_role = normalize_page_role(record.page_role or _infer_page_role(document, record.page_type))
            if record.page_type == PAGE_TYPE_GENERIC_CONTENT:
                record.page_type = page_type
            if not record.source_scope:
                record.source_scope = source_scope
            record = _validate_post_ai_money_fields(record, document)
            record = _apply_record_review_flags(record)
            finalized = _finalize_record_acceptance(record)
            if finalized:
                finalized_records.append(finalized)
        records = finalized_records
        if page_type == PAGE_TYPE_OPEN_CALL and not any(has_fundable_support(record) for record in records):
            logger.info("ai_classification_rejected_unfundable_open_call", page_url=document.page_url)
            return []
        if not records:
            logger.info("ai_classification_rejected_all_records", page_url=document.page_url, page_type=page_type)
            return []
        records = self._recover_missing_listing_records(document, records)

        duration = time.time() - start
        logger.info("ai_classification_success", page_url=document.page_url, duration=duration, records=len(records))
        return records

    def classify_page(self, document: PageContentDocument) -> List[FundingProgrammeRecord]:
        # Public wrapper kept for callers that still use the older page-oriented
        # name.
        return self.classify_document(document)

    def classify_documents(self, documents: Sequence[PageContentDocument]) -> List[FundingProgrammeRecord]:
        # Batch classification simply runs the single-document path for each page
        # and concatenates the results.
        records: List[FundingProgrammeRecord] = []
        for document in documents:
            records.extend(self.classify_document(document))
        return records

    # Compatibility shims for the older enrichment interface.
    def enrich_record(self, record: FundingProgrammeRecord, page_text_or_context: Any) -> FundingProgrammeRecord:
        # Older callers can still provide a page document or raw text and get a
        # single best-effort record back.
        if isinstance(page_text_or_context, PageContentDocument):
            classified = self.classify_document(page_text_or_context)
            return classified[0] if classified else record
        text = _coerce_text(page_text_or_context)
        if not text:
            return record
        document = PageContentDocument(
            page_url=record.source_url,
            title=record.source_page_title or record.program_name,
            headings=[],
            full_body_text=text,
            source_domain=record.source_domain,
            page_title=record.source_page_title or record.program_name,
        )
        classified = self.classify_document(document)
        return classified[0] if classified else record

    def enrich_records(self, records: List[FundingProgrammeRecord], page_context: Any) -> List[FundingProgrammeRecord]:
        # Compatibility layer for older callers that still expect an "enrich"
        # style API rather than the newer classify-first flow.
        if isinstance(page_context, PageContentDocument):
            page_context = self._prepare_document_context(page_context)
            if self.api_key:
                # When AI is available, the existing records are re-evaluated
                # against the page context as a batch.
                record_snapshots = [
                    PageAIRecordSnapshot(
                        record_index=index,
                        normalized_record=record.model_dump(mode="json", exclude={"page_debug_package"}),
                    )
                    for index, record in enumerate(records)
                ] if records else None
                if record_snapshots is not None:
                    system_prompt = self._build_system_prompt()
                    user_prompt = self._build_user_prompt(page_context, record_snapshots=record_snapshots)
                    self._write_artifact("input", page_context, {"system_prompt": system_prompt, "user_prompt": user_prompt})
                    raw_response = self._call_model(system_prompt, user_prompt)
                    parsed = self._parse_response(raw_response)
                    parsed.page_decision = _normalize_page_decision(parsed.page_decision)
                    if parsed.page_decision == PAGE_DECISION_NOT_FUNDING_PROGRAM:
                        return []
                    updated_records: List[FundingProgrammeRecord] = []
                    for draft in _merge_drafts(parsed.records):
                        # Each draft is normalized back into the canonical record
                        # shape before being returned to the caller.
                        normalized = _normalize_draft(
                            draft,
                            page_context,
                            industry_taxonomy=self.industry_taxonomy,
                            use_of_funds_taxonomy=self.use_of_funds_taxonomy,
                            ownership_target_keywords=self.ownership_target_keywords,
                            entity_type_keywords=self.entity_type_keywords,
                            certification_keywords=self.certification_keywords,
                        )
                        updated_records.append(
                            _draft_to_record(
                                normalized,
                                page_context,
                                parser_version="ai-first-v1",
                                industry_taxonomy=self.industry_taxonomy,
                                use_of_funds_taxonomy=self.use_of_funds_taxonomy,
                                ownership_target_keywords=self.ownership_target_keywords,
                                entity_type_keywords=self.entity_type_keywords,
                                certification_keywords=self.certification_keywords,
                            )
                        )
                    return updated_records or list(records)
            classified = self.classify_document(page_context)
            return classified or list(records)
        if not records:
            return []
        return list(records)


# Backwards-compatible alias used by older code paths.
AIEnhancer = AIClassifier
