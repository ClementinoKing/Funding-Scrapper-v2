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


def test_generic_parser_extracts_clean_content_and_sections(settings, fixture_dir: Path) -> None:
    parser = GenericFundingParser(settings)
    html = (fixture_dir / "single_program.html").read_text(encoding="utf-8")
    page = _page(
        "https://example.org/programmes/green-energy-sme-grant",
        html,
        "Green Energy SME Grant - National Empowerment Fund",
    )

    result = parser.parse(page, allowed_domains=["example.org"])

    assert result.page_url == "https://example.org/programmes/green-energy-sme-grant"
    assert result.title == "Green Energy SME Grant - National Empowerment Fund"
    assert result.headings[:3] == ["Green Energy SME Grant", "Eligibility", "Funding Offer"]
    assert "grant funding to qualifying SMEs" in result.full_body_text
    assert any(section.heading == "Eligibility" for section in result.structured_sections)
    assert any("business plan" in section.content.lower() for section in result.structured_sections)
    assert result.application_links == ["https://example.org/apply/green-energy-sme-grant"]
    assert any(document.endswith(".pdf") for document in result.document_links)


def test_generic_parser_keeps_listing_pages_generic(settings, fixture_dir: Path) -> None:
    parser = GenericFundingParser(settings)
    html = (fixture_dir / "multi_program_listing.html").read_text(encoding="utf-8")
    page = _page(
        "https://example.org/funding-products",
        html,
        "Funding Products - Growth Finance Agency",
    )

    result = parser.parse(page, allowed_domains=["example.org"])

    assert result.title == "Funding Products - Growth Finance Agency"
    assert result.headings == ["Youth Growth Loan", "Asset Finance Facility"]
    assert "working capital loan for youth-owned businesses" in result.full_body_text.lower()
    assert "https://example.org/programmes/youth-growth-loan" in result.discovered_links
    assert "https://example.org/programmes/asset-finance-facility" in result.discovered_links
