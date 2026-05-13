from __future__ import annotations

import json
from datetime import datetime, timezone

from scraper.ai.ai_enhancement import AIClassifier
from scraper.schemas import FundingProgrammeRecord, PageContentDocument, PageContentSection
from scraper.utils.dedupe import dedupe_records


class StubClassifier(AIClassifier):
    def __init__(self, response: dict):
        super().__init__({"openaiKey": "test", "aiProvider": "openai", "disableRemoteAi": False})
        self._response = response
        self.call_count = 0

    def _call_model(self, system_prompt: str, user_prompt: str) -> str:
        self.call_count += 1
        return json.dumps(self._response)


def test_ai_enhancer_rejects_support_programmes_before_persistence() -> None:
    document = PageContentDocument(
        page_url="https://example.org/mentorship",
        title="Mentorship Programme",
        page_title="Mentorship Programme",
        source_domain="example.org",
        full_body_text="Business mentorship and training support for founders. Apply online.",
    )
    classifier = StubClassifier(
        {
            "page_decision": "not_funding_program",
            "page_type": "support_programme",
            "records": [],
            "notes": ["Support-only page."],
        }
    )

    records = classifier.classify_document(document)

    assert records == []


def test_ai_enhancer_skips_ai_for_obvious_non_program_pages() -> None:
    document = PageContentDocument(
        page_url="https://example.org/investment-philosophy",
        title="Investment Philosophy",
        page_title="Investment Philosophy",
        source_domain="example.org",
        full_body_text="Our investment philosophy and governance process are outlined here.",
    )
    classifier = StubClassifier(
        {
            "page_decision": "funding_program",
            "page_type": "generic_content",
            "records": [
                {
                    "program_name": "Should Not Be Used",
                    "funder_name": "Example Agency",
                    "funding_type": "Grant",
                }
            ],
            "notes": [],
        }
    )

    records = classifier.classify_document(document)

    assert records == []
    assert classifier.call_count == 0


def test_ai_enhancer_rejects_technology_station_pages() -> None:
    document = PageContentDocument(
        page_url="https://example.org/technology-station",
        title="Technology Station",
        page_title="Technology Station",
        source_domain="example.org",
        full_body_text="Technology station support for prototyping and technical assistance.",
    )
    classifier = StubClassifier(
        {
            "page_decision": "funding_program",
            "page_type": "technology_station",
            "records": [
                {
                    "program_name": "Technology Station",
                    "funder_name": "Example Agency",
                    "funding_type": "Unknown",
                }
            ],
            "notes": [],
        }
    )

    records = classifier.classify_document(document)

    assert records == []


def test_ai_enhancer_validates_money_after_ai_output() -> None:
    document = PageContentDocument(
        page_url="https://example.org/programmes/green-grant",
        title="Green Grant",
        page_title="Green Grant",
        source_domain="example.org",
        full_body_text="Green Grant supports SMEs. Call 011 555 0100 for more information and apply online.",
        structured_sections=[PageContentSection(heading="Overview", content="Green Grant supports SMEs. Call 011 555 0100.")],
    )
    classifier = StubClassifier(
        {
            "page_decision": "funding_program",
            "page_type": "funding_programme",
            "records": [
                {
                    "program_name": "Green Grant",
                    "funder_name": "Example Agency",
                    "funding_type": "Grant",
                    "ticket_max": 115550100,
                    "raw_funding_offer_data": ["Call 011 555 0100 for more information."],
                }
            ],
            "notes": [],
        }
    )

    records = classifier.classify_document(document)

    assert len(records) == 1
    assert records[0].ticket_max is None
    assert "invalid_money_context" in records[0].needs_review_reasons


def test_ai_enhancer_rejects_listing_with_unknown_funding_type() -> None:
    document = PageContentDocument(
        page_url="https://example.org/funding-opportunities",
        title="Funding Opportunities",
        page_title="Funding Opportunities",
        source_domain="example.org",
        full_body_text="Browse funding opportunities for SMEs and startups.",
    )
    classifier = StubClassifier(
        {
            "page_decision": "funding_program",
            "page_type": "funding_listing",
            "records": [
                {
                    "program_name": "Green Finance Support",
                    "funder_name": "Example Agency",
                    "funding_type": "Unknown",
                }
            ],
            "notes": [],
        }
    )

    records = classifier.classify_document(document)

    assert records == []


def test_ai_enhancer_rejects_faq_support_record_with_unknown_funding_type() -> None:
    document = PageContentDocument(
        page_url="https://www.pic.gov.za/faq-isibaya",
        title="Isibaya FAQ",
        page_title="Isibaya FAQ",
        source_domain="pic.gov.za",
        full_body_text="Frequently asked questions about Isibaya applications.",
    )
    classifier = StubClassifier(
        {
            "page_decision": "funding_program",
            "page_type": "funding_programme",
            "records": [
                {
                    "program_name": "Isibaya",
                    "funder_name": "Public Investment Corporation",
                    "funding_type": "Unknown",
                }
            ],
            "notes": [],
        }
    )

    records = classifier.classify_document(document)

    assert records == []


def test_ai_enhancer_accepts_recoverable_response_shape_variants() -> None:
    document = PageContentDocument(
        page_url="https://example.org/programmes/green-grant",
        title="Green Grant",
        page_title="Green Grant",
        source_domain="example.org",
        full_body_text="Green Grant offers grant funding up to R1 million for SMEs. Apply online.",
        structured_sections=[PageContentSection(heading="Funding", content="Grant funding up to R1 million for SMEs.")],
    )
    classifier = StubClassifier(
        {
            "page_decision": "funding_program",
            "page_type": "funding_programme",
            "records": [
                {
                    "program_name": "Green Grant",
                    "funder_name": "Example Agency",
                    "funding_type": "Grant",
                    "ticket_max": 1000000,
                    "extraction_confidence": 0.95,
                    "raw_funding_offer_data": ["Grant funding up to R1 million for SMEs."],
                }
            ],
            "notes": "",
        }
    )

    records = classifier.classify_document(document)

    assert len(records) == 1
    assert records[0].program_name == "Green Grant"


def test_ai_enhancer_forces_review_for_listing_even_with_known_funding_type() -> None:
    document = PageContentDocument(
        page_url="https://example.org/funding-opportunities/green-grant",
        title="Green Grant listing detail",
        page_title="Green Grant listing detail",
        source_domain="example.org",
        full_body_text="Green Grant offers grant funding up to R1 million for SMEs.",
        structured_sections=[PageContentSection(heading="Funding", content="Grant funding up to R1 million for qualifying SMEs.")],
    )
    classifier = StubClassifier(
        {
            "page_decision": "funding_program",
            "page_type": "funding_listing",
            "records": [
                {
                    "program_name": "Green Grant",
                    "funder_name": "Example Agency",
                    "funding_type": "Grant",
                    "ticket_max": 1000000,
                    "raw_funding_offer_data": ["Grant funding up to R1 million for qualifying SMEs."],
                }
            ],
            "notes": [],
        }
    )

    records = classifier.classify_document(document)

    assert len(records) == 1
    assert records[0].needs_review is True
    assert "unconfirmed_page_type" in records[0].needs_review_reasons


def test_ai_enhancer_allows_clean_funding_programme_to_clear_review() -> None:
    document = PageContentDocument(
        page_url="https://example.org/programmes/green-grant",
        title="Green Grant - Example Agency",
        page_title="Green Grant - Example Agency",
        source_domain="example.org",
        full_body_text="Green Grant offers grant funding up to R1 million for SMEs. Apply online.",
        structured_sections=[PageContentSection(heading="Funding", content="Grant funding up to R1 million for qualifying SMEs.")],
        application_links=["https://example.org/apply/green-grant"],
    )
    classifier = StubClassifier(
        {
            "page_decision": "funding_program",
            "page_type": "funding_programme",
            "records": [
                {
                    "program_name": "Green Grant",
                    "funder_name": "Example Agency",
                    "funding_type": "Grant",
                    "ticket_max": 1000000,
                    "raw_funding_offer_data": ["Grant funding up to R1 million for qualifying SMEs."],
                    "application_url": "https://example.org/apply/green-grant",
                }
            ],
            "notes": [],
        }
    )

    records = classifier.classify_document(document)

    assert len(records) == 1
    assert records[0].needs_review is False


def test_ai_enhancer_scores_related_pages_before_ai_merge_judging() -> None:
    classifier = StubClassifier({"page_decision": "not_funding_program", "page_type": "generic_content", "records": []})
    left = FundingProgrammeRecord(
        program_name="Green Growth Fund",
        funder_name="Example Agency",
        source_url="https://example.org/programmes/green-growth-fund",
        source_urls=["https://example.org/programmes/green-growth-fund"],
        source_domain="example.org",
        scraped_at=datetime.now(timezone.utc),
        page_type="funding_programme",
        page_role="overview",
    )
    right = FundingProgrammeRecord(
        program_name="Green Growth Fund",
        funder_name="Example Agency",
        parent_programme_name="Green Growth Fund",
        source_url="https://example.org/programmes/green-growth-fund/eligibility",
        source_urls=["https://example.org/programmes/green-growth-fund/eligibility"],
        source_domain="example.org",
        scraped_at=datetime.now(timezone.utc),
        page_type="funding_programme",
        page_role="eligibility",
    )

    scored = classifier.score_duplicate_records(left, right)

    assert scored["decision"] == "merge"
    assert scored["score"] >= 65


def test_cross_page_merge_detects_conflicting_values() -> None:
    overview = FundingProgrammeRecord(
        program_name="Green Growth Fund",
        funder_name="Example Agency",
        source_url="https://example.org/programmes/green-growth-fund",
        source_urls=["https://example.org/programmes/green-growth-fund"],
        source_domain="example.org",
        scraped_at=datetime.now(timezone.utc),
        page_type="funding_programme",
        page_role="overview",
        application_url="https://example.org/apply/green-growth-fund",
        field_evidence={
            "application_url": [
                {
                    "field_name": "application_url",
                    "normalized_value": "https://example.org/apply/green-growth-fund",
                    "raw_value": "https://example.org/apply/green-growth-fund",
                    "evidence_text": "Apply online",
                    "source_url": "https://example.org/programmes/green-growth-fund",
                    "confidence": 0.9,
                }
            ]
        },
    )
    application = FundingProgrammeRecord(
        program_name="Green Growth Fund",
        funder_name="Example Agency",
        parent_programme_name="Green Growth Fund",
        source_url="https://example.org/programmes/green-growth-fund/application",
        source_urls=["https://example.org/programmes/green-growth-fund/application"],
        source_domain="example.org",
        scraped_at=datetime.now(timezone.utc),
        page_type="funding_programme",
        page_role="application",
        application_url="https://portal.example.org/green-growth-fund",
        field_evidence={
            "application_url": [
                {
                    "field_name": "application_url",
                    "normalized_value": "https://portal.example.org/green-growth-fund",
                    "raw_value": "https://portal.example.org/green-growth-fund",
                    "evidence_text": "Submit application here",
                    "source_url": "https://example.org/programmes/green-growth-fund/application",
                    "confidence": 0.9,
                }
            ]
        },
    )

    classifier = StubClassifier({"page_decision": "not_funding_program", "page_type": "generic_content", "records": []})
    merged = dedupe_records([overview, application], merge_decider=classifier)

    assert len(merged) == 1
    assert "application_url" in merged[0].field_conflicts
    assert "conflicting_field_values" in merged[0].needs_review_reasons
