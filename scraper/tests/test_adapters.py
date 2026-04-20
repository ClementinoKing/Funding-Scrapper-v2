from __future__ import annotations

from scraper.adapters.base import SiteAdapter
from scraper.adapters.registry import build_default_registry
from scraper.parsers.generic_parser import GenericFundingParser
from scraper.pipeline import ScraperPipeline
from scraper.schemas import FundingProgrammeRecord, PageFetchResult
from scraper.storage.json_store import LocalJsonStore
from scraper.storage.site_repository import SiteDefinition
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


def test_adapter_registry_resolves_generic_adapter_only() -> None:
    registry = build_default_registry()

    assert registry.resolve("https://example.org").key == "generic"
    assert registry.resolve("blog.example.org").key == "generic"
    assert registry.get_by_key("nefcorp").key == "generic"


def test_adapter_registry_builds_db_controlled_site_profiles() -> None:
    registry = build_default_registry()

    adapter = registry.build_for_site(
        adapter_key="nefcorp",
        primary_domain="nefcorp.co.za",
        config={
            "allowed_path_prefixes": ["/products-services/"],
            "strict_path_prefixes": True,
        },
    )

    assert adapter.key == "nefcorp"
    assert adapter.domain == "nefcorp.co.za"
    assert adapter.allowed_path_prefixes == ("/products-services/",)
    assert adapter.strict_path_prefixes is True


def test_adapter_registry_builds_nested_site_extraction_profile() -> None:
    registry = build_default_registry()

    adapter = registry.build_for_site(
        adapter_key="example-site",
        primary_domain="example.org",
        config={
            "site_profile": {
                "content_scope_selectors": [".entry-content"],
                "content_exclude_selectors": [".sidebar", ".share-tools"],
                "candidate_selectors": [".funding-card"],
                "section_heading_selectors": ["h2", ".section-title"],
                "section_aliases": {
                    "eligibility": ["who qualifies"],
                    "documents": ["paperwork needed"],
                },
            }
        },
    )

    profile = adapter.extraction_profile()

    assert profile.content_scope_selectors == (".entry-content",)
    assert profile.content_exclude_selectors == (".sidebar", ".share-tools")
    assert profile.candidate_selectors == (".funding-card",)
    assert profile.section_heading_selectors == ("h2", ".section-title")
    assert profile.section_aliases == {
        "eligibility": ("who qualifies",),
        "documents": ("paperwork needed",),
    }


def test_adapter_selectors_improve_parsing(settings) -> None:
    adapter = SiteAdapter(
        key="generic",
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


def test_site_profile_controls_content_scope_exclusions_and_section_aliases(settings) -> None:
    adapter = SiteAdapter(
        key="generic",
        domain="example.org",
    ).configured(
        {
            "site_profile": {
                "content_scope_selectors": [".entry-content"],
                "content_exclude_selectors": [".sidebar"],
                "candidate_selectors": [".funding-card"],
                "section_heading_selectors": ["h2"],
                "section_aliases": {
                    "eligibility": ["who qualifies"],
                    "documents": ["paperwork needed"],
                },
            }
        }
    )
    parser = GenericFundingParser(settings)
    html = """
    <html>
      <head><title>Custom Funding Page</title></head>
      <body>
        <main class="entry-content">
          <aside class="sidebar">
            <a href="https://example.org/apply/noisy-sidebar-link">Apply now</a>
            <p>Sidebar promotion content that should not affect extraction.</p>
          </aside>
          <article class="funding-card">
            <h2>Innovation Booster Grant</h2>
            <p>Grant for new product development.</p>
            <h2>Who qualifies</h2>
            <p>Registered SMEs with a working prototype.</p>
            <h2>Paperwork needed</h2>
            <p>Certified company registration documents.</p>
            <a href="https://example.org/apply/innovation-booster">Apply online</a>
          </article>
        </main>
      </body>
    </html>
    """
    page = _page("https://example.org/funding", html, "Custom Funding Page")

    result = parser.parse(page, allowed_domains=["example.org"], adapter=adapter)

    assert any(record.program_name == "Innovation Booster Grant" for record in result.records)
    programme = next(record for record in result.records if record.program_name == "Innovation Booster Grant")
    assert programme.application_url == "https://example.org/apply/innovation-booster"
    assert programme.raw_eligibility_data == ["Registered SMEs with a working prototype."]
    assert programme.required_documents == ["Certified company registration documents."]


def test_generic_adapter_allowed_path_prefixes_gate_crawl_scope() -> None:
    adapter = SiteAdapter(
        key="generic",
        domain="example.org",
        allowed_path_prefixes=("/programmes/",),
        include_url_terms=("programme", "apply"),
        exclude_url_terms=("/news/",),
    )

    assert adapter.should_allow_url("https://example.org/programmes/youth-growth-loan")
    assert adapter.should_allow_url("https://example.org/apply/youth-growth-loan")
    assert not adapter.should_allow_url("https://example.org/about")
    assert not adapter.should_allow_url("https://example.org/news/latest-update")


def test_generic_adapter_empty_overrides_preserve_defaults() -> None:
    adapter = SiteAdapter(
        key="generic",
        domain="example.org",
        allowed_path_prefixes=("/funding/",),
        include_url_terms=("grant",),
        exclude_url_terms=("/news/",),
        strict_path_prefixes=True,
        merge_aliases={"overview": ""},
    )

    configured = adapter.configured(
        {
            "allowed_path_prefixes": [],
            "include_url_terms": [],
            "exclude_url_terms": [],
            "strict_path_prefixes": False,
            "allow_root_url": False,
            "merge_aliases": {},
        }
    )

    assert configured.allowed_path_prefixes == ("/funding/",)
    assert configured.include_url_terms == ("grant",)
    assert configured.exclude_url_terms == ("/news/",)
    assert configured.strict_path_prefixes is False
    assert configured.allow_root_url is False
    assert configured.merge_aliases == {"overview": ""}


def test_generic_adapter_strips_numbered_prefix_and_funder_suffix() -> None:
    adapter = SiteAdapter(
        key="generic",
        domain="nefcorp.co.za",
        program_name_strip_prefix_patterns=(r"^\s*\d+\s*[.)-]?\s*",),
        program_name_strip_suffix_patterns=(r"\s*(?:-|—|\||::)\s*National Empowerment Fund\s*$",),
    )
    record = FundingProgrammeRecord(
        source_url="https://www.nefcorp.co.za/products-services/new-venture-capital",
        source_domain="nefcorp.co.za",
        program_name="2. New Venture Capital - National Empowerment Fund",
        funder_name="National Empowerment Fund",
    )

    normalized = adapter.normalize_record(
        record,
        page_type="listing",
        page_url="https://www.nefcorp.co.za/products-services/new-venture-capital",
        page_title="2. New Venture Capital - National Empowerment Fund",
    )

    assert normalized.program_name == "New Venture Capital"


def test_generic_adapter_infers_parent_programme_name_from_numbered_child_url() -> None:
    adapter = SiteAdapter(
        key="generic",
        domain="nefcorp.co.za",
        program_name_strip_prefix_patterns=(r"^\s*\d+\s*[.)-]?\s*",),
        program_name_strip_suffix_patterns=(r"\s*(?:-|—|\||::)\s*National Empowerment Fund\s*$",),
    )
    record = FundingProgrammeRecord(
        source_url="https://www.nefcorp.co.za/products-services/rural-community-development-fund/2-new-venture-capital",
        source_domain="nefcorp.co.za",
        program_name="2. New Venture Capital - National Empowerment Fund",
        funder_name="National Empowerment Fund",
    )

    normalized = adapter.normalize_record(
        record,
        page_type="programme_index_page",
        page_url="https://www.nefcorp.co.za/products-services/rural-community-development-fund/2-new-venture-capital",
        page_title="2. New Venture Capital - National Empowerment Fund",
    )

    assert normalized.program_name == "New Venture Capital"
    assert normalized.parent_programme_name == "Rural Community Development Fund"


def test_generic_adapter_infers_parent_programme_name_from_support_child_url() -> None:
    adapter = SiteAdapter(
        key="generic",
        domain="nefcorp.co.za",
    )
    record = FundingProgrammeRecord(
        source_url="https://www.nefcorp.co.za/products-services/tourism-transformation-fund/programme-guidelines",
        source_domain="nefcorp.co.za",
        program_name="Programme Guidelines",
        funder_name="National Empowerment Fund",
        source_page_title="Programme guidelines - Tourism Transformation Fund",
    )

    normalized = adapter.normalize_record(
        record,
        page_type="support-document",
        page_url="https://www.nefcorp.co.za/products-services/tourism-transformation-fund/programme-guidelines",
        page_title="Programme guidelines - Tourism Transformation Fund",
    )

    assert normalized.parent_programme_name == "Tourism Transformation Fund"


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
                    "exclude_url_terms": ["/news/"],
                },
            )
        ]
    )

    assert summary.total_urls_crawled == 2
    trace = (settings.output_path / "logs" / "crawl_trace.jsonl").read_text(encoding="utf-8")
    assert "products-services/innovation-grant" in trace
    assert "news/latest-update" not in trace
