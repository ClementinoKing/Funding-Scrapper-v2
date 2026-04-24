"""AI-first classification for raw page content."""

from __future__ import annotations

import json
import os
import re
import time
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
from scraper.schemas import (
    CandidateBlockSnapshot,
    AIMergeDecisionResponse,
    AIClassificationResponse,
    AIProgrammeDraft,
    ApprovalStatus,
    ApplicationChannel,
    DeadlineType,
    FundingProgrammeRecord,
    FundingType,
    GeographyScope,
    InterestType,
    PageContentDocument,
    PageAIRecordSnapshot,
    ProgrammeStatus,
    RepaymentFrequency,
    TriState,
)
from scraper.utils.dates import parse_deadline_info
from scraper.utils.money import extract_budget_total, extract_money_range, infer_default_currency
from scraper.parsers.normalization import classify_page_type
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
from scraper.utils.urls import canonicalize_url, extract_domain


logger = structlog.get_logger()

PROMPT_KEYWORDS = ("fund", "eligibility", "criteria", "requirements", "investment", "loan")
MAX_SECTION_CHARS = 1800
MAX_BODY_CHARS = 8000
MAX_PROMPT_CHARS = 22000
PAGE_DECISION_FUNDING_PROGRAM = "funding_program"
PAGE_DECISION_NOT_FUNDING_PROGRAM = "not_funding_program"
PAGE_DECISION_UNCLEAR = "unclear"
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

ELIGIBILITY_STAGE_PATTERNS = {
    "startup": ("startup", "start-up", "new business", "early-stage business"),
    "seed": ("seed", "seed stage"),
    "early stage": ("early stage", "early-stage", "emerging business"),
    "growth stage": ("growth stage", "scale-up", "growth-focused"),
    "expansion": ("expansion", "expanding", "expand your business"),
    "established business": ("established business", "existing business", "trading for"),
}


def _coerce_text(value: Any) -> str:
    return clean_text(str(value)) if value is not None else ""


def _coerce_optional_text(value: Any) -> Optional[str]:
    text = _coerce_text(value)
    return text or None


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


def _coerce_int(value: Any) -> Optional[int]:
    float_value = _coerce_float(value)
    if float_value is None:
        return None
    return int(float_value)


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


def _extract_stage_labels(text: str) -> List[str]:
    lowered = (text or "").lower()
    labels: List[str] = []
    for label, terms in ELIGIBILITY_STAGE_PATTERNS.items():
        if any(term in lowered for term in terms):
            labels.append(label)
    return unique_preserve_order(labels)


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


def _trim_lines(text: str, max_lines: int = 120) -> str:
    lines = [clean_text(line) for line in (text or "").splitlines()]
    deduped = unique_preserve_order([line for line in lines if line])
    return "\n".join(deduped[:max_lines])


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


def _build_prompt_content(document: PageContentDocument) -> Dict[str, Any]:
    sections = [
        {"heading": section.heading, "content": section.content}
        for section in document.structured_sections
    ]
    selected_sections = _keyword_section_filter(sections)
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
        "headings": document.headings,
        "structured_sections": selected_sections,
        "full_body_text": body_excerpt,
        "source_domain": document.source_domain,
        "main_content_hint": document.main_content_hint,
        "classification_hint": {
            "page_decision": page_decision,
            "reasons": decision_reasons,
        },
    }
    return {key: value for key, value in prompt_payload.items() if value not in (None, "", [], {})}


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


def _compact_record_prompt_data(record_data: Dict[str, Any]) -> Dict[str, Any]:
    prompt_data: Dict[str, Any] = {}
    for key, value in record_data.items():
        if key in PROMPT_RECORD_FIELD_EXCLUSIONS:
            continue
        compacted = _compact_prompt_value(value)
        if compacted not in (None, "", [], {}):
            prompt_data[key] = compacted
    return prompt_data


def _record_prompt_terms(record_data: Dict[str, Any]) -> List[str]:
    terms: List[str] = []
    for field_name in ("program_name", "funder_name", "parent_programme_name", "source_page_title", "application_channel", "geography_scope"):
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
    return {key: value for key, value in payload.items() if value not in (None, "", [], {})}


def _estimate_prompt_size(payload: Dict[str, Any]) -> int:
    return len(json.dumps(payload, ensure_ascii=False)) // 4


def _normalize_page_decision(value: Any) -> str:
    text = _coerce_text(value).casefold().replace("-", "_").replace(" ", "_")
    if text in {
        PAGE_DECISION_FUNDING_PROGRAM,
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


def _page_decision_hint(document: PageContentDocument) -> Tuple[str, List[str]]:
    text = " ".join(
        [
            document.page_url or "",
            document.title or "",
            document.page_title or "",
            " ".join(document.headings or []),
            document.main_content_hint or "",
            (document.full_body_text or "")[:2000],
        ]
    ).casefold()
    program_hits = [term for term in PROGRAMME_SIGNAL_TERMS if term in text]
    non_program_hits = [term for term in NON_PROGRAMME_SIGNAL_TERMS if term in text]
    file_like = bool(re.search(r"\bimg[-_ ]?\d|\.(?:jpe?g|png|gif|webp|pdf)(?:\b|$)", text))
    if file_like and len(program_hits) < 2:
        return PAGE_DECISION_NOT_FUNDING_PROGRAM, ["title or URL looks like a file or media asset"]
    if len(non_program_hits) >= 2 and len(program_hits) == 0:
        return PAGE_DECISION_NOT_FUNDING_PROGRAM, ["page matches generic article/media/policy signals"]
    if len(program_hits) >= 2:
        return PAGE_DECISION_FUNDING_PROGRAM, [f"contains programme signals: {', '.join(program_hits[:4])}"]
    if len(program_hits) == 1 and len(non_program_hits) == 0 and len((document.full_body_text or "").strip()) >= 600:
        return PAGE_DECISION_FUNDING_PROGRAM, [f"contains funding signal: {program_hits[0]}"]
    return PAGE_DECISION_UNCLEAR, []


def _collect_section_snippets(
    document: PageContentDocument,
    heading_terms: Sequence[str],
    body_terms: Sequence[str],
    *,
    fallback_chars: int = 1200,
    max_sentences: int = 4,
) -> List[str]:
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
    funding_offer = _collect_section_snippets(
        document,
        heading_terms=("fund", "funding", "finance", "loan", "grant", "offer", "investment"),
        body_terms=("fund", "funding", "finance", "loan", "grant", "equity", "investment"),
    )
    eligibility = _collect_section_snippets(
        document,
        heading_terms=("eligibility", "criteria", "requirements", "who qualifies", "qualifies"),
        body_terms=("eligibility", "criteria", "requirement", "qualify", "ownership", "stage"),
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
    lowered = (text or "").lower()
    industries = unique_preserve_order(match_keyword_map(text, industry_taxonomy)[0]) if industry_taxonomy else []
    use_of_funds = unique_preserve_order(match_keyword_map(text, use_of_funds_taxonomy)[0]) if use_of_funds_taxonomy else []
    ownership_targets = unique_preserve_order(match_keyword_map(text, ownership_target_keywords)[0]) if ownership_target_keywords else []
    entity_types_allowed = unique_preserve_order(match_keyword_map(text, entity_type_keywords)[0]) if entity_type_keywords else []
    certifications_required = unique_preserve_order(match_keyword_map(text, certification_keywords)[0]) if certification_keywords else []
    business_stage_eligibility = _extract_stage_labels(text)
    turnover_min = turnover_max = None
    for sentence in sentence_chunks(text):
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
    parts = [
        *[clean_text(item) for item in eligibility_items if clean_text(item)],
        *[clean_text(item) for item in extra_items if clean_text(item)],
        *[section.content for section in document.structured_sections if clean_text(section.content)],
        document.full_body_text or "",
        document.title or "",
    ]
    return " ".join(unique_preserve_order([part for part in parts if part]))


def _merge_drafts(drafts: Sequence[AIProgrammeDraft]) -> List[AIProgrammeDraft]:
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
    derived = _derive_page_evidence(document)
    payload = draft.model_dump(mode="python")
    ai_eligibility_items = _coerce_list(payload.get("raw_eligibility_data"))
    eligibility_text = _combine_eligibility_text(
        document,
        ai_eligibility_items or derived["raw_eligibility_data"] or [],
        derived["raw_terms_data"],
    )
    eligibility_profile = _derive_eligibility_profile(
        eligibility_text,
        industry_taxonomy=industry_taxonomy,
        use_of_funds_taxonomy=use_of_funds_taxonomy,
        ownership_target_keywords=ownership_target_keywords,
        entity_type_keywords=entity_type_keywords,
        certification_keywords=certification_keywords,
    )
    payload["source_url"] = document.page_url
    payload["source_urls"] = [document.page_url]
    payload["source_page_title"] = _coerce_optional_text(payload.get("source_page_title")) or document.title
    payload["program_name"] = strip_leading_numbered_prefix(_coerce_optional_text(payload.get("program_name")) or "")
    if not payload["program_name"] and document.title:
        payload["program_name"] = strip_leading_numbered_prefix(document.title)
    payload["funder_name"] = _coerce_optional_text(payload.get("funder_name"))
    payload["parent_programme_name"] = _coerce_optional_text(payload.get("parent_programme_name"))
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
    payload["funding_lines"] = _coerce_list(payload.get("funding_lines")) or list(derived["raw_funding_offer_data"])
    payload["raw_eligibility_data"] = ai_eligibility_items or derived["raw_eligibility_data"]
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
    payload["required_documents"] = _coerce_list(payload.get("required_documents"))
    payload["related_documents"] = unique_preserve_order([*document.document_links, *_coerce_list(payload.get("related_documents"))])
    payload["notes"] = _coerce_list(payload.get("notes"))
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
    payload["application_url"] = _coerce_optional_text(payload.get("application_url"))
    payload["contact_email"] = _coerce_optional_text(payload.get("contact_email"))
    payload["contact_phone"] = _coerce_optional_text(payload.get("contact_phone"))
    payload["raw_funding_offer_data"] = _coerce_list(payload.get("raw_funding_offer_data")) or list(derived["raw_funding_offer_data"])
    payload["raw_terms_data"] = _coerce_list(payload.get("raw_terms_data")) or list(derived["raw_terms_data"])
    payload["raw_documents_data"] = _coerce_list(payload.get("raw_documents_data")) or list(derived["raw_documents_data"])
    payload["raw_application_data"] = _coerce_list(payload.get("raw_application_data")) or list(derived["raw_application_data"])
    payload["raw_text_snippets"] = {
        key: _coerce_list(value) for key, value in {**derived["raw_text_snippets"], **dict(payload.get("raw_text_snippets") or {})}.items()
    }
    payload["extraction_confidence"] = {
        str(key): max(0.0, min(float(value), 1.0))
        for key, value in {**derived["extraction_confidence"], **dict(payload.get("extraction_confidence") or {})}.items()
        if value is not None
    }
    payload["approval_status"] = (
        _coerce_text(payload.get("approval_status")).casefold() if payload.get("approval_status") else ApprovalStatus.PENDING.value
    )
    if payload["approval_status"] not in {member.value for member in ApprovalStatus}:
        payload["approval_status"] = ApprovalStatus.PENDING.value
    payload["country_code"] = _coerce_text(payload.get("country_code")) or "ZA"
    payload["status"] = _coerce_text(payload.get("status")) or "unknown"
    payload["ai_enriched"] = True
    payload["source_domain"] = document.source_domain or extract_domain(document.page_url)
    payload["program_name"] = payload["program_name"] or strip_leading_numbered_prefix(document.title or "") or (
        document.title if document.title and len(document.title.split()) <= 12 else None
    )
    payload["funder_name"] = payload["funder_name"] or payload["source_domain"].replace(".", " ").title() if payload["source_domain"] else None
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
    now = datetime.now(timezone.utc)
    derived = _derive_page_evidence(document)
    payload = draft.model_dump(mode="python")
    ai_eligibility_items = _coerce_list(payload.get("raw_eligibility_data"))
    eligibility_text = _combine_eligibility_text(
        document,
        ai_eligibility_items or derived["raw_eligibility_data"] or [],
        derived["raw_terms_data"],
    )
    eligibility_profile = _derive_eligibility_profile(
        eligibility_text,
        industry_taxonomy=industry_taxonomy,
        use_of_funds_taxonomy=use_of_funds_taxonomy,
        ownership_target_keywords=ownership_target_keywords,
        entity_type_keywords=entity_type_keywords,
        certification_keywords=certification_keywords,
    )
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

    raw_eligibility_data = ai_eligibility_items or eligibility_profile["raw_eligibility_data"] or derived["raw_eligibility_data"]
    funding_lines = _coerce_list(payload.get("funding_lines")) or list(derived["raw_funding_offer_data"])
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
    required_documents = _coerce_list(payload.get("required_documents"))
    related_documents = unique_preserve_order([*document.document_links])
    notes = unique_preserve_order([*_coerce_list(payload.get("notes"))])
    source_urls = [source_url]

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
    payback_months_min = _coerce_int(payload.get("payback_months_min"))
    payback_months_max = _coerce_int(payload.get("payback_months_max"))
    currency = _coerce_text(payload.get("currency")) or None
    if not currency:
        currency = infer_default_currency(document.full_body_text or document.title or "", source_domain=source_domain or "")
    if not currency and any(text for text in (ticket_min, ticket_max, program_budget_total) if text is not None):
        currency = "ZAR" if (source_domain or "").endswith(".za") else None

    deadline_info = parse_deadline_info(
        " ".join(
            [
                document.title or "",
                document.full_body_text or "",
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

    raw_text_snippets = {
        key: _coerce_list(value)
        for key, value in {**derived["raw_text_snippets"], **dict(payload.get("raw_text_snippets") or {})}.items()
    }

    extraction_confidence = {
        str(key): max(0.0, min(float(value), 1.0))
        for key, value in {**derived["extraction_confidence"], **dict(payload.get("extraction_confidence") or {})}.items()
        if value is not None
    }
    if not extraction_confidence and _coerce_text(payload.get("program_name")):
        extraction_confidence["program_name"] = 0.65

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
        raw_funding_offer_data=list(derived["raw_funding_offer_data"]),
        raw_terms_data=list(derived["raw_terms_data"]),
        raw_documents_data=list(derived["raw_documents_data"]),
        raw_application_data=list(derived["raw_application_data"]),
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
        interest_type=interest_type,
        repayment_frequency=repayment_frequency,
        exclusions=exclusions,
        required_documents=required_documents,
        application_channel=application_channel,
        application_url=_coerce_optional_text(payload.get("application_url")),
        contact_email=_coerce_optional_text(payload.get("contact_email")),
        contact_phone=_coerce_optional_text(payload.get("contact_phone")),
        raw_text_snippets=raw_text_snippets,
        extraction_confidence=extraction_confidence,
        evidence_by_field={},
        field_confidence=dict(extraction_confidence),
        related_documents=related_documents,
        parser_version=parser_version or SCRAPER_VERSION,
        ai_enriched=True,
        approval_status=approval_status,
        country_code=_coerce_text(payload.get("country_code")) or "ZA",
        status=_coerce_enum(ProgrammeStatus, payload.get("status")) or ProgrammeStatus.UNKNOWN,
        notes=notes or [f"AI classification applied to {document.page_url}"],
    )
    return FundingProgrammeRecord.model_validate(record.model_dump(mode="python"))


class AIClassifier:
    """Classify cleaned page content into the funding-programme schema."""

    def __init__(self, config: Dict[str, Any], storage: Optional[Any] = None) -> None:
        self.config = config
        self.storage = storage
        self.disable_remote_ai = bool(config.get("disableRemoteAi") or config.get("offline"))
        self.ai_provider = (config.get("aiProvider") or os.getenv("AI_PROVIDER") or "openai").strip().lower()
        self.model = config.get("aiModel") or os.getenv("SCRAPER_AI_MODEL") or "gpt-4o-mini"
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

    def _artifact_slug(self, document: PageContentDocument) -> str:
        return re.sub(r"[^a-zA-Z0-9]+", "-", document.page_url.lower()).strip("-")[:120] or "page"

    def _write_artifact(self, kind: str, document: PageContentDocument, payload: Any) -> None:
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

    def _build_system_prompt(self) -> str:
        return (
            "You are a strict JSON classifier for funding programme pages.\n"
            "Return JSON only. Do not add markdown, comments, or explanations.\n"
            "Use only evidence present in the supplied page content.\n"
            "Existing extracted values are included in current_records; treat them as the starting record state and preserve any populated field unless the page evidence clearly supports a correction.\n"
            "Do not invent missing values. If a value is absent, use null, an empty array, or Unknown.\n"
            "Prefer exact wording for eligibility and requirements.\n"
            "Normalize money values to plain numbers.\n"
            "First decide whether the page is a real funding programme page.\n"
            "If the page is not a programme page, set page_decision to not_funding_program and return records as an empty array.\n"
            "Use not_funding_program for article, news, policy, about, contact, media, image, gallery, document, or screenshot pages that are not the actual funding programme page.\n"
            "Use funding_program only when the page is clearly a programme page with substantive funding, eligibility, or application evidence.\n"
            "A child or sub-programme is still a real programme record if it has its own distinct name, rules, or funding terms.\n"
            "Do not collapse sibling programmes just because they share a parent fund or similar numbered naming.\n"
            "When raw_eligibility_data is present, extract it into industries, use_of_funds, business_stage_eligibility, turnover_min/max, years_in_business_min/max, employee_min/max, ownership_targets, entity_types_allowed, and certifications_required whenever supported.\n"
            "Prefer short list values for those fields and do not leave them blank if the eligibility text clearly supports them.\n"
            "If the page is ambiguous, use unclear and keep records empty unless the page clearly supports a programme record.\n"
            "Return an object with keys: page_decision, page_decision_confidence, records, and notes.\n"
            "records must be an array of 0 or more programme objects.\n"
            "Set source_url and source_urls to the current page URL only unless the page clearly references another canonical source page.\n"
            "Each programme object may contain only funding-programme fields and must omit technical DB fields such as program_id, id, created_at, updated_at, scraped_at, source_domain, parser_version, approval_status, and ai_enriched.\n"
            "Allowed business fields include program_name, funder_name, source_url, source_urls, source_page_title, raw_eligibility_data, raw_funding_offer_data, raw_terms_data, raw_documents_data, raw_application_data, funding_type, funding_lines, ticket_min, ticket_max, currency, program_budget_total, deadline_type, deadline_date, funding_speed_days_min, funding_speed_days_max, geography_scope, provinces, municipalities, postal_code_ranges, industries, use_of_funds, business_stage_eligibility, turnover_min, turnover_max, years_in_business_min, years_in_business_max, employee_min, employee_max, ownership_targets, entity_types_allowed, certifications_required, security_required, equity_required, payback_months_min, payback_months_max, interest_type, repayment_frequency, exclusions, required_documents, application_channel, application_url, contact_email, contact_phone, raw_text_snippets, extraction_confidence, related_documents, notes, status, country_code, and parent_programme_name."
        )

    def _build_user_prompt(
        self,
        document: PageContentDocument,
        *,
        record_snapshots: Optional[Sequence[PageAIRecordSnapshot | Dict[str, Any] | Any]] = None,
    ) -> str:
        payload = _build_context_prompt_payload(document, record_snapshots=record_snapshots)
        prompt = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        if len(prompt) > MAX_PROMPT_CHARS:
            prompt = prompt[: MAX_PROMPT_CHARS - 3] + "..."
        return (
            "Map the page content into zero or more funding-programme records.\n"
            "If the page is not a programme page, return {\"page_decision\": \"not_funding_program\", \"records\": [], \"notes\": [...]}.\n"
            "If the page is a sub-programme with its own name and terms, keep it as an independent programme record.\n"
            "Use the values already present under current_records as the baseline record state and only change them when the page evidence supports a better value.\n"
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
        payload = _build_context_prompt_payload(document, record_snapshots=record_snapshots)
        prompt = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        if len(prompt) > MAX_PROMPT_CHARS:
            prompt = prompt[: MAX_PROMPT_CHARS - 3] + "..."
        return (
            "Decide whether this page is a real funding programme page.\n"
            "If it is not, return page_decision as not_funding_program and records as an empty array.\n"
            "If it is, return page_decision as funding_program and include only records directly supported by the page.\n"
            "Do not guess.\n\n"
            f"PAGE CONTENT:\n{prompt}"
        )

    def _merge_record_payload(self, record: FundingProgrammeRecord) -> Dict[str, Any]:
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
            "source_scope": record.source_scope,
            "funding_type": record.funding_type.value if hasattr(record.funding_type, "value") else record.funding_type,
            "funding_lines": list(record.funding_lines),
            "raw_eligibility_data": list(record.raw_eligibility_data or []),
            "raw_funding_offer_data": list(record.raw_funding_offer_data),
            "raw_terms_data": list(record.raw_terms_data),
            "raw_documents_data": list(record.raw_documents_data),
            "raw_application_data": list(record.raw_application_data),
            "application_url": record.application_url,
            "contact_email": record.contact_email,
            "contact_phone": record.contact_phone,
            "related_documents": list(record.related_documents),
            "notes": list(record.notes),
        }

    def _build_merge_decision_prompt(self, left: FundingProgrammeRecord, right: FundingProgrammeRecord) -> str:
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
        text = _coerce_text(value).casefold().replace("-", "_").replace(" ", "_")
        if text in {"merge", "same", "same_program", "same_programme", "duplicate", "duplicates"}:
            return "merge"
        if text in {"separate", "different", "different_program", "different_programme", "no_merge"}:
            return "separate"
        return "unclear"

    def should_merge_records(self, left: FundingProgrammeRecord, right: FundingProgrammeRecord) -> Optional[bool]:
        if not self.api_key:
            return None
        same_name = clean_text(left.program_name or "").casefold() == clean_text(right.program_name or "").casefold()
        same_funder = clean_text(left.funder_name or "").casefold() == clean_text(right.funder_name or "").casefold()
        if not (same_name and same_funder):
            return None
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
        if not self.api_key:
            raise RuntimeError("Missing AI API key.")
        if self.ai_provider == "openai":
            return self._call_openai(system_prompt, user_prompt)
        if self.ai_provider == "groq":
            return self._call_groq(system_prompt, user_prompt)
        raise ValueError(f"Unsupported AI provider: {self.ai_provider}")

    def _parse_response(self, raw: str) -> AIClassificationResponse:
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

    def _fallback_classify(self, document: PageContentDocument) -> List[FundingProgrammeRecord]:
        page_decision, decision_reasons = _page_decision_hint(document)
        if page_decision == PAGE_DECISION_NOT_FUNDING_PROGRAM:
            logger.info("fallback_rejected_non_program_page", page_url=document.page_url, reasons=decision_reasons)
            return []
        derived = _derive_page_evidence(document)
        title = document.title or document.page_title or ""
        title_candidate = strip_leading_numbered_prefix(title.split(" - ")[0].split(" | ")[0].strip() or "")
        heading_candidate = strip_leading_numbered_prefix(document.headings[0]) if document.headings else None
        generic_title = bool(title_candidate) and any(term in title_candidate.lower() for term in ["page", "custom", "funding products", "products and services"])
        if title_candidate and not looks_like_support_title(title_candidate) and not generic_title:
            program_name = title_candidate
        else:
            program_name = heading_candidate or title_candidate
        section_text = " ".join(section.content for section in document.structured_sections)
        body = document.full_body_text or section_text
        source_domain = document.source_domain or extract_domain(document.page_url)
        funding_type = FundingType.UNKNOWN
        lowered = body.lower()
        if "grant" in lowered:
            funding_type = FundingType.GRANT
        elif "loan" in lowered or "debt" in lowered:
            funding_type = FundingType.LOAN
        elif "equity" in lowered or "shareholding" in lowered:
            funding_type = FundingType.EQUITY
        elif "guarantee" in lowered:
            funding_type = FundingType.GUARANTEE

        combined_text = " ".join([title, body, section_text])
        money_min, money_max, currency, _snippet, _confidence = extract_money_range(combined_text, default_currency=None)
        budget_total, budget_currency, _budget_snippet, _budget_confidence = extract_budget_total(combined_text)
        if not currency:
            currency = budget_currency
        deadline_info = parse_deadline_info(combined_text)
        eligibility_texts = list(derived["raw_eligibility_data"] or [])
        funding_texts = list(derived["raw_funding_offer_data"] or [])
        documents_texts = list(derived["raw_documents_data"] or [])
        application_texts = list(derived["raw_application_data"] or [])
        eligibility_profile = _derive_eligibility_profile(
            _combine_eligibility_text(document, eligibility_texts, funding_texts),
            industry_taxonomy=self.industry_taxonomy,
            use_of_funds_taxonomy=self.use_of_funds_taxonomy,
            ownership_target_keywords=self.ownership_target_keywords,
            entity_type_keywords=self.entity_type_keywords,
            certification_keywords=self.certification_keywords,
        )

        application_urls = [
            url
            for url in unique_preserve_order([*document.application_links, *extract_urls(" ".join(application_texts))])
            if any(term in url.lower() for term in ["apply", "application", "portal", "register"])
        ]
        contact_emails = extract_emails(" ".join(application_texts) or combined_text)
        contact_phones = extract_phone_numbers(" ".join(application_texts) or combined_text)
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

        page_type = classify_page_type(
            record_count=1,
            candidate_block_count=max(1, len(document.structured_sections) or len(document.headings) or 1),
            internal_link_count=len(document.internal_links),
            detail_link_count=len(document.discovered_links),
            application_link_count=len(document.application_links),
            document_link_count=len(document.document_links),
            text=" ".join([document.title or "", document.full_body_text or ""]),
        )
        source_scope = "support_page" if page_type == "support" else "listing_page" if page_type == "listing" else "product_page"

        record = FundingProgrammeRecord(
            program_name=program_name,
            funder_name=(source_domain or "").replace(".", " ").title() or None,
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
            related_documents=unique_preserve_order([*document.document_links]),
            raw_text_snippets=derived["raw_text_snippets"],
            extraction_confidence=derived["extraction_confidence"],
            application_channel=application_channel,
            application_url=application_urls[0] if application_urls else None,
            contact_email=contact_emails[0] if contact_emails else None,
            contact_phone=contact_phones[0] if contact_phones else None,
            page_type=page_type,
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
            required_documents=unique_preserve_order(
                [
                    clean_text(re.split(r"(?i)\bapply\b.*", text)[0])
                    for text in [*documents_texts, *document.document_links]
                    if clean_text(re.split(r"(?i)\bapply\b.*", text)[0])
                ]
            ),
            notes=["Fallback classification used because no AI key was configured."],
            ai_enriched=False,
        )
        return [FundingProgrammeRecord.model_validate(record.model_dump(mode="python"))]

    def classify_document(self, document: PageContentDocument) -> List[FundingProgrammeRecord]:
        if not document.page_url:
            return []
        if not self.api_key:
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

        page_type = classify_page_type(
            record_count=len(records),
            candidate_block_count=max(1, len(document.structured_sections) or len(document.headings) or 1),
            internal_link_count=len(document.internal_links),
            detail_link_count=len(document.discovered_links),
            application_link_count=len(document.application_links),
            document_link_count=len(document.document_links),
            text=" ".join([document.title or "", document.full_body_text or ""]),
        )
        source_scope = "support_page" if page_type == "support" else "listing_page" if page_type == "listing" else "product_page"
        for record in records:
            if not record.page_type:
                record.page_type = page_type
            if not record.source_scope:
                record.source_scope = source_scope

        duration = time.time() - start
        logger.info("ai_classification_success", page_url=document.page_url, duration=duration, records=len(records))
        return records

    def classify_page(self, document: PageContentDocument) -> List[FundingProgrammeRecord]:
        return self.classify_document(document)

    def classify_documents(self, documents: Sequence[PageContentDocument]) -> List[FundingProgrammeRecord]:
        records: List[FundingProgrammeRecord] = []
        for document in documents:
            records.extend(self.classify_document(document))
        return records

    # Compatibility shims for the older enrichment interface.
    def enrich_record(self, record: FundingProgrammeRecord, page_text_or_context: Any) -> FundingProgrammeRecord:
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
        if isinstance(page_context, PageContentDocument):
            if self.api_key:
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


AIEnhancer = AIClassifier
