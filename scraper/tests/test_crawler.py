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


class FixtureHttpResponse:
    def __init__(self, text: str, status_code: int = 200, url: str = "https://example.org/sitemap.xml", headers=None):
        self.text = text
        self.content = text.encode("utf-8")
        self.status_code = status_code
        self.url = url
        self.headers = headers or {"content-type": "application/xml"}
        self.encoding = "utf-8"


class SitemapClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls: list[str] = []

    def get(self, url: str, headers=None):
        self.calls.append(url)
        return self.responses.get(url, FixtureHttpResponse("", status_code=404, url=url))


class SitemapFixtureFetcher(FixtureFetcher):
    def __init__(self, pages, responses):
        super().__init__(pages)
        self.client = SitemapClient(responses)

    def _headers(self):
        return {}


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
    assert summary.browser_fallback_count == 1
    assert browser_fetcher.calls == ["https://example.org/programmes/youth-growth-loan"]
    trace = (settings.output_path / "logs" / "crawl_trace.jsonl").read_text(encoding="utf-8")
    assert '"event":"content_extracted"' in trace
    assert '"event":"browser_fallback"' in trace
    assert "restricted-or-rate-limited-status" in trace


def test_crawler_does_not_browser_fetch_document_urls_even_when_adapter_requires_browser(settings) -> None:
    pdf_url = "https://www.pic.gov.za/assets/funding-form.pdf"
    pdf_page = PageFetchResult(
        url=pdf_url,
        requested_url=pdf_url,
        canonical_url=pdf_url,
        final_url=pdf_url,
        status_code=200,
        content_type="application/pdf",
        html="Funding form",
        title="Funding form",
        fetch_method="http",
        headers={"content-type": "application/pdf"},
        js_rendered=False,
        notes=[],
    )
    fetcher = FixtureFetcher({pdf_url: pdf_page})
    browser_fetcher = TrackingBrowserFetcher(_page(pdf_url, "<html></html>", "Browser document"))
    pipeline = ScraperPipeline(
        settings=settings,
        storage=LocalJsonStore(settings.output_path),
        parser=GenericFundingParser(settings),
        http_fetcher=fetcher,
        browser_fetcher=browser_fetcher,
    )

    summary = pipeline.run_sites(
        [
            SiteDefinition(
                site_key="pic",
                display_name="PIC",
                primary_domain="www.pic.gov.za",
                adapter_key="generic",
                seed_urls=(pdf_url,),
                adapter_config={
                    "allowed_path_prefixes": ["/assets"],
                    "playwright_required_by_default": True,
                    "force_browser_url_terms": ["pic.gov.za"],
                },
            )
        ]
    )

    assert summary.pages_fetched_successfully == 1
    assert browser_fetcher.calls == []


def test_crawler_treats_www_and_root_domain_as_same_site(settings) -> None:
    home = _page(
        "https://example.org/",
        "<html><body><main><a href='https://www.example.org/funding/youth-grant'>Youth Grant</a></main></body></html>",
        "Example",
    )
    grant = _page(
        "https://www.example.org/funding/youth-grant",
        "<html><body><main><h1>Youth Grant</h1><p>Grant funding for youth businesses.</p></main></body></html>",
        "Youth Grant",
    )
    fetcher = FixtureFetcher({"https://example.org/": home, "https://www.example.org/funding/youth-grant": grant})
    pipeline = ScraperPipeline(
        settings=settings,
        storage=LocalJsonStore(settings.output_path),
        parser=GenericFundingParser(settings),
        http_fetcher=fetcher,
        browser_fetcher=None,
    )

    summary = pipeline.run(["https://example.org/"])

    assert summary.pages_fetched_successfully == 2
    assert "https://www.example.org/funding/youth-grant" in fetcher.calls


def test_crawler_discovers_sitemaps_from_robots_and_nested_indexes(settings) -> None:
    home = _page("https://example.org/", "<html><body><main><h1>Home</h1></main></body></html>", "Home")
    grant = _page(
        "https://example.org/funding/youth-grant",
        "<html><body><main><h1>Youth Grant</h1><p>Grant funding for youth businesses.</p></main></body></html>",
        "Youth Grant",
    )
    responses = {
        "https://example.org/robots.txt": FixtureHttpResponse(
            "User-agent: *\nAllow: /\nSitemap: https://example.org/sitemap-index.xml",
            url="https://example.org/robots.txt",
            headers={"content-type": "text/plain"},
        ),
        "https://example.org/sitemap-index.xml": FixtureHttpResponse(
            """<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <sitemap><loc>https://example.org/programmes-sitemap.xml</loc></sitemap>
            </sitemapindex>""",
            url="https://example.org/sitemap-index.xml",
        ),
        "https://example.org/programmes-sitemap.xml": FixtureHttpResponse(
            """<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://example.org/funding/youth-grant</loc></url>
            </urlset>""",
            url="https://example.org/programmes-sitemap.xml",
        ),
    }
    fetcher = SitemapFixtureFetcher({"https://example.org/": home, "https://example.org/funding/youth-grant": grant}, responses)
    pipeline = ScraperPipeline(
        settings=settings,
        storage=LocalJsonStore(settings.output_path),
        parser=GenericFundingParser(settings),
        http_fetcher=fetcher,
        browser_fetcher=None,
    )

    summary = pipeline.run(["https://example.org/"])

    assert summary.pages_fetched_successfully == 2
    assert "https://example.org/robots.txt" in fetcher.client.calls
    assert "https://example.org/programmes-sitemap.xml" in fetcher.client.calls


def test_crawler_applies_queue_and_link_caps(settings) -> None:
    settings.max_queue_urls = 1
    settings.max_links_per_page = 2
    home_links = "".join(
        f"<a href='https://example.org/funding/program-{index}'>Programme {index} Grant</a>"
        for index in range(5)
    )
    pages = {
        "https://example.org/": _page("https://example.org/", f"<html><body><main>{home_links}</main></body></html>", "Home")
    }
    for index in range(5):
        url = f"https://example.org/funding/program-{index}"
        pages[url] = _page(url, f"<html><body><main><h1>Programme {index}</h1><p>Grant funding.</p></main></body></html>", f"Programme {index}")
    fetcher = FixtureFetcher(pages)
    pipeline = ScraperPipeline(
        settings=settings,
        storage=LocalJsonStore(settings.output_path),
        parser=GenericFundingParser(settings),
        http_fetcher=fetcher,
        browser_fetcher=None,
    )

    summary = pipeline.run(["https://example.org/"])

    assert summary.pages_fetched_successfully == 2
    assert summary.queue_saturation_count >= 1
    assert summary.skipped_url_counts["queue-saturated"] >= 1


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


def test_crawler_uses_sharepoint_portal_profile_with_relative_seeds(settings) -> None:
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
                <a href="/pic/site/site-map">Site map</a>
                <button data-href="/apply-for-funding/isibaya">Isibaya</button>
                <button data-href="/apply-for-funding/properties">Properties</button>
              </nav>
            </main>
          </body>
        </html>
        """,
        "Public Investment Corporation",
    )
    site_map = _page(
        "https://www.pic.gov.za/pic/site/site-map",
        """
        <html>
          <head><title>Site Map</title></head>
          <body>
            <main>
              <article>
                <h1>Site Map</h1>
                <a href="/Pages/isibaya.aspx">Isibaya</a>
                <a href="/Pages/properties.aspx">Properties</a>
              </article>
            </main>
          </body>
        </html>
        """,
        "Site Map",
    )
    apply_isibaya = _page(
        "https://www.pic.gov.za/apply-for-funding/isibaya",
        """
        <html>
          <head><title>Isibaya Fund Applications</title></head>
          <body>
            <main>
              <article>
                <h1>Isibaya Fund Applications</h1>
                <p>Application portal for Isibaya funding proposals.</p>
              </article>
            </main>
          </body>
        </html>
        """,
        "Isibaya Fund Applications",
    )
    apply_properties = _page(
        "https://www.pic.gov.za/apply-for-funding/properties",
        """
        <html>
          <head><title>Properties Funding Applications</title></head>
          <body>
            <main>
              <article>
                <h1>Properties Funding Applications</h1>
                <p>Application portal for property investment opportunities.</p>
              </article>
            </main>
          </body>
        </html>
        """,
        "Properties Funding Applications",
    )
    pages = {
        "https://www.pic.gov.za/": http_home,
        "https://www.pic.gov.za/pic/site/site-map": site_map,
        "https://www.pic.gov.za/apply-for-funding/isibaya": apply_isibaya,
        "https://www.pic.gov.za/apply-for-funding/properties": apply_properties,
        "https://www.pic.gov.za/Pages/isibaya.aspx": _page(
            "https://www.pic.gov.za/Pages/isibaya.aspx",
            """
            <html><head><title>Isibaya</title></head><body><main><article><h1>Isibaya</h1></article></main></body></html>
            """,
            "Isibaya",
        ),
        "https://www.pic.gov.za/Pages/properties.aspx": _page(
            "https://www.pic.gov.za/Pages/properties.aspx",
            """
            <html><head><title>Properties</title></head><body><main><article><h1>Properties</h1></article></main></body></html>
            """,
            "Properties",
        ),
    }

    fetcher = FixtureFetcher(pages)
    browser_fetcher = TrackingBrowserFetcher(browser_home)
    pipeline = ScraperPipeline(
        settings=settings,
        storage=LocalJsonStore(settings.output_path),
        parser=GenericFundingParser(settings),
        http_fetcher=fetcher,
        browser_fetcher=browser_fetcher,
    )

    summary = pipeline.run_sites(
        [
            SiteDefinition(
                site_key="pic",
                display_name="Public Investment Corporation",
                primary_domain="www.pic.gov.za",
                adapter_key="sharepoint_portal",
                seed_urls=("https://www.pic.gov.za/",),
                adapter_config={
                    "default_seed_urls": [
                        "/pic/site/site-map",
                        "/apply-for-funding/isibaya",
                        "/apply-for-funding/properties",
                    ],
                },
            )
        ]
    )

    assert summary.pages_fetched_successfully == 4
    assert browser_fetcher.calls[0] == "https://www.pic.gov.za/"
    assert "https://www.pic.gov.za/pic/site/site-map" in fetcher.calls
    assert "https://www.pic.gov.za/apply-for-funding/isibaya" in fetcher.calls
    assert "https://www.pic.gov.za/apply-for-funding/properties" in fetcher.calls
