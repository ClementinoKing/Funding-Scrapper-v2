"""Map web-search extraction drafts into canonical scraper records."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from scraper.schemas import (
    ApplicationChannel,
    FundingProgrammeRecord,
    FundingType,
    GeographyScope,
    ProgrammeStatus,
    RepaymentFrequency,
)
from scraper.utils.money import extract_money_range, parse_money_token
from scraper.utils.text import clean_text, unique_preserve_order
from scraper.utils.urls import canonicalize_url, extract_host
from scraper.web_search.models import WebSearchFunder, WebSearchProgrammeDraft, WebSearchSource


FUNDING_TYPE_TERMS = {
    FundingType.LOAN: ("repayment", "repayable", "loan term", "tenor", "interest", "collateral", "security"),
    FundingType.EQUITY: ("ownership stake", "shareholding", "equity participation", "investment exit", "equity stake"),
    FundingType.GRANT: ("non-repayable", "non repayable", "grant"),
    FundingType.GUARANTEE: ("guarantee", "guarantees"),
}


def draft_to_record(
    draft: WebSearchProgrammeDraft,
    *,
    funder: WebSearchFunder,
    secondary_sources: Iterable[WebSearchSource],
) -> Optional[FundingProgrammeRecord]:
    if not draft.source_url or not draft.program_name:
        return None
    source_url = canonicalize_url(draft.source_url)
    if not source_url:
        return None

    now = datetime.now(timezone.utc)
    source_domain = extract_host(source_url)
    confidence = draft.confidence_score / 100
    funding_type = _classify_funding_type(draft)
    ticket_min = _coerce_money_value(draft.ticket_min, funder.currency)
    ticket_max = _coerce_money_value(draft.ticket_max, funder.currency)
    if ticket_min is None or ticket_max is None:
        parsed_min, parsed_max, _currency, _snippet, _confidence = extract_money_range(
            " ".join([*draft.funding_lines, draft.ideal_range or ""]),
            default_currency=funder.currency,
        )
        ticket_min = ticket_min if ticket_min is not None else parsed_min
        ticket_max = ticket_max if ticket_max is not None else parsed_max

    secondary_payload = [
        source.model_dump(mode="json")
        for source in secondary_sources
        if source.url != source_url
    ]
    extraction_notes = unique_preserve_order(
        [
            draft.extraction_notes or "",
            "extracted_from_search=true",
            "source_type=%s" % (draft.source_type or "official_website"),
            "confidence_score=%s" % draft.confidence_score,
            "web_search_query=%s" % (draft.query or ""),
            *(
                ["is_sub_programme=true; parent_program_name=%s" % draft.parent_program_name]
                if draft.is_sub_programme and draft.parent_program_name
                else []
            ),
        ]
    )
    raw_text_snippets: Dict[str, List[str]] = {
        "web_search_metadata": unique_preserve_order(
            [
                "source_type=%s" % (draft.source_type or "official_website"),
                "extracted_from_search=true",
                "confidence_score=%s" % draft.confidence_score,
                *("ideal_range=%s" % draft.ideal_range for _ in [0] if draft.ideal_range),
                *("secondary_sources=%s" % secondary_payload for _ in [0] if secondary_payload),
            ]
        ),
        "raw_eligibility_criteria": list(draft.raw_eligibility_criteria),
        "raw_repayment_terms": list(draft.raw_repayment_terms),
        "application_process": [draft.application_process] if draft.application_process else [],
    }
    raw_text_snippets = {key: value for key, value in raw_text_snippets.items() if value}

    record = FundingProgrammeRecord(
        program_name=draft.program_name,
        funder_name=funder.funder_name,
        country_code=funder.country_code,
        status=ProgrammeStatus.UNKNOWN,
        site_adapter="web_search",
        page_type="funding_programme",
        page_role="funding_detail",
        parent_programme_name=draft.parent_program_name,
        source_url=source_url,
        source_urls=unique_preserve_order([source_url, *[source.url for source in secondary_sources]]),
        source_domain=source_domain,
        source_page_title=draft.source_title,
        source_scope="web_search",
        scraped_at=now,
        created_at=now,
        updated_at=now,
        last_scraped_at=now,
        raw_eligibility_data=list(draft.raw_eligibility_criteria) or None,
        raw_eligibility_criteria=list(draft.raw_eligibility_criteria),
        raw_funding_offer_data=list(draft.funding_lines),
        raw_terms_data=list(draft.raw_repayment_terms),
        raw_documents_data=list(draft.required_documents),
        raw_application_data=[draft.application_process] if draft.application_process else [],
        funding_type=funding_type,
        funding_lines=list(draft.funding_lines),
        ticket_min=ticket_min,
        ticket_max=ticket_max,
        currency=draft.currency or funder.currency,
        geography_scope=GeographyScope.UNKNOWN,
        industries=list(draft.sector_focus),
        use_of_funds=list(draft.funding_lines),
        business_stage_eligibility=list(draft.target_applicants),
        payback_raw_text="; ".join(draft.raw_repayment_terms) or None,
        repayment_frequency=RepaymentFrequency.UNKNOWN,
        required_documents=list(draft.required_documents),
        application_channel=ApplicationChannel.MANUAL_CONTACT_FIRST if draft.application_process else ApplicationChannel.UNKNOWN,
        raw_text_snippets=raw_text_snippets,
        evidence_by_field={
            "source_url": [source_url],
            "source_page_title": [draft.source_title] if draft.source_title else [],
            "funding_lines": list(draft.funding_lines),
            "raw_eligibility_criteria": list(draft.raw_eligibility_criteria),
            "required_documents": list(draft.required_documents),
            "web_search_metadata": raw_text_snippets.get("web_search_metadata", []),
        },
        extraction_confidence={
            "program_name": confidence,
            "source_url": confidence,
            "funding_type": confidence if funding_type != FundingType.UNKNOWN else min(confidence, 0.55),
            "ticket_min": confidence if ticket_min is not None else 0.0,
            "ticket_max": confidence if ticket_max is not None else 0.0,
            "raw_eligibility_criteria": confidence if draft.raw_eligibility_criteria else 0.0,
            "required_documents": confidence if draft.required_documents else 0.0,
        },
        related_documents=[source.url for source in secondary_sources if source.source_type == "official_document"],
        notes=extraction_notes,
        ai_enriched=True,
        needs_review=draft.confidence_score < 70,
        needs_review_reasons=["web_search_confidence_below_70"] if draft.confidence_score < 70 else [],
    )
    return FundingProgrammeRecord.model_validate(record.model_dump(mode="python"))


def _classify_funding_type(draft: WebSearchProgrammeDraft) -> FundingType:
    explicit = clean_text(draft.funding_type or "")
    for value in FundingType:
        if explicit.casefold() == value.value.casefold():
            return value
    text = " ".join(
        [
            *draft.funding_lines,
            *draft.raw_repayment_terms,
            *draft.raw_eligibility_criteria,
            draft.extraction_notes or "",
        ]
    ).casefold()
    has_debt = any(term in text for term in FUNDING_TYPE_TERMS[FundingType.LOAN])
    has_equity = any(term in text for term in FUNDING_TYPE_TERMS[FundingType.EQUITY])
    if has_debt and has_equity:
        return FundingType.HYBRID
    if has_debt:
        return FundingType.LOAN
    if has_equity:
        return FundingType.EQUITY
    if any(term in text for term in FUNDING_TYPE_TERMS[FundingType.GRANT]):
        return FundingType.GRANT
    if any(term in text for term in FUNDING_TYPE_TERMS[FundingType.GUARANTEE]):
        return FundingType.GUARANTEE
    return FundingType.UNKNOWN


def _coerce_money_value(value: Any, default_currency: str) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    parsed = parse_money_token(str(value), default_currency=default_currency, require_context=False)
    return parsed.value if parsed else None
