from __future__ import annotations

from bs4 import BeautifulSoup

from scraper.parsers.extractor_rules import CandidateBlock, extract_application_links
from scraper.classifiers.geography import classify_geography
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


def test_build_programme_record_falls_back_to_body_text_for_ticket_range_when_funding_section_is_requirements(settings) -> None:
    block = CandidateBlock(
        heading="Women Empowerment Fund (WEF)",
        text=(
            "The NEF Women Empowerment Fund is aimed at accelerating the provision of funding to businesses owned "
            "by black women. The funding starts from R250 000 to R75 million across a range of sectors. "
            "Funding requirements: Minimum of 51% black female ownership."
        ),
        source_url="https://www.nefcorp.co.za/products-services/women-empowerment-fund",
        section_map={
            "Funding requirements": [
                "Minimum of 51% black female ownership.",
            ]
        },
    )
    record, _evidence = build_programme_record(
        block=block,
        page_url="https://www.nefcorp.co.za/products-services/women-empowerment-fund",
        page_title="Women Empowerment Fund (WEF) - National Empowerment Fund",
        settings=settings,
    )
    assert record is not None
    assert record.ticket_min == 250000
    assert record.ticket_max == 75000000
    assert record.currency == "ZAR"


def test_build_programme_record_extracts_payback_terms(settings) -> None:
    block = CandidateBlock(
        heading="Growth Loan",
        text=(
            "Loan term of up to 5 years. A 3 month grace period applies and the facility is repaid in monthly instalments."
        ),
        source_url="https://example.org/programmes/growth-loan",
    )
    record, _evidence = build_programme_record(
        block=block,
        page_url="https://example.org/programmes/growth-loan",
        page_title="Growth Loan - Example Funder",
        settings=settings,
    )

    assert record is not None
    assert record.payback_raw_text is not None
    assert "5 years" in record.payback_raw_text
    assert record.payback_months_min is None
    assert record.payback_months_max == 60
    assert record.payback_term_min_months is None
    assert record.payback_term_max_months == 60
    assert record.payback_structure == "monthly instalments"
    assert record.grace_period_months == 3
    assert record.repayment_frequency.value == "Monthly"
    assert record.payback_confidence > 0


def test_build_programme_record_extracts_clean_eligibility_criteria(settings) -> None:
    block = CandidateBlock(
        heading="Growth Loan",
        text=(
            "Eligibility Criteria: The business must be majority black-owned; the applicant must submit a completed application form. "
            "The enterprise must demonstrate commercial viability and sustainability. "
            "Loan term of up to 60 months. Contact us on email."
        ),
        source_url="https://example.org/programmes/growth-loan",
        section_map={
            "Eligibility Criteria": [
                "The business must be majority black-owned; the applicant must submit a completed application form.",
                "The enterprise must demonstrate commercial viability and sustainability.",
            ],
            "Compliance Requirements": [
                "The applicant must provide valid registration documents and tax clearance.",
            ],
            "Terms and Conditions": [
                "Loan term of up to 60 months.",
                "Contact us on email.",
            ],
        },
    )
    record, _evidence = build_programme_record(
        block=block,
        page_url="https://example.org/programmes/growth-loan",
        page_title="Growth Loan - Example Funder",
        settings=settings,
    )

    assert record is not None
    assert record.raw_eligibility_criteria == [
        "The business must be majority black-owned",
        "the applicant must submit a completed application form.",
        "The enterprise must demonstrate commercial viability and sustainability.",
        "The applicant must provide valid registration documents and tax clearance.",
    ]
    assert "Loan term of up to 60 months" not in " ".join(record.raw_eligibility_criteria)


def test_extract_application_links_ignores_document_downloads() -> None:
    soup = BeautifulSoup(
        """
        <div>
          <a href="/wp-content/uploads/2018/07/Funding-Application-Forms.pdf">Application Form</a>
          <a href="https://online.nefcorp.co.za">The NEF Application Portal</a>
        </div>
        """,
        "html.parser",
    )

    links = extract_application_links(soup, "https://www.nefcorp.co.za/products-services/women-empowerment-fund")

    assert links == ["https://online.nefcorp.co.za"]


def test_build_programme_record_prefers_live_application_portal_over_dead_pdf(settings) -> None:
    block = CandidateBlock(
        heading="Women Empowerment Fund (WEF)",
        text=(
            "The NEF Women Empowerment Fund supports black women-owned businesses. "
            "See the application portal for online submissions."
        ),
        source_url="https://www.nefcorp.co.za/products-services/women-empowerment-fund",
        application_links=[
            "https://www.nefcorp.co.za/wp-content/uploads/2018/07/Funding-Application-Forms.pdf",
            "https://online.nefcorp.co.za",
        ],
    )

    record, _evidence = build_programme_record(
        block=block,
        page_url="https://www.nefcorp.co.za/products-services/women-empowerment-fund",
        page_title="Women Empowerment Fund (WEF) - National Empowerment Fund",
        settings=settings,
    )

    assert record is not None
    assert record.application_channel.value == "Online form"
    assert record.application_url == "https://online.nefcorp.co.za"
