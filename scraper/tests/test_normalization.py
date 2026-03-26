from __future__ import annotations

from scraper.classifiers.geography import classify_geography
from scraper.parsers.extractor_rules import CandidateBlock
from scraper.parsers.normalization import build_programme_record
from scraper.utils.text import generate_program_id


def test_program_id_is_stable() -> None:
    first = generate_program_id("example.org", "Growth Finance Agency", "Youth Growth Loan")
    second = generate_program_id("example.org", "Growth Finance Agency", "Youth Growth Loan")
    assert first == second
    assert first.startswith("funding_example-org_youth-growth-loan_")


def test_geography_classifier_maps_provinces_and_municipalities(settings) -> None:
    result = classify_geography(
        "Available in Gauteng, Western Cape, City of Cape Town, and eThekwini.",
        settings,
    )
    assert result["provinces"] == ["Gauteng", "Western Cape"]
    assert "City of Cape Town" in result["municipalities"]
    assert "eThekwini" in result["municipalities"]


def test_build_programme_record_maps_security_equity_and_funding_type(settings) -> None:
    block = CandidateBlock(
        heading="Township Growth Loan",
        text=(
            "A working capital loan for township enterprises. Loan sizes range from R500k to R5m. "
            "Applications are considered on a rolling basis. No collateral is required. Loan only with no dilution. "
            "Monthly repayments apply over 12 to 24 months."
        ),
        source_url="https://example.org/programmes/township-growth-loan",
        application_links=["https://example.org/apply/township-growth-loan"],
    )
    record, _evidence = build_programme_record(
        block=block,
        page_url="https://example.org/programmes/township-growth-loan",
        page_title="Township Growth Loan - Example Funder",
        settings=settings,
    )
    assert record is not None
    assert record.funding_type.value == "Loan"
    assert record.security_required.value == "No"
    assert record.equity_required.value == "No"
    assert record.deadline_type.value == "Rolling"
    assert record.application_channel.value == "Online form"
    assert record.ticket_min == 500000
    assert record.ticket_max == 5000000


def test_build_programme_record_ignores_support_section_heading_as_program_name(settings) -> None:
    block = CandidateBlock(
        heading="4. ELIGIBILITY CRITERIA TTF",
        text=(
            "Funding applications must adhere to the following: commercial viability, legal compliance, "
            "and black ownership requirements."
        ),
        source_url="https://www.nefcorp.co.za/products-services/tourism-transformation-fund/programme-guidelines",
    )
    record, _evidence = build_programme_record(
        block=block,
        page_url="https://www.nefcorp.co.za/products-services/tourism-transformation-fund/programme-guidelines",
        page_title="Programme guidelines - Tourism Transformation Fund",
        settings=settings,
    )
    assert record is not None
    assert record.program_name == "Tourism Transformation Fund"


def test_build_programme_record_classifies_debt_quasi_equity_and_equity_as_hybrid(settings) -> None:
    block = CandidateBlock(
        heading="iMbewu Fund",
        text=(
            "This Fund supports black entrepreneurs wishing to start new businesses and existing black-owned "
            "enterprises with expansion capital. The fund offers debt, quasi-equity and equity finance products."
        ),
        source_url="https://www.nefcorp.co.za/products-services/imbewu-fund",
    )
    record, _evidence = build_programme_record(
        block=block,
        page_url="https://www.nefcorp.co.za/products-services/imbewu-fund",
        page_title="iMbewu Fund - National Empowerment Fund",
        settings=settings,
    )
    assert record is not None
    assert record.funding_type.value == "Hybrid"
