from __future__ import annotations

import json
from pathlib import Path

from scraper.parsers.generic_parser import GenericFundingParser
from scraper.pipeline import ScraperPipeline
from scraper.schemas import PageFetchResult
from scraper.storage.json_store import LocalJsonStore


class FixtureFetcher:
    def __init__(self, pages):
        self.pages = pages

    def fetch(self, url: str) -> PageFetchResult:
        if url in self.pages:
            return self.pages[url]
        return PageFetchResult(
            url=url,
            requested_url=url,
            canonical_url=url,
            status_code=404,
            content_type="text/html",
            html="",
            title=None,
            fetch_method="http",
            headers={},
            js_rendered=False,
            notes=["Fixture not found"],
        )

    def close(self) -> None:
        return None


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


def test_pipeline_runs_end_to_end(settings, fixture_dir: Path, monkeypatch) -> None:
    monkeypatch.setattr("scraper.pipeline.add_application_verification_note", lambda record, timeout_seconds: record)

    listing_html = (fixture_dir / "multi_program_listing.html").read_text(encoding="utf-8")
    youth_html = (fixture_dir / "youth_growth_loan_detail.html").read_text(encoding="utf-8")
    asset_html = (fixture_dir / "asset_finance_detail.html").read_text(encoding="utf-8")

    pages = {
        "https://example.org/funding-products": _page(
            "https://example.org/funding-products",
            listing_html,
            "Funding Products - Growth Finance Agency",
        ),
        "https://example.org/programmes/youth-growth-loan": _page(
            "https://example.org/programmes/youth-growth-loan",
            youth_html,
            "Youth Growth Loan - Growth Finance Agency",
        ),
        "https://example.org/programmes/asset-finance-facility": _page(
            "https://example.org/programmes/asset-finance-facility",
            asset_html,
            "Asset Finance Facility - Growth Finance Agency",
        ),
    }

    storage = LocalJsonStore(settings.output_path)
    pipeline = ScraperPipeline(
        settings=settings,
        storage=storage,
        parser=GenericFundingParser(settings),
        http_fetcher=FixtureFetcher(pages),
        browser_fetcher=None,
    )

    summary = pipeline.run(["https://example.org/funding-products"])

    assert summary.total_urls_crawled == 3
    assert summary.pages_fetched_successfully == 3
    assert summary.pages_failed == 0
    assert summary.programmes_after_dedupe == 2
    assert (settings.output_path / "raw" / "extracted_programs.jsonl").exists()
    assert (settings.output_path / "normalized" / "funding_programmes.json").exists()
    assert (settings.output_path / "normalized" / "funding_programmes.csv").exists()
    assert (settings.output_path / "logs" / "run_summary.json").exists()

    payload = json.loads((settings.output_path / "normalized" / "funding_programmes.json").read_text(encoding="utf-8"))
    names = {item["program_name"] for item in payload}
    assert names == {"Youth Growth Loan", "Asset Finance Facility"}


def test_pipeline_processes_domains_sequentially_and_resumes(settings, fixture_dir: Path, monkeypatch) -> None:
    monkeypatch.setattr("scraper.pipeline.add_application_verification_note", lambda record, timeout_seconds: record)

    listing_html = (fixture_dir / "multi_program_listing.html").read_text(encoding="utf-8")
    youth_html = (fixture_dir / "youth_growth_loan_detail.html").read_text(encoding="utf-8")
    asset_html = (fixture_dir / "asset_finance_detail.html").read_text(encoding="utf-8")

    pages = {
        "https://example.org/funding-products": _page(
            "https://example.org/funding-products",
            listing_html,
            "Funding Products - Growth Finance Agency",
        ),
        "https://example.org/programmes/youth-growth-loan": _page(
            "https://example.org/programmes/youth-growth-loan",
            youth_html,
            "Youth Growth Loan - Growth Finance Agency",
        ),
        "https://anotherfund.org/programmes/asset-finance-facility": _page(
            "https://anotherfund.org/programmes/asset-finance-facility",
            asset_html,
            "Asset Finance Facility - Another Fund",
        ),
    }

    storage = LocalJsonStore(settings.output_path)
    pipeline = ScraperPipeline(
        settings=settings,
        storage=storage,
        parser=GenericFundingParser(settings),
        http_fetcher=FixtureFetcher(pages),
        browser_fetcher=None,
    )

    summary = pipeline.run([
        "https://example.org/funding-products",
        "https://anotherfund.org/programmes/asset-finance-facility",
    ])

    assert summary.programmes_after_dedupe == 3
    state = json.loads((settings.output_path / "logs" / "crawl_state.json").read_text(encoding="utf-8"))
    assert state["completed_domains"] == ["anotherfund.org", "example.org"]

    pipeline_again = ScraperPipeline(
        settings=settings,
        storage=LocalJsonStore(settings.output_path),
        parser=GenericFundingParser(settings),
        http_fetcher=FixtureFetcher(pages),
        browser_fetcher=None,
    )
    resumed_summary = pipeline_again.run([
        "https://example.org/funding-products",
        "https://anotherfund.org/programmes/asset-finance-facility",
    ])

    assert resumed_summary.total_urls_crawled == 0
    payload = json.loads((settings.output_path / "normalized" / "funding_programmes.json").read_text(encoding="utf-8"))
    assert {item["source_domain"] for item in payload} == {"example.org", "anotherfund.org"}
    assert len(payload) == 3


def test_pipeline_can_limit_to_one_domain_per_run(settings, fixture_dir: Path, monkeypatch) -> None:
    monkeypatch.setattr("scraper.pipeline.add_application_verification_note", lambda record, timeout_seconds: record)

    listing_html = (fixture_dir / "multi_program_listing.html").read_text(encoding="utf-8")
    youth_html = (fixture_dir / "youth_growth_loan_detail.html").read_text(encoding="utf-8")
    asset_html = (fixture_dir / "asset_finance_detail.html").read_text(encoding="utf-8")

    pages = {
        "https://example.org/funding-products": _page(
            "https://example.org/funding-products",
            listing_html,
            "Funding Products - Growth Finance Agency",
        ),
        "https://example.org/programmes/youth-growth-loan": _page(
            "https://example.org/programmes/youth-growth-loan",
            youth_html,
            "Youth Growth Loan - Growth Finance Agency",
        ),
        "https://anotherfund.org/programmes/asset-finance-facility": _page(
            "https://anotherfund.org/programmes/asset-finance-facility",
            asset_html,
            "Asset Finance Facility - Another Fund",
        ),
    }

    pipeline = ScraperPipeline(
        settings=settings,
        storage=LocalJsonStore(settings.output_path),
        parser=GenericFundingParser(settings),
        http_fetcher=FixtureFetcher(pages),
        browser_fetcher=None,
    )

    summary = pipeline.run(
        [
            "https://example.org/funding-products",
            "https://anotherfund.org/programmes/asset-finance-facility",
        ],
        max_domains=1,
    )

    assert summary.programmes_after_dedupe == 2
    state = json.loads((settings.output_path / "logs" / "crawl_state.json").read_text(encoding="utf-8"))
    assert state["completed_domains"] == ["example.org"]
    assert state["failed_domains"] == []
