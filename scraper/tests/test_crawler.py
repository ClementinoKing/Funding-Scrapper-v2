from __future__ import annotations

import json
from pathlib import Path

import pytest

from scraper.crawler import Crawler
from scraper.parsers.generic_parser import GenericFundingParser
from scraper.pipeline import ScraperPipeline
from scraper.schemas import PageFetchResult
from scraper.storage.json_store import LocalJsonStore
from scraper.storage.site_repository import SiteDefinition


class FixtureFetcher:
    def __init__(self, pages):
        self.pages = pages
        self.calls: list[str] = []

    def fetch(self, url: str) -> PageFetchResult:
        self.calls.append(url)
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


class TrackingBrowserFetcher:
    def __init__(self, page: PageFetchResult):
        self.page = page
        self.calls: list[str] = []

    def fetch(self, url: str) -> PageFetchResult:
        self.calls.append(url)
        return self.page

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


@pytest.fixture(autouse=True)
def _noop_application_verification(monkeypatch) -> None:
    monkeypatch.setattr("scraper.pipeline.add_application_verification_note", lambda record, timeout_seconds: record)


def test_crawler_keeps_application_links_out_of_crawl_queue(settings) -> None:
    html = """
    <html>
      <head><title>Youth Growth Loan</title></head>
      <body>
        <main>
          <article>
            <h1>Youth Growth Loan</h1>
            <p>A working capital loan for youth-owned enterprises.</p>
            <a href="https://example.org/apply/youth-growth-loan">Apply online</a>
          </article>
        </main>
      </body>
    </html>
    """
    url = "https://example.org/programmes/youth-growth-loan"
    pages = {url: _page(url, html, "Youth Growth Loan")}

    fetcher = FixtureFetcher(pages)
    pipeline = ScraperPipeline(
        settings=settings,
        storage=LocalJsonStore(settings.output_path),
        parser=GenericFundingParser(settings),
        http_fetcher=fetcher,
        browser_fetcher=None,
    )

    summary = pipeline.run([url])

    assert summary.pages_fetched_successfully == 1
    assert summary.pages_failed == 0
    assert fetcher.calls == [url]

    content_path = next((settings.output_path / "raw" / "content").glob("*.json"))
    document = json.loads(content_path.read_text(encoding="utf-8"))
    assert document["application_links"] == ["https://example.org/apply/youth-growth-loan"]
    assert document["internal_links"] == []
    trace = (settings.output_path / "logs" / "crawl_trace.jsonl").read_text(encoding="utf-8")
    assert '"event":"content_extracted"' in trace


def test_crawler_filters_irrelevant_urls_with_adapter_rules(settings, monkeypatch) -> None:
    home_html = """
    <html>
      <head><title>Example Funding Hub</title></head>
      <body>
        <main>
          <a href="https://example.org/products-services/innovation-grant">Innovation Grant</a>
          <a href="https://example.org/news/latest-update">Latest Update</a>
        </main>
      </body>
    </html>
    """
    program_html = """
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
    """
    news_html = """
    <html>
      <head><title>Latest Update</title></head>
      <body>
        <main>
          <article>
            <h1>Latest Update</h1>
            <p>This is a news article.</p>
          </article>
        </main>
      </body>
    </html>
    """
    pages = {
        "https://example.org/": _page("https://example.org/", home_html, "Example Funding Hub"),
        "https://example.org/products-services/innovation-grant": _page(
            "https://example.org/products-services/innovation-grant",
            program_html,
            "Innovation Grant",
        ),
        "https://example.org/news/latest-update": _page(
            "https://example.org/news/latest-update",
            news_html,
            "Latest Update",
        ),
    }

    monkeypatch.setattr(
        Crawler,
        "_fetch_sitemap_urls",
        lambda self, domain: [
            "https://example.org/news/latest-update",
            "https://example.org/products-services/innovation-grant",
        ],
    )

    fetcher = FixtureFetcher(pages)
    pipeline = ScraperPipeline(
        settings=settings,
        storage=LocalJsonStore(settings.output_path),
        parser=GenericFundingParser(settings),
        http_fetcher=fetcher,
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
                    "exclude_url_terms": ["/news/"],
                },
            )
        ]
    )

    assert summary.total_urls_crawled == 2
    assert "https://example.org/news/latest-update" not in fetcher.calls
    trace = (settings.output_path / "logs" / "crawl_trace.jsonl").read_text(encoding="utf-8")
    assert "news/latest-update" not in trace
    assert "products-services/innovation-grant" in trace
    payload = json.loads((settings.output_path / "normalized" / "funding_programmes.json").read_text(encoding="utf-8"))
    assert any(item["program_name"] == "Innovation Grant" for item in payload)


def test_crawler_uses_browser_fallback_on_forbidden_response(settings) -> None:
    http_page = PageFetchResult(
        url="https://example.org/programmes/youth-growth-loan",
        requested_url="https://example.org/programmes/youth-growth-loan",
        canonical_url="https://example.org/programmes/youth-growth-loan",
        final_url="https://example.org/programmes/youth-growth-loan",
        status_code=403,
        content_type="text/html",
        html="",
        title=None,
        fetch_method="http",
        headers={},
        js_rendered=False,
        notes=["Forbidden"],
    )
    browser_page = _page(
        "https://example.org/programmes/youth-growth-loan",
        """
        <html>
          <head><title>Youth Growth Loan</title></head>
          <body>
            <main>
              <article>
                <h1>Youth Growth Loan</h1>
                <p>Working capital loan.</p>
              </article>
            </main>
          </body>
        </html>
        """,
        "Youth Growth Loan",
    )

    fetcher = FixtureFetcher({"https://example.org/programmes/youth-growth-loan": http_page})
    browser_fetcher = TrackingBrowserFetcher(browser_page)
    pipeline = ScraperPipeline(
        settings=settings,
        storage=LocalJsonStore(settings.output_path),
        parser=GenericFundingParser(settings),
        http_fetcher=fetcher,
        browser_fetcher=browser_fetcher,
    )

    summary = pipeline.run(["https://example.org/programmes/youth-growth-loan"])

    assert summary.pages_fetched_successfully == 1
    assert browser_fetcher.calls == ["https://example.org/programmes/youth-growth-loan"]
    trace = (settings.output_path / "logs" / "crawl_trace.jsonl").read_text(encoding="utf-8")
    assert '"event":"content_extracted"' in trace


def test_crawler_discovers_programme_routes_from_rendered_homepage(settings) -> None:
    http_home = PageFetchResult(
        url="https://www.pic.gov.za/",
        requested_url="https://www.pic.gov.za/",
        canonical_url="https://www.pic.gov.za/",
        final_url="https://www.pic.gov.za/",
        status_code=200,
        content_type="text/html",
        html="""
        <html>
          <head>
            <title>Public Investment Corporation</title>
            <script src="/assets/app.js"></script>
            <script src="/assets/vendor.js"></script>
            <script src="/assets/runtime.js"></script>
          </head>
          <body>
            <div id="root"></div>
          </body>
        </html>
        """,
        title="Public Investment Corporation",
        fetch_method="http",
        headers={},
        js_rendered=False,
        notes=[],
    )
    browser_home = _page(
        "https://www.pic.gov.za/",
        """
        <html>
          <head><title>Public Investment Corporation</title></head>
          <body>
            <main>
              <nav class="site-nav">
                <button data-href="/early-stage-fund">Early Stage Fund</button>
                <button onclick="window.location='/isibaya'">Isibaya</button>
                <a href="/properties">Properties</a>
              </nav>
              <section class="card-grid">
                <article class="card">
                  <h2>Early Stage Fund</h2>
                  <p>Backing young companies through targeted investment.</p>
                </article>
              </section>
            </main>
          </body>
        </html>
        """,
        "Public Investment Corporation",
    )
    early_stage = _page(
        "https://www.pic.gov.za/early-stage-fund",
        """
        <html>
          <head><title>Early Stage Fund</title></head>
          <body>
            <main>
              <article>
                <h1>Early Stage Fund</h1>
                <p>Investment for early-stage companies.</p>
              </article>
            </main>
          </body>
        </html>
        """,
        "Early Stage Fund",
    )
    isibaya = _page(
        "https://www.pic.gov.za/isibaya",
        """
        <html>
          <head><title>Isibaya</title></head>
          <body>
            <main>
              <article>
                <h1>Isibaya</h1>
                <p>Local development investment initiative.</p>
              </article>
            </main>
          </body>
        </html>
        """,
        "Isibaya",
    )
    properties = _page(
        "https://www.pic.gov.za/properties",
        """
        <html>
          <head><title>Properties</title></head>
          <body>
            <main>
              <article>
                <h1>Properties</h1>
                <p>Commercial property portfolio and investment assets.</p>
              </article>
            </main>
          </body>
        </html>
        """,
        "Properties",
    )

    fetcher = FixtureFetcher(
        {
            "https://www.pic.gov.za/": http_home,
            "https://www.pic.gov.za/early-stage-fund": early_stage,
            "https://www.pic.gov.za/isibaya": isibaya,
            "https://www.pic.gov.za/properties": properties,
        }
    )
    browser_fetcher = TrackingBrowserFetcher(browser_home)
    pipeline = ScraperPipeline(
        settings=settings,
        storage=LocalJsonStore(settings.output_path),
        parser=GenericFundingParser(settings),
        http_fetcher=fetcher,
        browser_fetcher=browser_fetcher,
    )

    summary = pipeline.run(["https://www.pic.gov.za/"])

    assert summary.pages_fetched_successfully == 4
    assert browser_fetcher.calls[0] == "https://www.pic.gov.za/"
    assert browser_fetcher.calls.count("https://www.pic.gov.za/") == 1
    assert "https://www.pic.gov.za/early-stage-fund" in fetcher.calls
    assert "https://www.pic.gov.za/isibaya" in fetcher.calls
    assert "https://www.pic.gov.za/properties" in fetcher.calls
