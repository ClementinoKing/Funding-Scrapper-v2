from __future__ import annotations

from pathlib import Path

from scraper.parsers.generic_parser import GenericFundingParser
from scraper.schemas import PageFetchResult


def _page(url: str, html: str, title: str) -> PageFetchResult:
    return PageFetchResult(
        url=url,
        requested_url=url,
        canonical_url=url,
        final_url=url,
        status_code=200,
        content_type="text/html",
        html=html,
        title=title,
        fetch_method="http",
        headers={},
        js_rendered=False,
        notes=[],
    )


def test_generic_parser_extracts_single_programme(settings, fixture_dir: Path) -> None:
    parser = GenericFundingParser(settings)
    html = (fixture_dir / "single_program.html").read_text(encoding="utf-8")
    page = _page(
        "https://example.org/programmes/green-energy-sme-grant",
        html,
        "Green Energy SME Grant - National Empowerment Fund",
    )

    result = parser.parse(page, allowed_domains=["example.org"])

    assert result.records
    record_names = {record.program_name for record in result.records}
    assert "Green Energy SME Grant" in record_names
    programme = next(record for record in result.records if record.program_name == "Green Energy SME Grant")
    assert programme.funding_type.value == "Grant"
    assert programme.application_url == "https://example.org/apply/green-energy-sme-grant"
    assert programme.raw_eligibility_data
    assert any(document.endswith(".pdf") for document in programme.related_documents)


def test_generic_parser_extracts_multiple_programmes_and_links(settings, fixture_dir: Path) -> None:
    parser = GenericFundingParser(settings)
    html = (fixture_dir / "multi_program_listing.html").read_text(encoding="utf-8")
    page = _page(
        "https://example.org/funding-products",
        html,
        "Funding Products - Growth Finance Agency",
    )

    result = parser.parse(page, allowed_domains=["example.org"])

    record_names = {record.program_name for record in result.records if record.program_name}
    assert "Youth Growth Loan" in record_names
    assert "Asset Finance Facility" in record_names
    assert "https://example.org/programmes/youth-growth-loan" in result.discovered_links
    assert "https://example.org/programmes/asset-finance-facility" in result.discovered_links

