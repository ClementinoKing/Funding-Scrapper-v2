from __future__ import annotations

import json
from pathlib import Path

from scraper.adapters.nyda import FUNDING_ONLY, FUNDING_PLUS_SUPPORT, NydaSiteAdapter
from scraper.adapters.registry import SiteAdapterRegistry, build_default_registry
from scraper.parsers.generic_parser import GenericFundingParser
from scraper.pipeline import ScraperPipeline
from scraper.config import RuntimeOptions
from scraper.schemas import PageFetchResult
from scraper.storage.json_store import LocalJsonStore
from scraper.utils.pdf import extract_pdf_text


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


def test_nyda_adapter_restricts_scope() -> None:
    adapter = NydaSiteAdapter.build(default_seed_urls=("https://www.nyda.gov.za/",))

    assert adapter.key == "nyda"
    assert adapter.should_allow_url("https://www.nyda.gov.za/Products-Services/NYDA-Voucher-Programme.html")
    assert adapter.should_allow_url("https://erp.nyda.gov.za/faq")
    assert adapter.should_allow_url("https://erp.nyda.gov.za/apply/grant-programme")
    assert not adapter.should_allow_url("https://www.nyda.gov.za/news/latest-update")
    assert not adapter.should_allow_url("https://erp.nyda.gov.za/dashboard")


def test_extract_pdf_text_fallback_reads_simple_pdf_stream() -> None:
    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nstream\nBT (NYDA Grant Programme) Tj ET\nendstream\nendobj\n%%EOF"

    assert "NYDA Grant Programme" in extract_pdf_text(pdf_bytes)


def test_nyda_grant_programme_merges_pdf_form_and_faq(settings, monkeypatch) -> None:
    monkeypatch.setattr("scraper.pipeline.add_application_verification_note", lambda record, timeout_seconds: record)

    adapter = NydaSiteAdapter.build(
        default_seed_urls=(
            "https://www.nyda.gov.za/Products-Services/NYDA-Grant-Programme.html",
            "https://www.nyda.gov.za/Portals/0/WebSitesCreative_MyContentManager/1092/NYDA_Grant_Programme.pdf",
            "https://www.nyda.gov.za/Portals/0/Downloads/Forms/Grant%20and%20Voucher%20Application%20Form.pdf",
            "https://erp.nyda.gov.za/faq",
        ),
    )
    registry = SiteAdapterRegistry(
        adapters={"nyda.gov.za": adapter},
        generic_adapter=build_default_registry().generic_adapter,
    )

    grant_html = """
    <html>
      <head><title>NYDA Grant Programme - NYDA</title></head>
      <body>
        <main>
          <article>
            <h1>NYDA Grant Programme</h1>
            <p>The programme supports movable and immovable assets, bridging finance, shop renovations, working capital, and co-funding for legal entities.</p>
            <p>Eligible entity types include Individuals, Ptys, and Co-operatives.</p>
            <p>Service standard: 30 working days.</p>
            <a href="https://erp.nyda.gov.za/apply/grant-programme">Apply now</a>
            <a href="https://erp.nyda.gov.za/faq">FAQ</a>
            <a href="https://www.nyda.gov.za/Portals/0/WebSitesCreative_MyContentManager/1092/NYDA_Grant_Programme.pdf">Programme PDF</a>
            <a href="https://www.nyda.gov.za/Portals/0/Downloads/Forms/Grant%20and%20Voucher%20Application%20Form.pdf">Application form</a>
          </article>
        </main>
      </body>
    </html>
    """
    pdf_text = """
    NYDA Grant Programme
    Use of funds: movable and immovable assets, bridging finance, shop renovations, working capital.
    Entity types allowed: Individuals, Ptys and Co-operatives.
    Service standard: 30 working days.
    """
    form_pdf_text = """
    NYDA Grant Programme
    Application form for the NYDA Grant Programme.
    Required documents: ID copy, business registration documents, bank statements, and proof of address.
    Application route: online form and FAQ support.
    """
    faq_html = """
    <html>
      <head><title>NYDA Grant Programme - NYDA</title></head>
      <body>
        <main>
          <article>
            <h1>NYDA Grant Programme</h1>
            <p>Apply online using the portal or the application form.</p>
            <p>Email grants@nyda.gov.za for questions.</p>
            <a href="https://erp.nyda.gov.za/apply/grant-programme">Apply now</a>
          </article>
        </main>
      </body>
    </html>
    """

    pages = {
        "https://www.nyda.gov.za/Products-Services/NYDA-Grant-Programme.html": _page(
            "https://www.nyda.gov.za/Products-Services/NYDA-Grant-Programme.html",
            grant_html,
            "NYDA Grant Programme - NYDA",
        ),
        "https://www.nyda.gov.za/Portals/0/WebSitesCreative_MyContentManager/1092/NYDA_Grant_Programme.pdf": _page(
            "https://www.nyda.gov.za/Portals/0/WebSitesCreative_MyContentManager/1092/NYDA_Grant_Programme.pdf",
            pdf_text,
            "NYDA Grant Programme",
            content_type="application/pdf",
        ),
        "https://www.nyda.gov.za/Portals/0/Downloads/Forms/Grant%20and%20Voucher%20Application%20Form.pdf": _page(
            "https://www.nyda.gov.za/Portals/0/Downloads/Forms/Grant%20and%20Voucher%20Application%20Form.pdf",
            form_pdf_text,
            "NYDA Grant Programme",
            content_type="application/pdf",
        ),
        "https://erp.nyda.gov.za/faq": _page(
            "https://erp.nyda.gov.za/faq",
            faq_html,
            "NYDA Grant Programme FAQ - NYDA",
        ),
        "https://erp.nyda.gov.za/apply/grant-programme": _page(
            "https://erp.nyda.gov.za/apply/grant-programme",
            "<html><head><title>NYDA Grant Programme - NYDA</title></head><body><main><article><h1>NYDA Grant Programme</h1><p>Complete the online application.</p></article></main></body></html>",
            "NYDA Grant Programme - NYDA",
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

    summary = pipeline.run(["https://www.nyda.gov.za/Products-Services/NYDA-Grant-Programme.html"])

    assert summary.programmes_after_dedupe == 1
    payload = json.loads((settings.output_path / "normalized" / "funding_programmes.json").read_text(encoding="utf-8"))
    assert len(payload) == 1
    record = payload[0]
    assert record["program_name"] == "NYDA Grant Programme"
    assert record["funding_type"] == "Grant"
    assert record["programme_nature"] == "direct_funding"
    assert record["display_category"] == "funding"
    assert sorted(record["source_urls"]) == sorted(
        [
            "https://www.nyda.gov.za/Products-Services/NYDA-Grant-Programme.html",
            "https://www.nyda.gov.za/Portals/0/WebSitesCreative_MyContentManager/1092/NYDA_Grant_Programme.pdf",
            "https://www.nyda.gov.za/Portals/0/Downloads/Forms/Grant%20and%20Voucher%20Application%20Form.pdf",
            "https://erp.nyda.gov.za/faq",
        ]
    )
    assert any(document.endswith("Grant%20and%20Voucher%20Application%20Form.pdf") for document in record["related_documents"])
    assert "grants@nyda.gov.za" == record["contact_email"]
    assert record["application_url"].startswith("https://erp.nyda.gov.za/")


def test_nyda_support_programmes_follow_mode(settings, monkeypatch) -> None:
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

    funding_only_settings = settings.with_overrides(
        RuntimeOptions(output_path=settings.output_path.parent / "nyda-funding-only")
    )
    support_settings = settings.with_overrides(
        RuntimeOptions(output_path=settings.output_path.parent / "nyda-funding-plus-support")
    )

    funding_only_registry = SiteAdapterRegistry(
        adapters={
            "nyda.gov.za": NydaSiteAdapter.build(
                crawl_mode=FUNDING_ONLY,
                default_seed_urls=("https://www.nyda.gov.za/Products-Services/Mentorship.html",),
            )
        },
        generic_adapter=build_default_registry().generic_adapter,
    )
    funding_only_pipeline = ScraperPipeline(
        settings=funding_only_settings,
        storage=LocalJsonStore(funding_only_settings.output_path),
        parser=GenericFundingParser(funding_only_settings),
        http_fetcher=FixtureFetcher(pages),
        browser_fetcher=None,
        adapter_registry=funding_only_registry,
    )

    funding_only_summary = funding_only_pipeline.run(["https://www.nyda.gov.za/Products-Services/Mentorship.html"])
    assert funding_only_summary.programmes_after_dedupe == 0

    support_registry = SiteAdapterRegistry(
        adapters={
            "nyda.gov.za": NydaSiteAdapter.build(
                crawl_mode=FUNDING_PLUS_SUPPORT,
                default_seed_urls=("https://www.nyda.gov.za/Products-Services/Mentorship.html",),
            )
        },
        generic_adapter=build_default_registry().generic_adapter,
    )
    support_pipeline = ScraperPipeline(
        settings=support_settings,
        storage=LocalJsonStore(support_settings.output_path),
        parser=GenericFundingParser(support_settings),
        http_fetcher=FixtureFetcher(pages),
        browser_fetcher=None,
        adapter_registry=support_registry,
    )

    support_summary = support_pipeline.run(["https://www.nyda.gov.za/Products-Services/Mentorship.html"])
    assert support_summary.programmes_after_dedupe == 1
    payload = json.loads(
        (support_settings.output_path / "normalized" / "funding_programmes.json").read_text(encoding="utf-8")
    )
    record = next(item for item in payload if item["program_name"] == "Mentorship Programme")
    assert record["programme_nature"] == "non_financial_support"
    assert record["display_category"] == "support"
    assert record["support_type"] == "mentorship"
