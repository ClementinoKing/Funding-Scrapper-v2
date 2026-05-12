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


def test_dedupe_groups_related_support_fragments_into_programme_record() -> None:
    detail = FundingProgrammeRecord(
        program_name="Green Growth Fund",
        funder_name="Example Agency",
        source_url="https://example.org/programmes/green-growth-fund",
        source_urls=["https://example.org/programmes/green-growth-fund"],
        source_domain="example.org",
        source_page_title="Green Growth Fund",
        scraped_at=datetime.now(timezone.utc),
        funding_type=FundingType.GRANT,
        page_type="funding_programme",
        ticket_max=1000000,
    )
    eligibility = FundingProgrammeRecord(
        program_name="Eligibility",
        funder_name="Example Agency",
        parent_programme_name="Green Growth Fund",
        source_url="https://example.org/programmes/green-growth-fund/eligibility",
        source_urls=["https://example.org/programmes/green-growth-fund/eligibility"],
        source_domain="example.org",
        source_page_title="Eligibility - Green Growth Fund",
        scraped_at=datetime.now(timezone.utc),
        funding_type=FundingType.UNKNOWN,
        page_type="support_programme",
        raw_eligibility_data=["SMEs must be registered and tax compliant."],
    )
    documents = FundingProgrammeRecord(
        program_name="Required Documents",
        funder_name="Example Agency",
        parent_programme_name="Green Growth Fund",
        source_url="https://example.org/programmes/green-growth-fund/documents",
        source_urls=["https://example.org/programmes/green-growth-fund/documents"],
        source_domain="example.org",
        source_page_title="Required Documents - Green Growth Fund",
        scraped_at=datetime.now(timezone.utc),
        funding_type=FundingType.UNKNOWN,
        page_type="support_programme",
        required_documents=["Tax clearance certificate"],
    )

    deduped = dedupe_records([detail, eligibility, documents])

    assert len(deduped) == 1
    merged = deduped[0]
    assert merged.program_name == "Green Growth Fund"
    assert merged.page_type == "funding_programme"
    assert len(merged.source_urls) == 3
    assert "SMEs must be registered and tax compliant." in (merged.raw_eligibility_data or [])
    assert "Tax clearance certificate" in merged.required_documents


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


def test_dedupe_does_not_merge_same_named_programmes_from_different_parent_programmes() -> None:
    left = FundingProgrammeRecord(
        program_name="Expansion Capital",
        funder_name="National Empowerment Fund",
        parent_programme_name="Umnotho Fund",
        source_url="https://www.nefcorp.co.za/products-services/umnotho-fund/3-expansion-capital",
        source_urls=["https://www.nefcorp.co.za/products-services/umnotho-fund/3-expansion-capital"],
        source_domain="nefcorp.co.za",
        source_page_title="3. Expansion Capital - Umnotho Fund",
        scraped_at=datetime.now(timezone.utc),
        funding_type=FundingType.LOAN,
    )
    right = FundingProgrammeRecord(
        program_name="Expansion Capital",
        funder_name="National Empowerment Fund",
        parent_programme_name="Rural Community Development Fund",
        source_url="https://www.nefcorp.co.za/products-services/rural-community-development-fund/3-expansion-capital",
        source_urls=["https://www.nefcorp.co.za/products-services/rural-community-development-fund/3-expansion-capital"],
        source_domain="nefcorp.co.za",
        source_page_title="3. Expansion Capital - Rural Community Development Fund",
        scraped_at=datetime.now(timezone.utc),
        funding_type=FundingType.LOAN,
    )

    deduped = dedupe_records([left, right])

    assert len(deduped) == 2
    assert {record.parent_programme_name for record in deduped} == {
        "Umnotho Fund",
        "Rural Community Development Fund",
    }


def test_dedupe_does_not_merge_same_named_programmes_when_parent_context_is_only_in_source_url() -> None:
    left = FundingProgrammeRecord(
        program_name="Expansion Capital",
        funder_name="National Empowerment Fund",
        source_url="https://www.nefcorp.co.za/products-services/umnotho-fund/3-expansion-capital",
        source_urls=["https://www.nefcorp.co.za/products-services/umnotho-fund/3-expansion-capital"],
        source_domain="nefcorp.co.za",
        source_page_title="3. Expansion Capital - Umnotho Fund",
        scraped_at=datetime.now(timezone.utc),
        funding_type=FundingType.LOAN,
    )
    right = FundingProgrammeRecord(
        program_name="Expansion Capital",
        funder_name="National Empowerment Fund",
        source_url="https://www.nefcorp.co.za/products-services/rural-community-development-fund/3-expansion-capital",
        source_urls=["https://www.nefcorp.co.za/products-services/rural-community-development-fund/3-expansion-capital"],
        source_domain="nefcorp.co.za",
        source_page_title="3. Expansion Capital - Rural Community Development Fund",
        scraped_at=datetime.now(timezone.utc),
        funding_type=FundingType.LOAN,
    )

    deduped = dedupe_records([left, right])

    assert len(deduped) == 2
    assert {record.program_name for record in deduped} == {"Expansion Capital"}


def test_dedupe_can_use_ai_decider_to_keep_ambiguous_same_named_programmes_separate() -> None:
    left = FundingProgrammeRecord(
        program_name="Expansion Capital",
        funder_name="National Empowerment Fund",
        source_url="https://example.org/expansion-capital",
        source_urls=["https://example.org/expansion-capital"],
        source_domain="example.org",
        source_page_title="Expansion Capital",
        scraped_at=datetime.now(timezone.utc),
        funding_type=FundingType.LOAN,
    )
    right = FundingProgrammeRecord(
        program_name="Expansion Capital",
        funder_name="National Empowerment Fund",
        source_url="https://example.org/expansion-capital-terms",
        source_urls=["https://example.org/expansion-capital-terms"],
        source_domain="example.org",
        source_page_title="Expansion Capital Terms",
        scraped_at=datetime.now(timezone.utc),
        funding_type=FundingType.LOAN,
    )

    class _RejectingDecider:
        def should_merge_records(self, _left, _right):
            return False

    deduped = dedupe_records([left, right], merge_decider=_RejectingDecider())

    assert len(deduped) == 2


def test_dedupe_keeps_same_page_listing_child_programmes_separate() -> None:
    sme = FundingProgrammeRecord(
        program_name="SME Fund",
        funder_name="Public Investment Corporation",
        source_url="https://www.pic.gov.za/isibaya",
        source_urls=["https://www.pic.gov.za/isibaya"],
        source_domain="pic.gov.za",
        source_page_title="Isibaya Fund",
        scraped_at=datetime.now(timezone.utc),
        funding_type=FundingType.EQUITY,
        page_type="funding_listing",
        raw_funding_offer_data=["Equity investment funding for growing small and medium businesses."],
    )
    housing = FundingProgrammeRecord(
        program_name="Affordable Housing Fund",
        funder_name="Public Investment Corporation",
        source_url="https://www.pic.gov.za/isibaya",
        source_urls=["https://www.pic.gov.za/isibaya"],
        source_domain="pic.gov.za",
        source_page_title="Isibaya Fund",
        scraped_at=datetime.now(timezone.utc),
        funding_type=FundingType.EQUITY,
        page_type="funding_listing",
        raw_funding_offer_data=["Investment funding for affordable and social housing projects."],
    )

    deduped = dedupe_records([sme, housing])

    assert len(deduped) == 2
    assert {record.program_name for record in deduped} == {"SME Fund", "Affordable Housing Fund"}
