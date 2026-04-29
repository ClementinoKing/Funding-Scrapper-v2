from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone

import pytest

from scraper.ai.ai_enhancement import AIClassifier
from scraper.config import RuntimeOptions
from scraper.parsers.generic_parser import GenericFundingParser
from scraper.pipeline import ScraperPipeline, build_settings_from_options
from scraper.schemas import FundingProgrammeRecord, PageContentDocument, PageFetchResult
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


def test_pipeline_runs_end_to_end_with_raw_content_and_classified_records(settings, fixture_dir: Path) -> None:
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

    pipeline = ScraperPipeline(
        settings=settings,
        storage=LocalJsonStore(settings.output_path),
        parser=GenericFundingParser(settings),
        http_fetcher=FixtureFetcher(pages),
        browser_fetcher=None,
    )

    summary = pipeline.run(["https://example.org/funding-products"])

    assert summary.pages_fetched_successfully == 3
    assert summary.pages_failed == 0
    assert summary.programmes_after_dedupe == 2

    content_dir = settings.output_path / "raw" / "content"
    content_files = sorted(content_dir.glob("*.json"))
    assert len(content_files) == 3

    first_document = json.loads(content_files[0].read_text(encoding="utf-8"))
    assert first_document["page_url"]
    assert isinstance(first_document["headings"], list)
    assert first_document["full_body_text"]

    payload = json.loads((settings.output_path / "normalized" / "funding_programmes.json").read_text(encoding="utf-8"))
    names = {item["program_name"] for item in payload}
    assert names == {"Youth Growth Loan", "Asset Finance Facility"}
    assert all(item["ai_enriched"] is False for item in payload)
    assert all(item["source_domain"] == "example.org" for item in payload)


def test_pipeline_resume_skips_completed_domains(settings, fixture_dir: Path) -> None:
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

    first_summary = pipeline.run(
        [
            "https://example.org/funding-products",
            "https://anotherfund.org/programmes/asset-finance-facility",
        ]
    )
    assert first_summary.pages_fetched_successfully == 3
    assert first_summary.programmes_after_dedupe >= 2

    second_pipeline = ScraperPipeline(
        settings=settings,
        storage=LocalJsonStore(settings.output_path),
        parser=GenericFundingParser(settings),
        http_fetcher=FixtureFetcher(pages),
        browser_fetcher=None,
    )
    resumed_summary = second_pipeline.run(
        [
            "https://example.org/funding-products",
            "https://anotherfund.org/programmes/asset-finance-facility",
        ]
    )

    assert resumed_summary.total_urls_crawled == 0
    crawl_state = json.loads((settings.output_path / "logs" / "crawl_state.json").read_text(encoding="utf-8"))
    assert crawl_state["completed_domains"] == ["anotherfund.org", "example.org"]


def test_ai_classifier_retries_on_malformed_json(settings, fixture_dir: Path, tmp_path: Path, monkeypatch) -> None:
    html = (fixture_dir / "single_program.html").read_text(encoding="utf-8")
    page = _page(
        "https://example.org/programmes/green-energy-sme-grant",
        html,
        "Green Energy SME Grant - National Empowerment Fund",
    )
    parser = GenericFundingParser(settings)
    document = parser.parse(page, allowed_domains=["example.org"])

    classifier = AIClassifier(
        {"openaiKey": "test", "aiProvider": "openai", "aiModel": "gpt-test"},
        storage=LocalJsonStore(tmp_path),
    )

    responses = iter(
        [
            "not json",
            json.dumps(
                {
                    "records": [
                        {
                            "program_name": "Green Energy SME Grant Plus",
                            "funder_name": "National Empowerment Fund",
                            "source_url": "https://example.org/programmes/green-energy-sme-grant",
                            "source_domain": "example.org",
                            "funding_type": "Grant",
                            "deadline_type": "Unknown",
                            "geography_scope": "National",
                            "application_channel": "Online form",
                            "ai_enriched": True,
                        }
                    ],
                    "notes": ["Recovered after retry."],
                }
            ),
        ]
    )
    calls: list[str] = []

    def fake_call_model(system_prompt: str, user_prompt: str) -> str:
        calls.append(user_prompt)
        return next(responses)

    monkeypatch.setattr(classifier, "_call_model", fake_call_model)

    records = classifier.classify_document(document)

    assert len(records) == 1
    assert records[0].program_name == "Green Energy SME Grant Plus"
    assert len(calls) == 2
    assert any(path.name.endswith("input.json") for path in (tmp_path / "raw" / "ai").glob("*.json"))
    assert any(path.name.endswith("output.json") for path in (tmp_path / "raw" / "ai").glob("*.json"))


def test_ai_classifier_reprompts_for_missing_fields(settings, fixture_dir: Path, tmp_path: Path, monkeypatch) -> None:
    html = (fixture_dir / "single_program.html").read_text(encoding="utf-8")
    page = _page(
        "https://example.org/programmes/green-energy-sme-grant",
        html,
        "Green Energy SME Grant - National Empowerment Fund",
    )
    parser = GenericFundingParser(settings)
    document = parser.parse(page, allowed_domains=["example.org"])

    classifier = AIClassifier(
        {"openaiKey": "test", "aiProvider": "openai", "aiModel": "gpt-test"},
        storage=LocalJsonStore(tmp_path),
    )

    prompts: list[str] = []
    responses = iter(
        [
            json.dumps({"records": [], "notes": ["Need more detail."]}),
            json.dumps(
                {
                    "records": [
                        {
                            "program_name": "Green Energy SME Grant",
                            "funder_name": "National Empowerment Fund",
                            "source_url": "https://example.org/programmes/green-energy-sme-grant",
                            "source_domain": "example.org",
                            "funding_type": "Grant",
                            "deadline_type": "Unknown",
                            "geography_scope": "National",
                            "application_channel": "Online form",
                            "ai_enriched": True,
                        }
                    ],
                    "notes": ["Missing fields filled after retry."],
                }
            ),
        ]
    )

    def fake_call_model(system_prompt: str, user_prompt: str) -> str:
        prompts.append(user_prompt)
        return next(responses)

    monkeypatch.setattr(classifier, "_call_model", fake_call_model)

    records = classifier.classify_document(document)

    assert len(records) == 1
    assert "Decide whether this page is a real funding programme page." in prompts[1]
    assert records[0].program_name == "Green Energy SME Grant"


def test_ai_prompt_builder_prioritizes_relevant_sections(settings) -> None:
    document = PageContentDocument(
        page_url="https://example.org/programmes/green-energy-sme-grant",
        title="Green Energy SME Grant",
        headings=["Green Energy SME Grant", "Eligibility Criteria", "Latest News"],
        full_body_text="Eligibility criteria apply to registered SMEs. The grant provides up to R2 million.",
        structured_sections=[
            {"heading": "Eligibility Criteria", "content": "Registered SMEs with a working prototype."},
            {"heading": "Funding", "content": "The grant provides up to R2 million."},
            {"heading": "News", "content": "Latest newsroom update about events."},
        ],
        source_domain="example.org",
    )

    classifier = AIClassifier({"disableRemoteAi": True}, storage=None)
    user_prompt = classifier._build_user_prompt(document)

    assert "Eligibility Criteria" in user_prompt
    assert "Funding" in user_prompt
    assert "Newsroom update" not in user_prompt
    assert "current_records" in user_prompt
    assert "Green Energy SME Grant" in user_prompt
    assert len(user_prompt) < 20000


def test_ai_prompt_builder_includes_existing_record_values(settings) -> None:
    document = PageContentDocument(
        page_url="https://example.org/programmes/green-energy-sme-grant",
        title="Green Energy SME Grant",
        headings=["Green Energy SME Grant", "Eligibility Criteria", "Funding"],
        full_body_text="Registered SMEs only. The grant provides up to R2 million for clean energy equipment.",
        structured_sections=[
            {"heading": "Eligibility Criteria", "content": "Registered SMEs only."},
            {"heading": "Funding", "content": "The grant provides up to R2 million for clean energy equipment."},
        ],
        source_domain="example.org",
    )

    classifier = AIClassifier({"disableRemoteAi": True}, storage=None)
    user_prompt = classifier._build_user_prompt(document)

    assert "current_records" in user_prompt
    assert "Registered SMEs only" in user_prompt
    assert "Green Energy SME Grant" in user_prompt


def test_ai_enrichment_reuses_passed_records_in_prompt(settings, tmp_path: Path, monkeypatch) -> None:
    document = PageContentDocument(
        page_url="https://example.org/programmes/green-energy-sme-grant",
        title="Green Energy SME Grant",
        headings=["Green Energy SME Grant", "Eligibility Criteria"],
        full_body_text="Registered SMEs only. The grant provides up to R2 million.",
        structured_sections=[
            {"heading": "Eligibility Criteria", "content": "Registered SMEs only."},
            {"heading": "Funding", "content": "The grant provides up to R2 million."},
        ],
        source_domain="example.org",
    )

    existing_record = FundingProgrammeRecord(
        program_name="Green Energy SME Grant",
        funder_name="National Empowerment Fund",
        source_url="https://example.org/programmes/green-energy-sme-grant",
        source_urls=["https://example.org/programmes/green-energy-sme-grant"],
        source_domain="example.org",
        source_page_title="Green Energy SME Grant - National Empowerment Fund",
        scraped_at=datetime.now(timezone.utc),
        funding_type="Grant",
        funding_lines=["The grant provides up to R2 million."],
        raw_eligibility_data=["Registered SMEs only."],
        ai_enriched=True,
        contact_email="apply@example.org",
        notes=["AI updated contact details."],
    )

    classifier = AIClassifier(
        {"openaiKey": "test", "aiProvider": "openai", "aiModel": "gpt-test"},
        storage=LocalJsonStore(tmp_path),
    )

    prompts: list[str] = []

    def fake_call_model(system_prompt: str, user_prompt: str) -> str:
        prompts.append(user_prompt)
        return json.dumps(
            {
                "page_decision": "funding_program",
                "records": [
                    {
                        "program_name": "Green Energy SME Grant",
                        "funder_name": "National Empowerment Fund",
                        "source_url": "https://example.org/programmes/green-energy-sme-grant",
                        "source_domain": "example.org",
                        "funding_type": "Grant",
                        "application_channel": "Online form",
                        "ai_enriched": True,
                    }
                ],
                "notes": ["Updated from existing record state."],
            }
        )

    monkeypatch.setattr(classifier, "_call_model", fake_call_model)

    records = classifier.enrich_records([existing_record], document)

    assert len(records) == 1
    assert "current_records" in prompts[0]
    assert "AI updated contact details." in prompts[0]
    assert "apply@example.org" in prompts[0]
    assert records[0].ai_enriched is True


def test_ai_classifier_strips_numbered_titles_and_keeps_page_source_only(settings, tmp_path: Path) -> None:
    document = PageContentDocument(
        page_url="https://example.org/programmes/entrepreneurship-finance",
        title="1. Entrepreneurship Finance - Example Fund",
        headings=["1. Entrepreneurship Finance"],
        full_body_text="Support for entrepreneurs in the early growth stage.",
        source_domain="example.org",
    )

    classifier = AIClassifier({"disableRemoteAi": True}, storage=LocalJsonStore(tmp_path))
    records = classifier.classify_document(document)

    assert len(records) == 1
    assert records[0].program_name == "Entrepreneurship Finance"
    assert records[0].source_url == document.page_url
    assert records[0].source_urls == [document.page_url]


def test_ai_classifier_routes_interactive_content_into_field_evidence(settings, tmp_path: Path) -> None:
    document = PageContentDocument(
        page_url="https://www.pic.gov.za/early-stage-fund",
        title="Early Stage Fund - Public Investment Corporation",
        headings=["Early Stage Fund", "Eligibility Criteria", "How to Apply"],
        full_body_text="",
        structured_sections=[
            {"heading": "Overview", "content": "Targeted investment support for early-stage businesses."},
        ],
        interactive_sections=[
            {
                "type": "tab",
                "label": "Eligibility Criteria",
                "content": "Applicants must be South African SMEs trading for at least 2 years with turnover below R5 million.",
            },
            {
                "type": "accordion",
                "label": "How to Apply",
                "content": "Apply online at https://www.pic.gov.za/apply/early-stage-fund or email pic@example.org. Applications close on 30 June 2026.",
            },
            {
                "type": "card",
                "label": "Funding Terms",
                "content": "Loans from R250 000 to R2 million repayable over 36 months with monthly instalments.",
            },
            {
                "type": "table",
                "label": "Required Documents",
                "content": "Completed application form | Latest bank statements | Company registration documents",
            },
        ],
        document_links=["https://www.pic.gov.za/docs/early-stage-fund-brochure.pdf"],
        application_links=["https://www.pic.gov.za/apply/early-stage-fund"],
        internal_links=["https://www.pic.gov.za/isibaya"],
        discovered_links=["https://www.pic.gov.za/early-stage-fund"],
        source_domain="pic.gov.za",
    )

    classifier = AIClassifier({"disableRemoteAi": True}, storage=LocalJsonStore(tmp_path))
    records = classifier.classify_document(document)

    assert len(records) == 1
    record = records[0]
    assert record.application_url == "https://www.pic.gov.za/apply/early-stage-fund"
    assert record.contact_email == "pic@example.org"
    assert record.payback_term_max_months == 36
    assert record.required_documents
    assert "raw_application_data" in record.evidence_by_field
    assert "raw_eligibility_data" in record.evidence_by_field
    assert record.field_confidence.get("application_url", 0.0) > 0.5
    assert record.field_confidence.get("payback_term_max_months", 0.0) > 0.5
    assert not record.validation_errors


def test_schema_keeps_funding_lists_as_arrays() -> None:
    record = FundingProgrammeRecord(
        program_name="Expansion Capital",
        funder_name="National Empowerment Fund",
        source_url="https://example.org/programmes/expansion-capital",
        source_urls=["https://example.org/programmes/expansion-capital"],
        source_domain="example.org",
        source_page_title="Expansion Capital - Example Fund",
        scraped_at=datetime.now(timezone.utc),
        funding_type="Loan",
        funding_lines=["Working capital support\nAsset finance support"],
        raw_eligibility_data=["Registered SMEs only\nBlack-owned businesses preferred"],
    )

    assert record.funding_lines == ["Working capital support", "Asset finance support"]
    assert record.raw_eligibility_data == ["Registered SMEs only", "Black-owned businesses preferred"]


def test_ai_eligibility_data_populates_structured_columns(settings, tmp_path: Path) -> None:
    industry_term = next(iter(settings.industry_taxonomy.values()))[0]
    use_term = next(iter(settings.use_of_funds_taxonomy.values()))[0]
    ownership_term = next(iter(settings.ownership_target_keywords.values()))[0]
    entity_term = next(iter(settings.entity_type_keywords.values()))[0]
    cert_term = next(iter(settings.certification_keywords.values()))[0]

    eligibility_text = (
        f"{industry_term} businesses may apply. "
        f"{use_term} support is available. "
        f"Eligible applicants are early stage businesses trading for at least 2 years with annual turnover up to R5 million and 5 to 50 employees. "
        f"{ownership_term} applicants, {entity_term} entities and {cert_term} holders are preferred."
    )

    document = PageContentDocument(
        page_url="https://example.org/programmes/expansion-capital",
        title="Expansion Capital",
        headings=["Eligibility"],
        full_body_text=eligibility_text,
        structured_sections=[{"heading": "Eligibility", "content": eligibility_text}],
        source_domain="example.org",
    )

    classifier = AIClassifier(
        {
            "disableRemoteAi": True,
            "industry_taxonomy": settings.industry_taxonomy,
            "use_of_funds_taxonomy": settings.use_of_funds_taxonomy,
            "ownership_target_keywords": settings.ownership_target_keywords,
            "entity_type_keywords": settings.entity_type_keywords,
            "certification_keywords": settings.certification_keywords,
        },
        storage=LocalJsonStore(tmp_path),
    )

    response = json.dumps(
        {
            "page_decision": "funding_program",
            "page_decision_confidence": 0.95,
            "records": [
                {
                    "program_name": "Expansion Capital",
                    "funder_name": "National Empowerment Fund",
                    "source_url": document.page_url,
                    "source_domain": "example.org",
                    "funding_type": "Loan",
                    "raw_eligibility_data": [eligibility_text],
                    "deadline_type": "Unknown",
                    "geography_scope": "National",
                    "application_channel": "Unknown",
                    "ai_enriched": True,
                }
            ],
            "notes": ["Eligibility mapped from raw eligibility data."],
        }
    )

    classifier._call_model = lambda system_prompt, user_prompt: response  # type: ignore[method-assign]

    records = classifier.classify_document(document)

    assert len(records) == 1
    record = records[0]
    assert len(record.raw_eligibility_data or []) >= 2
    assert any(industry_term.casefold() in item.casefold() for item in record.raw_eligibility_data or [])
    assert any(use_term.casefold() in item.casefold() for item in record.raw_eligibility_data or [])
    assert record.industries
    assert record.use_of_funds
    assert record.business_stage_eligibility
    assert record.turnover_max == 5000000 or record.turnover_max == 5
    assert record.years_in_business_min == 2
    assert record.employee_min == 5
    assert record.ownership_targets
    assert record.entity_types_allowed
    assert record.certifications_required


def test_ai_classifier_respects_non_program_page_decision(settings, fixture_dir: Path, tmp_path: Path, monkeypatch) -> None:
    html = (fixture_dir / "single_program.html").read_text(encoding="utf-8")
    page = _page(
        "https://example.org/news/launch-update",
        html,
        "Launch update - Example Fund",
    )
    parser = GenericFundingParser(settings)
    document = parser.parse(page, allowed_domains=["example.org"])

    classifier = AIClassifier(
        {"openaiKey": "test", "aiProvider": "openai", "aiModel": "gpt-test"},
        storage=LocalJsonStore(tmp_path),
    )

    response = json.dumps(
        {
            "page_decision": "not_funding_program",
            "page_decision_confidence": 0.98,
            "records": [
                {
                    "program_name": "Fake Programme",
                    "funder_name": "Fake Fund",
                    "source_url": document.page_url,
                    "source_domain": "example.org",
                    "funding_type": "Grant",
                    "deadline_type": "Unknown",
                    "geography_scope": "National",
                    "application_channel": "Unknown",
                    "ai_enriched": True,
                }
            ],
            "notes": ["This is not a programme page."],
        }
    )

    monkeypatch.setattr(classifier, "_call_model", lambda system_prompt, user_prompt: response)

    records = classifier.classify_document(document)

    assert records == []


def test_ai_fallback_rejects_image_like_non_program_page(settings, tmp_path: Path) -> None:
    document = PageContentDocument(
        page_url="https://example.org/wp-content/uploads/2023/07/IMG-20230707-WA0005-2.jpg",
        title="IMG-20230707-WA0005-2.jpg (900x1600)",
        headings=["IMG-20230707-WA0005-2.jpg"],
        full_body_text="",
        source_domain="example.org",
    )

    classifier = AIClassifier({"disableRemoteAi": True}, storage=LocalJsonStore(tmp_path))
    records = classifier.classify_document(document)

    assert records == []


def test_build_settings_from_options_ai_flag_overrides_env(monkeypatch) -> None:
    monkeypatch.setenv("SCRAPER_AI_ENRICHMENT", "1")

    disabled = build_settings_from_options(None, None, None, None, None, None, False)
    enabled = build_settings_from_options(None, None, None, None, None, None, True)
    inherited = build_settings_from_options(None, None, None, None, None, None, None)

    assert disabled.ai_enrichment is False
    assert enabled.ai_enrichment is True
    assert inherited.ai_enrichment is True
