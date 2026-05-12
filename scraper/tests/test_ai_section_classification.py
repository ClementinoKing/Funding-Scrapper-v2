from __future__ import annotations

import json

from scraper.ai.ai_enhancement import AIClassifier
from scraper.schemas import PageContentDocument, PageContentSection


class StubAIClassifier(AIClassifier):
    def _call_model(self, system_prompt: str, user_prompt: str) -> str:
        return json.dumps(
            {
                "page_decision": "funding_program",
                "page_type": "funding_listing",
                "page_decision_confidence": 0.91,
                "records": [
                    {
                        "program_name": "Green Grant",
                        "funder_name": "Example Agency",
                        "funding_type": "Grant",
                        "raw_funding_offer_data": ["Grant funding up to R1 million."],
                        "ticket_max": 1000000,
                        "currency": "ZAR",
                    },
                    {
                        "program_name": "Youth Loan",
                        "funder_name": "Example Agency",
                        "funding_type": "Loan",
                        "raw_funding_offer_data": ["Loan amount between R200 000 and R2 million."],
                        "ticket_min": 200000,
                        "ticket_max": 2000000,
                        "currency": "ZAR",
                    },
                ],
                "notes": ["Section-based listing classification."],
            }
        )


class SingleAggregateAIClassifier(AIClassifier):
    def _call_model(self, system_prompt: str, user_prompt: str) -> str:
        return json.dumps(
            {
                "page_decision": "funding_program",
                "page_type": "funding_listing",
                "page_decision_confidence": 0.88,
                "records": [
                    {
                        "program_name": "Isibaya Fund",
                        "funder_name": "Public Investment Corporation",
                        "funding_type": "Equity",
                        "raw_funding_offer_data": ["Isibaya provides developmental investment funding."],
                    }
                ],
                "notes": ["Model returned a single aggregate listing record."],
            }
        )


def test_ai_classification_can_emit_multiple_records_from_heading_sections() -> None:
    document = PageContentDocument(
        page_url="https://example.org/funding",
        title="Funding Opportunities",
        page_title="Funding Opportunities",
        source_domain="example.org",
        full_body_text=(
            "Green Grant provides grant funding up to R1 million. "
            "Youth Loan provides loan amount between R200 000 and R2 million."
        ),
        headings=["Green Grant", "Youth Loan"],
        structured_sections=[
            PageContentSection(heading="Green Grant", content="Grant funding up to R1 million."),
            PageContentSection(heading="Youth Loan", content="Loan amount between R200 000 and R2 million."),
        ],
    )
    classifier = StubAIClassifier({"openaiKey": "test", "aiProvider": "openai", "disableRemoteAi": False})

    records = classifier.classify_document(document)

    assert [record.program_name for record in records] == ["Green Grant", "Youth Loan"]
    assert {record.page_type for record in records} == {"funding_listing"}


def test_ai_classification_recovers_missing_programmes_from_listing_sections() -> None:
    document = PageContentDocument(
        page_url="https://www.pic.gov.za/isibaya",
        title="Isibaya Fund",
        page_title="Isibaya Fund",
        source_domain="pic.gov.za",
        full_body_text=(
            "SME Fund provides equity investment funding for growing businesses. "
            "Affordable Housing Fund provides investment funding for social housing projects."
        ),
        headings=["SME Fund", "Affordable Housing Fund"],
        structured_sections=[
            PageContentSection(
                heading="SME Fund",
                content="Equity investment funding for growing small and medium businesses.",
            ),
            PageContentSection(
                heading="Affordable Housing Fund",
                content="Investment funding for affordable and social housing projects.",
            ),
        ],
    )
    classifier = SingleAggregateAIClassifier({"openaiKey": "test", "aiProvider": "openai", "disableRemoteAi": False})

    records = classifier.classify_document(document)

    assert [record.program_name for record in records] == ["SME Fund", "Affordable Housing Fund"]
    assert {record.source_url for record in records} == {"https://www.pic.gov.za/isibaya"}
    assert {record.page_type for record in records} == {"funding_listing"}


def test_ai_recovery_does_not_promote_generic_important_information_section() -> None:
    document = PageContentDocument(
        page_url="https://www.pic.gov.za/isibaya",
        title="Isibaya Fund",
        page_title="Isibaya Fund",
        source_domain="pic.gov.za",
        full_body_text=(
            "Isibaya Fund provides developmental investment funding. "
            "Important Information: all investments are subject to due diligence."
        ),
        headings=["Isibaya Fund", "Important Information"],
        structured_sections=[
            PageContentSection(
                heading="Isibaya Fund",
                content="Developmental equity investment funding for qualifying businesses.",
            ),
            PageContentSection(
                heading="Important Information",
                content="All investments are subject to due diligence and PIC approval.",
            ),
        ],
    )
    classifier = SingleAggregateAIClassifier({"openaiKey": "test", "aiProvider": "openai", "disableRemoteAi": False})

    records = classifier.classify_document(document)

    assert [record.program_name for record in records] == ["Isibaya Fund"]
    assert records[0].funder_name == "Public Investment Corporation"


def test_ai_recovery_does_not_split_homepage_navigation_cards() -> None:
    document = PageContentDocument(
        page_url="https://www.pic.gov.za/",
        title="Public Investment Corporation",
        page_title="Public Investment Corporation",
        source_domain="pic.gov.za",
        full_body_text="Isibaya Fund developmental investment. Early Stage Fund investment.",
        headings=["Isibaya Fund", "Early Stage Fund"],
        structured_sections=[
            PageContentSection(heading="Isibaya Fund", content="Developmental investment funding."),
            PageContentSection(heading="Early Stage Fund", content="Investment funding for early-stage businesses."),
        ],
    )
    classifier = SingleAggregateAIClassifier({"openaiKey": "test", "aiProvider": "openai", "disableRemoteAi": False})

    records = classifier.classify_document(document)

    assert records == []
