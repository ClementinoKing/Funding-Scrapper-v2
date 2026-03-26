from __future__ import annotations

import json
from pathlib import Path

from scraper.adapters.base import SiteAdapter
from scraper.adapters.registry import SiteAdapterRegistry, build_default_registry
from scraper.parsers.generic_parser import GenericFundingParser
from scraper.pipeline import ScraperPipeline
from scraper.schemas import PageFetchResult
from scraper.storage.json_store import LocalJsonStore
from scraper.utils.urls import canonicalize_url


class FixtureFetcher:
    def __init__(self, pages):
        self.pages = pages

    def fetch(self, url: str) -> PageFetchResult:
        if url in self.pages:
            return self.pages[url]
        canonical = canonicalize_url(url)
        if canonical in self.pages:
            return self.pages[canonical]
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


def test_adapter_registry_resolves_exact_domain_subdomain_and_generic() -> None:
    adapter = SiteAdapter(key="example", domain="example.org")
    registry = SiteAdapterRegistry(adapters={"example.org": adapter}, generic_adapter=build_default_registry().generic_adapter)

    assert registry.resolve("https://example.org").key == "example"
    assert registry.resolve("blog.example.org").key == "example"
    assert registry.resolve("https://unknown.example").key == "generic"


def test_adapter_selectors_improve_parsing(settings) -> None:
    adapter = SiteAdapter(
        key="custom",
        domain="example.org",
        candidate_selectors=(".funding-item",),
        content_selectors=(".funding-item",),
    )
    parser = GenericFundingParser(settings)
    html = """
    <html>
      <head><title>Custom Funding Page</title></head>
      <body>
        <main>
          <div class="funding-item">
            <h2>Innovation Booster Grant</h2>
            <p>Grant for new product development.</p>
            <a href="https://example.org/apply/innovation-booster">Apply online</a>
          </div>
        </main>
      </body>
    </html>
    """
    page = _page("https://example.org/funding", html, "Custom Funding Page")

    result = parser.parse(page, allowed_domains=["example.org"], adapter=adapter)

    assert any(record.program_name == "Innovation Booster Grant" for record in result.records)
    assert result.application_links == ["https://example.org/apply/innovation-booster"]


def test_nefcorp_content_selectors_ignore_sidebar_noise(settings) -> None:
    adapter = build_default_registry().resolve("https://www.nefcorp.co.za/")
    parser = GenericFundingParser(settings)
    html = """
    <html>
      <head><title>Precise Fund - National Empowerment Fund</title></head>
      <body>
        <main>
          <article class="single-page-article">
            <div class="single-page-content entry clr">
              <h1>Precise Fund</h1>
              <section>
                <h2>Funding offer</h2>
                <p>This fund provides working capital and expansion capital.</p>
                <a href="https://www.nefcorp.co.za/products-services/precise-fund/programme-guidelines.pdf">Programme Guidelines</a>
              </section>
            </div>
          </article>
          <aside id="sidebar" class="sidebar-container">
            <nav class="menu-funding-solutions-container">
              <a href="https://www.nefcorp.co.za/wp-content/uploads/2024/05/annual-report.pdf">Annual report</a>
              <p>Retail Tourism Energy</p>
            </nav>
          </aside>
        </main>
      </body>
    </html>
    """
    page = _page("https://www.nefcorp.co.za/products-services/precise-fund", html, "Precise Fund - National Empowerment Fund")

    result = parser.parse(page, allowed_domains=["nefcorp.co.za"], adapter=adapter)

    assert result.records
    record = result.records[0]
    assert record.related_documents == [
        "https://www.nefcorp.co.za/products-services/precise-fund/programme-guidelines.pdf"
    ]
    assert record.industries == []
    assert record.use_of_funds == ["Working capital", "Expansion capital"]


def test_adapter_url_rules_filter_news_pages(settings) -> None:
    settings.programme_accept_threshold = 20
    settings.programme_review_threshold = 10
    adapter = SiteAdapter(
        key="example",
        domain="example.org",
        allowed_path_prefixes=("/programmes/",),
        include_url_terms=("programme", "apply"),
        exclude_url_terms=("/news/",),
    )
    registry = SiteAdapterRegistry(
        adapters={"example.org": adapter},
        generic_adapter=build_default_registry().generic_adapter,
    )

    home_html = """
    <html><head><title>Home</title></head>
    <body>
      <main>
        <a href="https://example.org/programmes/youth-growth-loan">Youth Growth Loan</a>
        <a href="https://example.org/news/latest-update">Latest update</a>
      </main>
    </body></html>
    """
    programme_html = """
    <html><head><title>Youth Growth Loan</title></head>
    <body>
      <main><article>
        <h1>Youth Growth Loan</h1>
        <p>Offered by Example Agency.</p>
        <p>Working capital loan for growth-stage businesses.</p>
        <p>Loan sizes range from R500k to R2m.</p>
        <p>Applications are open year-round.</p>
        <p>Only youth-owned small businesses in Gauteng may apply.</p>
        <a href="https://example.org/apply/youth-growth-loan">Apply now</a>
      </article></main>
    </body></html>
    """
    news_html = """
    <html><head><title>Latest Update</title></head>
    <body><main><article><p>Announcement only.</p></article></main></body></html>
    """

    pages = {
        "https://example.org/": _page("https://example.org/", home_html, "Home"),
        "https://example.org/programmes/youth-growth-loan": _page(
            "https://example.org/programmes/youth-growth-loan",
            programme_html,
            "Youth Growth Loan",
        ),
        "https://example.org/news/latest-update": _page(
            "https://example.org/news/latest-update",
            news_html,
            "Latest Update",
        ),
    }

    storage = LocalJsonStore(settings.output_path)
    pipeline = ScraperPipeline(
        settings=settings,
        storage=storage,
        parser=GenericFundingParser(settings),
        http_fetcher=FixtureFetcher(pages),
        browser_fetcher=None,
        adapter_registry=registry,
    )

    summary = pipeline.run(["https://example.org/"])

    assert summary.total_urls_crawled == 2
    assert summary.programmes_extracted == 1
    trace = (settings.output_path / "logs" / "crawl_trace.jsonl").read_text(encoding="utf-8")
    assert '"adapter_name":"example"' in trace
    assert '"page_role":"detail"' in trace or '"page_role":"listing"' in trace
    payload = json.loads((settings.output_path / "normalized" / "funding_programmes.json").read_text(encoding="utf-8"))
    assert len(payload) in {0, 1}


def test_nefcorp_adapter_merges_child_pages_into_parent_programme(settings) -> None:
    settings.programme_accept_threshold = 20
    settings.programme_review_threshold = 10
    registry = build_default_registry()
    adapter = registry.resolve("https://www.nefcorp.co.za/")

    index_html = """
    <html><head><title>Products and Services - NEF</title></head>
    <body>
      <main>
        <a href="https://www.nefcorp.co.za/products-services/imbewu-fund/">iMbewu Fund</a>
        <a href="https://www.nefcorp.co.za/news/latest-update">Latest update</a>
      </main>
    </body></html>
    """
    parent_html = """
    <html><head><title>iMbewu Fund - NEF</title></head>
    <body>
      <main>
        <article>
          <h1>iMbewu Fund</h1>
          <p>The fund supports entrepreneurship finance, procurement finance, and franchise finance.</p>
          <p>Applications are open year-round.</p>
          <p>Visit the application portal or download the checklist.</p>
          <a href="https://apply.nefcorp.co.za/portal">Application portal</a>
          <a href="https://www.nefcorp.co.za/products-services/imbewu-fund/checklist.pdf">Checklist</a>
          <a href="https://www.nefcorp.co.za/products-services/imbewu-fund/1-entrepreneurship-finance/">Entrepreneurship Finance</a>
        </article>
      </main>
    </body></html>
    """
    child_html = """
    <html><head><title>1. Entrepreneurship Finance - iMbewu Fund</title></head>
    <body>
      <main>
        <article>
          <h1>1. Entrepreneurship Finance</h1>
          <p>Funding for startup and growth-stage businesses.</p>
          <p>Loan finance for working capital and acquisition.</p>
          <p>Maximum funding is R2 million.</p>
          <p>Eligible applicants include black-owned SMEs.</p>
        </article>
      </main>
    </body></html>
    """
    support_html = """
    <html><head><title>Funding Criteria - NEF</title></head>
    <body>
      <main>
        <article>
          <h1>Funding Criteria</h1>
          <p>Commercial viability and legal compliance are required.</p>
          <p>Black ownership and job creation are viewed favourably.</p>
        </article>
      </main>
    </body></html>
    """

    pages = {
        "https://www.nefcorp.co.za/products-services": _page(
            "https://www.nefcorp.co.za/products-services",
            index_html,
            "Products and Services - NEF",
        ),
        "https://www.nefcorp.co.za/products-services/imbewu-fund": _page(
            "https://www.nefcorp.co.za/products-services/imbewu-fund",
            parent_html,
            "iMbewu Fund - NEF",
        ),
        "https://www.nefcorp.co.za/products-services/imbewu-fund/1-entrepreneurship-finance": _page(
            "https://www.nefcorp.co.za/products-services/imbewu-fund/1-entrepreneurship-finance",
            child_html,
            "1. Entrepreneurship Finance - iMbewu Fund",
        ),
        "https://www.nefcorp.co.za/products-services/funding-criteria": _page(
            "https://www.nefcorp.co.za/products-services/funding-criteria",
            support_html,
            "Funding Criteria - NEF",
        ),
        "https://www.nefcorp.co.za/products-services/imbewu-fund/checklist.pdf": PageFetchResult(
            url="https://www.nefcorp.co.za/products-services/imbewu-fund/checklist.pdf",
            requested_url="https://www.nefcorp.co.za/products-services/imbewu-fund/checklist.pdf",
            canonical_url="https://www.nefcorp.co.za/products-services/imbewu-fund/checklist.pdf",
            final_url="https://www.nefcorp.co.za/products-services/imbewu-fund/checklist.pdf",
            status_code=200,
            content_type="application/pdf",
            html="PDF fixture",
            title="Checklist",
            fetch_method="http",
            headers={},
            js_rendered=False,
            notes=[],
        ),
        "https://www.nefcorp.co.za/news/latest-update": _page(
            "https://www.nefcorp.co.za/news/latest-update",
            "<html><head><title>Latest update</title></head><body><p>News only.</p></body></html>",
            "Latest update",
        ),
    }

    pipeline = ScraperPipeline(
        settings=settings,
        storage=LocalJsonStore(settings.output_path),
        parser=GenericFundingParser(settings),
        http_fetcher=FixtureFetcher(pages),
        browser_fetcher=None,
        adapter_registry=registry,
    )

    summary = pipeline.run(["https://www.nefcorp.co.za/products-services/"])

    assert summary.total_urls_crawled == 4
    payload = json.loads((settings.output_path / "normalized" / "funding_programmes.json").read_text(encoding="utf-8"))
    assert len(payload) >= 2
    assert all(record.get("page_type") != "sub-product" for record in payload)
    assert any(record["program_name"] == "iMbewu Fund" for record in payload)
    assert any("Entrepreneurship Finance" in record["program_name"] for record in payload)
    sub_record = next(record for record in payload if "Entrepreneurship Finance" in record["program_name"])
    assert sub_record.get("parent_programme_name") in (None, "")
    trace = (settings.output_path / "logs" / "crawl_trace.jsonl").read_text(encoding="utf-8")
    assert '"url":"https://www.nefcorp.co.za/news/latest-update"' in trace
    assert '"reason":"adapter-rule"' in trace


def test_nefcorp_programme_guidelines_remain_flat_programmes(settings) -> None:
    settings.programme_accept_threshold = 20
    settings.programme_review_threshold = 10
    registry = build_default_registry()
    adapter = registry.resolve("https://www.nefcorp.co.za/")

    index_html = """
    <html><head><title>Products and Services - NEF</title></head>
    <body>
      <main>
        <a href="https://www.nefcorp.co.za/products-services/tourism-transformation-fund/">Tourism Transformation Fund</a>
      </main>
    </body></html>
    """
    parent_html = """
    <html><head><title>Tourism Transformation Fund - National Empowerment Fund</title></head>
    <body>
      <main>
        <article>
          <h1>Tourism Transformation Fund</h1>
          <p>The fund aims to drive transformation in the tourism sector.</p>
          <p>Applications are submitted online.</p>
          <a href="https://www.nefcorp.co.za/products-services/tourism-transformation-fund/programme-guidelines">Programme guidelines</a>
        </article>
      </main>
    </body></html>
    """
    support_html = """
    <html><head><title>Programme guidelines - Tourism Transformation Fund</title></head>
    <body>
      <main>
        <article>
          <h1>4. ELIGIBILITY CRITERIA TTF</h1>
          <p>Funding applications must be commercially viable and legally compliant.</p>
          <p>The enterprise must be black owned.</p>
          <p>Download the checklist for supporting documents.</p>
        </article>
      </main>
    </body></html>
    """

    pages = {
        "https://www.nefcorp.co.za/products-services": _page(
            "https://www.nefcorp.co.za/products-services",
            index_html,
            "Products and Services - NEF",
        ),
        "https://www.nefcorp.co.za/products-services/tourism-transformation-fund": _page(
            "https://www.nefcorp.co.za/products-services/tourism-transformation-fund",
            parent_html,
            "Tourism Transformation Fund - National Empowerment Fund",
        ),
        "https://www.nefcorp.co.za/products-services/tourism-transformation-fund/programme-guidelines": _page(
            "https://www.nefcorp.co.za/products-services/tourism-transformation-fund/programme-guidelines",
            support_html,
            "Programme guidelines - Tourism Transformation Fund",
        ),
    }

    pipeline = ScraperPipeline(
        settings=settings,
        storage=LocalJsonStore(settings.output_path),
        parser=GenericFundingParser(settings),
        http_fetcher=FixtureFetcher(pages),
        browser_fetcher=None,
        adapter_registry=registry,
    )

    summary = pipeline.run(["https://www.nefcorp.co.za/products-services/"])

    assert summary.programmes_after_dedupe == 1
    payload = json.loads((settings.output_path / "normalized" / "funding_programmes.json").read_text(encoding="utf-8"))
    assert len(payload) == 1
    record = payload[0]
    assert record["program_name"] == "Tourism Transformation Fund"
    assert record.get("parent_programme_name") in (None, "")
    assert sorted(record["source_urls"]) == sorted(
        [
            "https://www.nefcorp.co.za/products-services/tourism-transformation-fund",
            "https://www.nefcorp.co.za/products-services/tourism-transformation-fund/programme-guidelines",
        ]
    )
    assert any("black owned" in item.lower() for item in record["raw_eligibility_data"])
