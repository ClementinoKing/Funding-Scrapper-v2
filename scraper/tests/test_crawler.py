from __future__ import annotations

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


def test_site_wide_crawl_discovers_internal_programme_pages(settings, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("scraper.pipeline.add_application_verification_note", lambda record, timeout_seconds: record)

    home_html = """
    <html><head><title>Home - Example Agency</title></head>
    <body>
      <main>
        <a href="https://example.org/funding-products">Funding products</a>
        <a href="https://example.org/careers">Careers</a>
      </main>
    </body></html>
    """
    listing_html = """
    <html><head><title>Funding Products - Example Agency</title></head>
    <body>
      <main>
        <section class="card">
          <h2>Youth Growth Loan</h2>
          <p>Working capital loan for youth-owned businesses.</p>
          <a href="https://example.org/programmes/youth-growth-loan">Learn more</a>
        </section>
        <section class="card">
          <h2>Asset Finance Facility</h2>
          <p>Finance for equipment and machinery purchases.</p>
          <a href="https://example.org/programmes/asset-finance-facility">View facility</a>
        </section>
      </main>
    </body></html>
    """
    youth_html = """
    <html><head><title>Youth Growth Loan - Example Agency</title></head>
    <body>
      <main><article>
        <h1>Youth Growth Loan</h1>
        <p>A working capital loan for youth-owned enterprises.</p>
        <a href="https://example.org/programmes/youth-growth-loan-about">More details</a>
      </article></main>
    </body></html>
    """
    youth_duplicate_html = """
    <html><head><title>Youth Growth Loan | Example Agency</title></head>
    <body>
      <main><article>
        <h1>Youth Growth Loan</h1>
        <p>Same programme described on a separate page with more application detail.</p>
      </article></main>
    </body></html>
    """
    asset_html = """
    <html><head><title>Asset Finance Facility - Example Agency</title></head>
    <body>
      <main><article>
        <h1>Asset Finance Facility</h1>
        <p>Finance for equipment and machinery purchases.</p>
      </article></main>
    </body></html>
    """
    irrelevant_html = """
    <html><head><title>Careers - Example Agency</title></head>
    <body><main><p>Join our team.</p></main></body></html>
    """

    pages = {
        "https://example.org/": _page("https://example.org/", home_html, "Home - Example Agency"),
        "https://example.org/funding-products": _page(
            "https://example.org/funding-products",
            listing_html,
            "Funding Products - Example Agency",
        ),
        "https://example.org/programmes/youth-growth-loan": _page(
            "https://example.org/programmes/youth-growth-loan",
            youth_html,
            "Youth Growth Loan - Example Agency",
        ),
        "https://example.org/programmes/youth-growth-loan-about": _page(
            "https://example.org/programmes/youth-growth-loan-about",
            youth_duplicate_html,
            "Youth Growth Loan | Example Agency",
        ),
        "https://example.org/programmes/asset-finance-facility": _page(
            "https://example.org/programmes/asset-finance-facility",
            asset_html,
            "Asset Finance Facility - Example Agency",
        ),
        "https://example.org/careers": _page("https://example.org/careers", irrelevant_html, "Careers - Example Agency"),
    }

    storage = LocalJsonStore(settings.output_path)
    pipeline = ScraperPipeline(
        settings=settings,
        storage=storage,
        parser=GenericFundingParser(settings),
        http_fetcher=FixtureFetcher(pages),
        browser_fetcher=None,
    )

    summary = pipeline.run(["https://example.org/"])

    assert summary.total_urls_crawled >= 4
    assert summary.programmes_extracted >= 3
    assert summary.programmes_after_dedupe == 2
    assert (settings.output_path / "logs" / "crawl_trace.jsonl").exists()
    assert (settings.output_path / "logs" / "merge_trace.json").exists()
    trace = (settings.output_path / "logs" / "crawl_trace.jsonl").read_text(encoding="utf-8")
    assert '"event":"visited"' in trace
    assert '"event":"extracted"' in trace


def test_crawler_uses_browser_fallback_on_forbidden_response(settings, tmp_path: Path) -> None:
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
        <html><head><title>Youth Growth Loan</title></head>
        <body><main><article><h1>Youth Growth Loan</h1><p>Working capital loan.</p></article></main></body></html>
        """,
        "Youth Growth Loan",
    )

    storage = LocalJsonStore(settings.output_path)
    pipeline = ScraperPipeline(
        settings=settings,
        storage=storage,
        parser=GenericFundingParser(settings),
        http_fetcher=FixtureFetcher({"https://example.org/programmes/youth-growth-loan": http_page}),
        browser_fetcher=TrackingBrowserFetcher(browser_page),
    )

    summary = pipeline.run(["https://example.org/programmes/youth-growth-loan"])

    assert summary.pages_fetched_successfully == 1
    assert pipeline.browser_fetcher is not None
    assert pipeline.browser_fetcher.calls == ["https://example.org/programmes/youth-growth-loan"]
    trace = (settings.output_path / "logs" / "crawl_trace.jsonl").read_text(encoding="utf-8")
    assert '"event":"parsed"' in trace
