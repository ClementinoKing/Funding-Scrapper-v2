from __future__ import annotations

from datetime import datetime, timezone

from scraper.schemas import FundingProgrammeRecord, FundingType
from scraper.utils.page_classification import (
    classify_global_page_type,
    mark_review_reasons,
    should_persist_record,
)


def test_global_page_classification_covers_expected_types() -> None:
    cases = {
        "funding_programme": "Growth Fund eligibility criteria application loan amount R1 million",
        "funding_listing": "Funding products Green Grant Youth Loan Asset Finance",
        "support_programme": "Business mentorship training and advisory support for entrepreneurs",
        "technology_station": "Technology station offers prototype support and technical assistance",
        "open_call": "Open call for applications with grant startup capital",
        "tender_procurement": "Tender number RFP 2025 procurement appointment of service provider",
        "news_article": "News article published on Monday announced a new programme",
        "generic_content": "About us contact privacy overview",
    }
    assert classify_global_page_type(text=cases["funding_programme"], application_link_count=1) == "funding_programme"
    assert classify_global_page_type(text=cases["funding_listing"], record_count=2, candidate_block_count=2) == "funding_listing"
    assert classify_global_page_type(text=cases["support_programme"]) == "support_programme"
    assert classify_global_page_type(text=cases["technology_station"]) == "technology_station"
    assert classify_global_page_type(text=cases["open_call"]) == "open_call"
    assert classify_global_page_type(text=cases["tender_procurement"]) == "tender_procurement"
    assert classify_global_page_type(text=cases["news_article"]) == "news_article"
    assert classify_global_page_type(text=cases["generic_content"]) == "generic_content"


def test_persistence_gate_rejects_tender_but_accepts_fundable_open_call() -> None:
    tender = FundingProgrammeRecord(
        program_name="RFP 2025 Appointment of a Service Provider",
        funder_name="Example Agency",
        source_url="https://example.org/tenders/rfp-2025",
        source_domain="example.org",
        scraped_at=datetime.now(timezone.utc),
        funding_type=FundingType.UNKNOWN,
        page_type="tender_procurement",
    )
    assert should_persist_record(tender)[0] is False

    open_call = FundingProgrammeRecord(
        program_name="Innovation Open Call",
        funder_name="Example Agency",
        source_url="https://example.org/open-call",
        source_domain="example.org",
        scraped_at=datetime.now(timezone.utc),
        funding_type=FundingType.GRANT,
        page_type="open_call",
    )
    assert should_persist_record(open_call)[0] is True


def test_review_reasons_mark_unknown_funding_and_tender_titles() -> None:
    record = FundingProgrammeRecord(
        program_name="Tender T2025/004 Supply and Delivery",
        funder_name="Example Agency",
        source_url="https://example.org/funding/tender",
        source_domain="example.org",
        scraped_at=datetime.now(timezone.utc),
        funding_type=FundingType.UNKNOWN,
        page_type="funding_listing",
    )
    marked = mark_review_reasons(record)
    assert marked.needs_review is True
    assert any("funding_type is Unknown" in reason for reason in marked.validation_errors)
    assert any("tender title" in reason for reason in marked.validation_errors)
