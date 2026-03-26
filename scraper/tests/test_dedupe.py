from __future__ import annotations

from datetime import datetime, timezone

from scraper.schemas import ApplicationChannel, FundingProgrammeRecord, FundingType
from scraper.utils.dedupe import dedupe_records


def _record(source_url: str, source_urls, notes, ticket_max=None, application_url=None) -> FundingProgrammeRecord:
    return FundingProgrammeRecord(
        program_name="Youth Growth Loan",
        funder_name="Growth Finance Agency",
        source_url=source_url,
        source_urls=source_urls,
        source_domain="example.org",
        source_page_title="Youth Growth Loan - Growth Finance Agency",
        scraped_at=datetime.now(timezone.utc),
        funding_type=FundingType.LOAN,
        ticket_max=ticket_max,
        application_channel=ApplicationChannel.ONLINE_FORM if application_url else ApplicationChannel.UNKNOWN,
        application_url=application_url,
        notes=notes,
    )


def test_dedupe_merges_records_and_preserves_sources() -> None:
    records = [
        _record(
            "https://example.org/programmes/youth-growth-loan",
            ["https://example.org/programmes/youth-growth-loan"],
            ["Listing page record"],
        ),
        _record(
            "https://example.org/programmes/youth-growth-loan?utm_source=test",
            ["https://example.org/programmes/youth-growth-loan?utm_source=test"],
            ["Detail page record"],
            ticket_max=5000000,
            application_url="https://example.org/apply/youth-growth-loan",
        ),
    ]

    deduped = dedupe_records(records)
    assert len(deduped) == 1
    merged = deduped[0]
    assert merged.ticket_max == 5000000
    assert len(merged.source_urls) == 2
    assert "Listing page record" in merged.notes
    assert "Detail page record" in merged.notes
    assert merged.application_url == "https://example.org/apply/youth-growth-loan"


def test_dedupe_normalizes_inverted_ticket_ranges() -> None:
    records = [
        _record(
            "https://example.org/programmes/youth-growth-loan",
            ["https://example.org/programmes/youth-growth-loan"],
            ["Listing page record"],
            ticket_max=5000000,
        ),
        FundingProgrammeRecord(
            program_name="Youth Growth Loan",
            funder_name="Growth Finance Agency",
            source_url="https://example.org/programmes/youth-growth-loan-terms",
            source_urls=["https://example.org/programmes/youth-growth-loan-terms"],
            source_domain="example.org",
            source_page_title="Youth Growth Loan Terms - Growth Finance Agency",
            scraped_at=datetime.now(timezone.utc),
            funding_type=FundingType.LOAN,
            ticket_min=5000000,
            ticket_max=500000,
        ),
    ]

    deduped = dedupe_records(records)
    assert len(deduped) == 1
    merged = deduped[0]
    assert merged.ticket_min == 500000
    assert merged.ticket_max == 5000000


def test_dedupe_keeps_ttf_support_pages_under_the_parent_programme() -> None:
    parent = FundingProgrammeRecord(
        program_name="Tourism Transformation Fund",
        funder_name="National Empowerment Fund",
        source_url="https://www.nefcorp.co.za/products-services/tourism-transformation-fund",
        source_urls=["https://www.nefcorp.co.za/products-services/tourism-transformation-fund"],
        source_domain="nefcorp.co.za",
        source_page_title="Tourism Transformation Fund - National Empowerment Fund",
        scraped_at=datetime.now(timezone.utc),
        funding_type=FundingType.HYBRID,
        required_documents=["https://www.nefcorp.co.za/products-services/tourism-transformation-fund/checklist.pdf"],
    )
    support = FundingProgrammeRecord(
        program_name="TTF Checklist",
        funder_name="National Empowerment Fund",
        parent_programme_name="Tourism Transformation Fund",
        source_url="https://www.nefcorp.co.za/products-services/tourism-transformation-fund/programme-guidelines",
        source_urls=["https://www.nefcorp.co.za/products-services/tourism-transformation-fund/programme-guidelines"],
        source_domain="nefcorp.co.za",
        source_page_title="Programme guidelines - Tourism Transformation Fund",
        scraped_at=datetime.now(timezone.utc),
        funding_type=FundingType.HYBRID,
        raw_eligibility_data=["Commercial viability required", "Black ownership required"],
    )
    sibling = FundingProgrammeRecord(
        program_name="Entrepreneurship Finance",
        funder_name="National Empowerment Fund",
        parent_programme_name="Tourism Transformation Fund",
        source_url="https://www.nefcorp.co.za/products-services/tourism-transformation-fund/entrepreneurship-finance",
        source_urls=["https://www.nefcorp.co.za/products-services/tourism-transformation-fund/entrepreneurship-finance"],
        source_domain="nefcorp.co.za",
        source_page_title="Entrepreneurship Finance - Tourism Transformation Fund",
        scraped_at=datetime.now(timezone.utc),
        funding_type=FundingType.HYBRID,
    )

    deduped = dedupe_records([parent, support, sibling])

    assert len(deduped) == 3
    assert {record.program_name for record in deduped} == {
        "Tourism Transformation Fund",
        "TTF Checklist",
        "Entrepreneurship Finance",
    }
    assert any(
        record.program_name == "TTF Checklist" and "Commercial viability required" in record.raw_eligibility_data
        for record in deduped
    )
