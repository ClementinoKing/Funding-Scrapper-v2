from __future__ import annotations

import json

from scraper.config import RuntimeOptions
from scraper.parsers.generic_parser import GenericFundingParser
from scraper.pipeline import ScraperPipeline
from scraper.schemas import PageFetchResult
from scraper.storage.json_store import LocalJsonStore
from scraper.storage.site_repository import SiteDefinition
from scraper.utils.pdf import extract_pdf_text


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


def _page(url: str, html: str, title: str, content_type: str = "text/html") -> PageFetchResult:
    return PageFetchResult(
        url=url,
        requested_url=url,
        canonical_url=url,
        final_url=url,
        status_code=200,
        content_type=content_type,
        html=html,
        title=title,
        fetch_method="http",
        headers={},
        js_rendered=False,
        notes=[],
    )


def test_extract_pdf_text_fallback_reads_simple_pdf_stream() -> None:
    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nstream\nBT (NYDA Grant Programme) Tj ET\nendstream\nendobj\n%%EOF"

    assert "NYDA Grant Programme" in extract_pdf_text(pdf_bytes)


def test_generic_adapter_support_mode_can_be_driven_by_db_config(settings, monkeypatch) -> None:
    monkeypatch.setattr("scraper.pipeline.add_application_verification_note", lambda record, timeout_seconds: record)

    mentorship_html = """
    <html>
      <head><title>Mentorship Programme - NYDA</title></head>
      <body>
        <main>
          <article>
            <h1>Mentorship Programme</h1>
            <p>Business management training and mentorship for young entrepreneurs.</p>
            <p>Apply online to join the programme.</p>
            <a href="https://erp.nyda.gov.za/register/mentorship">Register now</a>
          </article>
        </main>
      </body>
    </html>
    """

    pages = {
        "https://www.nyda.gov.za/Products-Services/Mentorship.html": _page(
            "https://www.nyda.gov.za/Products-Services/Mentorship.html",
            mentorship_html,
            "Mentorship Programme - NYDA",
        ),
        "https://erp.nyda.gov.za/register/mentorship": _page(
            "https://erp.nyda.gov.za/register/mentorship",
            "<html><head><title>Mentorship registration</title></head><body><main><article><h1>Mentorship Programme</h1><p>Register here.</p></article></main></body></html>",
            "Mentorship registration",
        ),
    }

    base_output = settings.output_path.parent
    funding_only_settings = settings.with_overrides(
        RuntimeOptions(output_path=base_output / "nyda-funding-only")
    )
    support_settings = settings.with_overrides(
        RuntimeOptions(output_path=base_output / "nyda-funding-plus-support")
    )

    db_config = {
        "crawl_mode": "funding_plus_support",
        "include_url_terms": [
            "grant",
            "voucher",
            "fund",
            "funding",
            "sponsorship",
            "thusano",
            "mentorship",
            "market linkage",
            "market linkages",
            "business management training",
            "entrepreneurship",
            "products-services",
            "apply",
            "application",
        ],
        "exclude_url_terms": [
            "/news/",
            "/media/",
            "/press/",
            "/careers/",
            "/jobs/",
            "/vacancies/",
            "/internship/",
            "/internships/",
            "/bursary/",
            "/bursaries/",
            "/about/",
        ],
        "discovery_terms": [
            "grant",
            "voucher",
            "fund",
            "funding",
            "sponsorship",
            "thusano",
            "mentorship",
            "market linkage",
            "market linkages",
            "business management training",
            "support",
            "apply",
            "application",
            "products & services",
        ],
        "content_selectors": [
            "main",
            "article",
            ".content",
            ".single-page-content",
            ".entry-content",
            ".products-services",
        ],
        "candidate_selectors": [
            "article",
            "section",
            "div.card",
            ".card",
            ".programme-card",
            ".single-page-content",
            ".entry-content",
        ],
        "parent_page_terms": [
            "products & services",
            "products and services",
            "nyda grant programme",
            "voucher programme",
            "sponsorships",
            "thusano fund",
        ],
        "child_page_terms": [
            "mentorship",
            "market linkage",
            "market linkages",
            "business management training",
            "how to apply",
            "application form",
            "faq",
        ],
        "application_support_terms": [
            "how to apply",
            "application form",
            "faq",
            "checklist",
            "portal",
            "register",
            "application",
            "guidelines",
        ],
        "supporting_programme_terms": [
            "mentorship",
            "market linkage",
            "market linkages",
            "business management training",
        ],
        "support_page_terms": [
            "application form",
            "faq",
            "checklist",
            "portal",
            "register",
            "guidelines",
        ],
        "suppress_support_record_terms": [
            "mentorship",
            "market linkage",
            "market linkages",
            "business management training",
            "business support",
        ],
        "merge_aliases": {
            "nyda voucher programme": "voucher programme",
            "sponsorships & thusano fund": "thusano fund",
            "products & services": "",
        },
    }

    funding_only_fetcher = FixtureFetcher(pages)
    funding_only_pipeline = ScraperPipeline(
        settings=funding_only_settings,
        storage=LocalJsonStore(funding_only_settings.output_path),
        parser=GenericFundingParser(funding_only_settings),
        http_fetcher=funding_only_fetcher,
        browser_fetcher=None,
    )

    funding_only_summary = funding_only_pipeline.run_sites(
        [
            SiteDefinition(
                site_key="nyda",
                display_name="NYDA",
                primary_domain="nyda.gov.za",
                adapter_key="generic",
                seed_urls=("https://www.nyda.gov.za/Products-Services/Mentorship.html",),
                adapter_config={**db_config, "crawl_mode": "funding_only"},
            )
        ]
    )
    assert funding_only_summary.programmes_after_dedupe == 0
    assert "https://erp.nyda.gov.za/register/mentorship" not in funding_only_fetcher.calls

    support_fetcher = FixtureFetcher(pages)
    support_pipeline = ScraperPipeline(
        settings=support_settings,
        storage=LocalJsonStore(support_settings.output_path),
        parser=GenericFundingParser(support_settings),
        http_fetcher=support_fetcher,
        browser_fetcher=None,
    )

    support_summary = support_pipeline.run_sites(
        [
            SiteDefinition(
                site_key="nyda",
                display_name="NYDA",
                primary_domain="nyda.gov.za",
                adapter_key="generic",
                seed_urls=("https://www.nyda.gov.za/Products-Services/Mentorship.html",),
                adapter_config=db_config,
            )
        ]
    )
    assert support_summary.programmes_after_dedupe == 0
    assert "https://erp.nyda.gov.za/register/mentorship" not in support_fetcher.calls
    payload = json.loads((support_settings.output_path / "normalized" / "funding_programmes.json").read_text(encoding="utf-8"))
    assert payload == []
