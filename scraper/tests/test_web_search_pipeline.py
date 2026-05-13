from __future__ import annotations

import json
from datetime import datetime, timezone

from typer.testing import CliRunner

from scraper.config import ScraperSettings
from scraper.main import app
from scraper.schemas import RunSummary
from scraper.storage.site_repository import SiteDefinition
from scraper.utils.money import parse_money_token
from scraper.web_search.mapper import draft_to_record
from scraper.web_search.models import WebSearchExtractionResponse, WebSearchFunder, WebSearchProgrammeDraft, WebSearchSource
from scraper.web_search.pipeline import WebSearchPipeline
from scraper.web_search.queries import generate_funder_queries


class FakeExtractor:
    def __init__(self, responses):
        self.responses = list(responses)
        self.queries: list[str] = []

    def extract(self, funder, query):
        self.queries.append(query)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_generate_funder_queries_uses_domain_and_funder_name_without_site_specific_branches() -> None:
    funders = [
        WebSearchFunder("SEFA", "https://www.sefa.org.za/products/direct-lending-products"),
        WebSearchFunder("IDC", "https://www.idc.co.za/"),
        WebSearchFunder("PIC", "https://www.pic.gov.za/"),
    ]

    query_sets = [generate_funder_queries(funder) for funder in funders]

    assert query_sets[0][0] == "site:sefa.org.za funding programmes"
    assert "site:idc.co.za investment products" in query_sets[1]
    assert '"PIC" application criteria' in query_sets[2]
    assert len({len(queries) for queries in query_sets}) == 1


def test_generate_funder_queries_prefers_programme_hints_when_available() -> None:
    funder = WebSearchFunder("PIC", "https://www.pic.gov.za/")

    queries = generate_funder_queries(funder, max_queries=3, programme_hints=["Isibaya Fund"])

    assert queries[0] == 'site:pic.gov.za "Isibaya Fund"'
    assert queries[1] == 'site:pic.gov.za "Isibaya Fund" funding'
    assert queries[2] == 'site:pic.gov.za "Isibaya Fund" application'


def test_web_search_mapper_preserves_source_metadata_and_sub_programme_hierarchy() -> None:
    funder = WebSearchFunder("SEFA", "https://www.sefa.org.za/products/direct-lending-products")
    draft = WebSearchProgrammeDraft(
        program_name="Bridging Loan",
        parent_program_name="Direct Lending",
        is_sub_programme=True,
        funding_type="Loan",
        funding_lines=["Funding from R50 million to R1bn for qualifying businesses."],
        ticket_min="R50 million",
        ticket_max="R1bn",
        ideal_range="R50 million to R1bn",
        currency="ZAR",
        raw_eligibility_criteria=["Registered South African SMEs may apply."],
        raw_repayment_terms=["Repayment over an agreed loan term."],
        required_documents=["Business plan", "Financial statements"],
        source_url="https://www.sefa.org.za/products/direct-lending-products",
        source_title="Direct Lending Products",
        source_type="official_website",
        confidence_score=91,
        extraction_notes="Official product page states the programme.",
        query="site:sefa.org.za funding products",
    )

    record = draft_to_record(
        draft,
        funder=funder,
        secondary_sources=[
            WebSearchSource(url="https://www.sefa.org.za/products/direct-lending-products", title="Direct Lending Products"),
            WebSearchSource(url="https://www.sefa.org.za/brochure.pdf", title="Brochure", source_type="official_document"),
        ],
    )

    assert record is not None
    assert record.program_name == "Bridging Loan"
    assert record.parent_programme_name == "Direct Lending"
    assert record.ticket_min == 50_000_000
    assert record.ticket_max == 1_000_000_000
    assert record.source_page_title == "Direct Lending Products"
    assert record.raw_text_snippets["web_search_metadata"]
    assert any("extracted_from_search=true" in note for note in record.notes)
    assert "https://www.sefa.org.za/brochure.pdf" in record.related_documents


def test_web_search_response_accepts_fractional_confidence_scores() -> None:
    response = WebSearchExtractionResponse.model_validate(
        {
            "programmes": [
                {
                    "program_name": "Isibaya Fund",
                    "source_url": "https://www.pic.gov.za/isibaya",
                    "source_title": "Isibaya",
                    "confidence_score": 0.86,
                }
            ]
        }
    )

    assert response.programmes[0].confidence_score == 86


def test_web_search_pipeline_skips_low_confidence_and_continues_after_funder_failure(tmp_path) -> None:
    settings = ScraperSettings(
        output_path=tmp_path,
        scraper_mode="web_search",
        web_search_max_queries_per_funder=1,
        web_search_min_insert_confidence=50,
    )
    accepted = WebSearchProgrammeDraft(
        program_name="Direct Lending",
        funding_type="Loan",
        source_url="https://www.sefa.org.za/products/direct-lending-products",
        source_title="Direct Lending Products",
        confidence_score=91,
    )
    low_confidence = WebSearchProgrammeDraft(
        program_name="Weak Programme",
        source_url="https://www.sefa.org.za/weak",
        source_title="Weak",
        confidence_score=40,
    )
    extractor = FakeExtractor(
        [
            (
                WebSearchExtractionResponse(programmes=[accepted, low_confidence]),
                [WebSearchSource(url="https://www.sefa.org.za/products/direct-lending-products", title="Direct Lending Products")],
            ),
            RuntimeError("search unavailable"),
        ]
    )
    pipeline = WebSearchPipeline(settings, extractor=extractor)

    summary = pipeline.run_funders(
        [
            WebSearchFunder("SEFA", "https://www.sefa.org.za/products/direct-lending-products", site_key="sefa"),
            WebSearchFunder("IDC", "https://www.idc.co.za/", site_key="idc"),
        ]
    )

    payload = json.loads((tmp_path / "normalized" / "funding_programmes.json").read_text(encoding="utf-8"))

    assert summary.status == "partial"
    assert summary.programmes_after_dedupe == 1
    assert summary.records_rejected_for_quality == 1
    assert summary.errors
    assert payload[0]["program_name"] == "Direct Lending"


def test_web_search_pipeline_keeps_records_found_before_later_query_failure(tmp_path) -> None:
    settings = ScraperSettings(
        output_path=tmp_path,
        scraper_mode="web_search",
        web_search_max_queries_per_funder=2,
        web_search_stop_after_success=False,
    )
    first_query_record = WebSearchProgrammeDraft(
        program_name="Isibaya Fund",
        source_url="https://www.pic.gov.za/isibaya",
        source_title="Isibaya",
        confidence_score=85,
    )
    extractor = FakeExtractor(
        [
            (
                WebSearchExtractionResponse(programmes=[first_query_record]),
                [WebSearchSource(url="https://www.pic.gov.za/isibaya", title="Isibaya")],
            ),
            RuntimeError("insufficient_quota"),
        ]
    )

    summary = WebSearchPipeline(settings, extractor=extractor).run_funders(
        [WebSearchFunder("PIC", "https://www.pic.gov.za/", site_key="pic")]
    )
    payload = json.loads((tmp_path / "normalized" / "funding_programmes.json").read_text(encoding="utf-8"))

    assert summary.status == "partial"
    assert summary.programmes_after_dedupe == 1
    assert summary.errors
    assert payload[0]["program_name"] == "Isibaya Fund"


def test_web_search_pipeline_dedupes_by_funder_programme_parent_and_source(tmp_path) -> None:
    settings = ScraperSettings(
        output_path=tmp_path,
        scraper_mode="web_search",
        web_search_max_queries_per_funder=2,
        web_search_stop_after_success=False,
    )
    lower = WebSearchProgrammeDraft(
        program_name="Direct Lending",
        source_url="https://www.sefa.org.za/products/direct-lending-products",
        source_title="Direct Lending",
        confidence_score=75,
    )
    higher = lower.model_copy(update={"confidence_score": 94, "extraction_notes": "Better official source details."})
    extractor = FakeExtractor(
        [
            (WebSearchExtractionResponse(programmes=[lower]), []),
            (WebSearchExtractionResponse(programmes=[higher]), []),
        ]
    )

    summary = WebSearchPipeline(settings, extractor=extractor).run_funders(
        [WebSearchFunder("SEFA", "https://www.sefa.org.za/products/direct-lending-products", site_key="sefa")]
    )
    payload = json.loads((tmp_path / "normalized" / "funding_programmes.json").read_text(encoding="utf-8"))

    assert summary.programmes_after_dedupe == 1
    assert payload[0]["extraction_confidence"]["program_name"] == 0.94


def test_web_search_pipeline_stops_after_first_success_by_default(tmp_path) -> None:
    settings = ScraperSettings(
        output_path=tmp_path,
        scraper_mode="web_search",
        web_search_max_queries_per_funder=4,
    )
    first_query_record = WebSearchProgrammeDraft(
        program_name="Direct Lending",
        source_url="https://www.sefa.org.za/products/direct-lending-products",
        source_title="Direct Lending",
        confidence_score=91,
    )
    extractor = FakeExtractor(
        [
            (WebSearchExtractionResponse(programmes=[first_query_record]), []),
            RuntimeError("second query should not run"),
        ]
    )

    summary = WebSearchPipeline(settings, extractor=extractor).run_funders(
        [WebSearchFunder("SEFA", "https://www.sefa.org.za/products/direct-lending-products", site_key="sefa")]
    )

    assert summary.status == "success"
    assert summary.total_urls_crawled == 1
    assert len(extractor.queries) == 1


def test_run_seeds_web_search_mode_does_not_construct_browser_fetcher(monkeypatch, tmp_path) -> None:
    class FailingBrowserFetcher:
        def __init__(self, *args, **kwargs):
            raise AssertionError("BrowserFetcher must not be constructed in web_search mode")

    class FakePipeline:
        def __init__(self, settings):
            self.settings = settings

        def run_funders(self, funders, max_funders=None):
            return RunSummary(
                run_id="run_test",
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                status="success",
                seed_urls=[funder.website_url for funder in funders],
            )

    monkeypatch.setattr("scraper.fetchers.browser_fetcher.BrowserFetcher", FailingBrowserFetcher)
    monkeypatch.setattr("scraper.main.WebSearchPipeline", FakePipeline)
    monkeypatch.setattr("scraper.main._upload_web_search_artifacts", lambda settings: None)
    monkeypatch.setattr(
        "scraper.main._load_site_definitions",
        lambda: [
            SiteDefinition(
                site_key="sefa",
                display_name="SEFA",
                primary_domain="www.sefa.org.za",
                adapter_key="generic",
                seed_urls=("https://www.sefa.org.za/products/direct-lending-products",),
                adapter_config={},
            )
        ],
    )

    result = CliRunner().invoke(
        app,
        ["run-seeds", "--output-path", str(tmp_path)],
        env={"SCRAPER_MODE": "web_search"},
    )

    assert result.exit_code == 0
    assert "BrowserFetcher must not be constructed" not in result.output


def test_mk_money_normalization_supported() -> None:
    parsed = parse_money_token("MK 5 million", default_currency="MWK", require_context=False)

    assert parsed is not None
    assert parsed.value == 5_000_000
    assert parsed.currency == "MWK"
