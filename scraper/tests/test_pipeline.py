from __future__ import annotations

import json
from pathlib import Path

from scraper import __version__ as SCRAPER_VERSION
from scraper.parsers.generic_parser import GenericFundingParser
from scraper.pipeline import ScraperPipeline
from scraper.schemas import PageFetchResult
from scraper.storage.json_store import LocalJsonStore
from scraper.storage.site_repository import SiteDefinition


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
    assert all(item["program_slug"] for item in payload)
    assert all(item["funder_slug"] for item in payload)
    assert all(item["country_code"] == "ZA" for item in payload)
    assert all(item["parser_version"] == SCRAPER_VERSION for item in payload)
    assert all("last_scraped_at" in item for item in payload)
    assert all("validation_errors" in item for item in payload)
    assert all("field_confidence" in item for item in payload)
    assert all("evidence_by_field" in item for item in payload)


def test_pipeline_runs_db_site_targets_with_adapter_key(settings, monkeypatch) -> None:
    monkeypatch.setattr("scraper.pipeline.add_application_verification_note", lambda record, timeout_seconds: record)

    pages = {
        "https://www.nefcorp.co.za/products-services": _page(
            "https://www.nefcorp.co.za/products-services",
            """
            <html>
              <head><title>Products and Services - NEF</title></head>
              <body>
                <main>
                  <article>
                    <h1>New Venture Capital - National Empowerment Fund</h1>
                    <p>Funding for startups and growth-stage businesses.</p>
                    <a href="https://www.nefcorp.co.za/products-services/new-venture-capital">Learn more</a>
                  </article>
                </main>
              </body>
            </html>
            """,
            "Products and Services - NEF",
        ),
        "https://www.nefcorp.co.za/products-services/new-venture-capital": _page(
            "https://www.nefcorp.co.za/products-services/new-venture-capital",
            """
            <html>
              <head><title>New Venture Capital - National Empowerment Fund</title></head>
              <body>
                <main>
                  <article>
                    <h1>New Venture Capital - National Empowerment Fund</h1>
                    <p>Funding for startups and growth-stage businesses.</p>
                  </article>
                </main>
              </body>
            </html>
            """,
            "New Venture Capital - National Empowerment Fund",
        ),
    }

    pipeline = ScraperPipeline(
        settings=settings,
        storage=LocalJsonStore(settings.output_path),
        parser=GenericFundingParser(settings),
        http_fetcher=FixtureFetcher(pages),
        browser_fetcher=None,
    )

    summary = pipeline.run_sites(
        [
            SiteDefinition(
                site_key="nefcorp",
                display_name="NEF",
                primary_domain="nefcorp.co.za",
                adapter_key="nefcorp",
                seed_urls=("https://www.nefcorp.co.za/products-services/",),
                adapter_config={
                    "allowed_path_prefixes": ["/products-services/"],
                    "strict_path_prefixes": True,
                    "include_url_terms": [
                        "fund",
                        "funding",
                        "finance",
                        "programme",
                        "product",
                        "transformation",
                        "capital",
                        "venture",
                        "acquisition",
                        "expansion",
                        "entrepreneurship",
                        "procurement",
                        "franchise",
                        "tourism",
                        "furniture",
                        "bakubung",
                        "spaza",
                        "film",
                        "arts",
                    ],
                    "program_name_strip_prefix_patterns": [r"^\s*\d+\s*[.)-]?\s*"],
                    "program_name_strip_suffix_patterns": [r"\s*(?:-|—|\||::)\s*National Empowerment Fund\s*$"],
                },
            )
        ]
    )

    assert summary.total_urls_crawled == 2
    trace = (settings.output_path / "logs" / "crawl_trace.jsonl").read_text(encoding="utf-8")
    assert '"adapter_name":"nefcorp"' in trace
    payload = json.loads((settings.output_path / "normalized" / "funding_programmes.json").read_text(encoding="utf-8"))
    assert any(item["program_name"] == "New Venture Capital" for item in payload)
    assert any(
        item["program_name"] == "New Venture Capital"
        and item.get("parent_programme_name") == "Rural Community Development Fund"
        for item in payload
    )
    assert any(item["site_adapter"] == "nefcorp" for item in payload)


def test_pipeline_applies_site_adapter_config_to_narrow_crawls(settings, monkeypatch) -> None:
    monkeypatch.setattr("scraper.pipeline.add_application_verification_note", lambda record, timeout_seconds: record)

    pages = {
        "https://example.org/": _page(
            "https://example.org/",
            """
            <html>
              <head><title>Example Funding Hub</title></head>
              <body>
                <main>
                  <a href="https://example.org/products-services/innovation-grant">Innovation Grant</a>
                  <a href="https://example.org/news/latest-update">Latest Update</a>
                </main>
              </body>
            </html>
            """,
            "Example Funding Hub",
        ),
        "https://example.org/products-services/innovation-grant": _page(
            "https://example.org/products-services/innovation-grant",
            """
            <html>
              <head><title>Innovation Grant</title></head>
              <body>
                <main>
                  <article>
                    <h1>Innovation Grant</h1>
                    <p>Support for product and business innovation.</p>
                  </article>
                </main>
              </body>
            </html>
            """,
            "Innovation Grant",
        ),
        "https://example.org/news/latest-update": _page(
            "https://example.org/news/latest-update",
            """
            <html>
              <head><title>Latest Update</title></head>
              <body>
                <main>
                  <article>
                    <h1>Latest Update</h1>
                  </article>
                </main>
              </body>
            </html>
            """,
            "Latest Update",
        ),
    }

    pipeline = ScraperPipeline(
        settings=settings,
        storage=LocalJsonStore(settings.output_path),
        parser=GenericFundingParser(settings),
        http_fetcher=FixtureFetcher(pages),
        browser_fetcher=None,
    )

    summary = pipeline.run_sites(
        [
            SiteDefinition(
                site_key="example",
                display_name="Example Funding",
                primary_domain="example.org",
                adapter_key="generic",
                seed_urls=("https://example.org/",),
                adapter_config={
                    "allowed_path_prefixes": ["/products-services/"],
                    "strict_path_prefixes": True,
                    "exclude_url_terms": ["/news/"]
                },
            )
        ]
    )

    assert summary.total_urls_crawled == 2
    trace = (settings.output_path / "logs" / "crawl_trace.jsonl").read_text(encoding="utf-8")
    assert "products-services/innovation-grant" in trace
    assert "news/latest-update" not in trace


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
