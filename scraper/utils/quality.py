"""Programme quality scoring and acceptance gates."""

from __future__ import annotations

from datetime import date, datetime, timezone
from urllib.parse import urlparse
from typing import List, Tuple

from scraper.schemas import FundingProgrammeRecord, FundingType, DeadlineType, ApplicationChannel
from scraper.utils.text import unique_preserve_order


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

PUBLICATION_NOTE_TERMS = (
    "article/publication page",
    "article or publication page",
    "press release",
    "media release",
    "news article",
    "publication",
    "success story",
    "case study",
)


def _has_text(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(_has_text(item) for item in value)
    return True


def _normalize_date(value: date | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)


def _looks_like_article_or_publication(record: FundingProgrammeRecord) -> bool:
    source_url = (record.source_url or "").lower()
    source_title = (record.source_page_title or "").lower()
    note_text = " ".join(record.notes or []).lower()
    path = urlparse(record.source_url or "").path.lower()

    haystack = " ".join([source_url, source_title, note_text, path])
    if any(term in haystack for term in PUBLICATION_NOTE_TERMS):
        return True
    return any(term in path for term in PUBLICATION_PATH_TERMS) or any(term in source_title for term in PUBLICATION_PATH_TERMS)


def score_programme_quality(record: FundingProgrammeRecord) -> Tuple[int, List[str], List[str]]:
    score = 0
    reasons: List[str] = []
    blockers: List[str] = []

    if _looks_like_article_or_publication(record):
        score -= 10

    if _has_text(record.program_name):
        score += 18
        reasons.append("Has programme name")
    else:
        blockers.append("Missing programme name")

    if _has_text(record.funder_name):
        score += 14
        reasons.append("Has funder name")
    else:
        blockers.append("Missing funder name")

    if record.funding_type != FundingType.UNKNOWN:
        score += 10
        reasons.append("Known funding type")
    else:
        blockers.append("Unknown funding type")

    if record.ticket_min is not None or record.ticket_max is not None or record.program_budget_total is not None:
        score += 10
        reasons.append("Funding amount captured")

    if record.application_channel != ApplicationChannel.UNKNOWN:
        score += 10
        reasons.append("Application route available")
    elif record.application_url or record.contact_email or record.contact_phone:
        score += 8
        reasons.append("Contact route available")
    else:
        score -= 4

    if record.raw_eligibility_data or record.entity_types_allowed or record.certifications_required or record.business_stage_eligibility:
        score += 10
        reasons.append("Eligibility details captured")

    if record.industries or record.use_of_funds or record.funding_lines:
        score += 8
        reasons.append("Use of funds or industry captured")

    if record.ownership_targets:
        score += 5
        reasons.append("Ownership target captured")

    if record.provinces or record.municipalities or record.geography_scope != record.geography_scope.UNKNOWN:
        score += 4
        reasons.append("Geography captured")

    if record.related_documents:
        score += 3
        reasons.append("Supporting documents linked")

    if record.deadline_type in {DeadlineType.OPEN, DeadlineType.ROLLING}:
        score += 8
        reasons.append("Open or rolling deadline")
    elif record.deadline_date is not None:
        deadline = _normalize_date(record.deadline_date)
        if deadline and deadline < datetime.now(timezone.utc):
            score -= 18
            blockers.append("Expired fixed deadline")
        else:
            score += 5
            reasons.append("Future deadline available")

    if any("archived" in note.lower() or "closed" in note.lower() for note in record.notes):
        score -= 20
        blockers.append("Archived or closed programme")

    if record.overall_confidence() < 0.25:
        score -= 10
        blockers.append("Very low extraction confidence")
    elif record.overall_confidence() >= 0.6:
        score += 4
        reasons.append("High extraction confidence")

    completeness_signals = sum(
        1
        for value in [
            record.program_name,
            record.funder_name,
            record.funding_type != FundingType.UNKNOWN,
            record.ticket_min is not None or record.ticket_max is not None,
            record.application_channel != ApplicationChannel.UNKNOWN or record.application_url or record.contact_email or record.contact_phone,
            record.raw_eligibility_data,
            record.industries,
            record.use_of_funds,
        ]
        if _has_text(value)
    )

    if completeness_signals <= 2:
        score -= 10

    return max(0, min(100, score)), unique_preserve_order(reasons), unique_preserve_order(blockers)


def is_real_programme_record(record: FundingProgrammeRecord, accept_threshold: int = 45) -> bool:
    score, _reasons, blockers = score_programme_quality(record)
    if score < accept_threshold:
        return False
    if "Missing programme name" in blockers or "Missing funder name" in blockers:
        return False
    return True


def is_borderline_programme_record(
    record: FundingProgrammeRecord,
    accept_threshold: int = 45,
    review_threshold: int = 25,
) -> bool:
    score, _reasons, blockers = score_programme_quality(record)
    if "Article or publication page" in blockers:
        return score >= review_threshold
    return review_threshold <= score < accept_threshold
