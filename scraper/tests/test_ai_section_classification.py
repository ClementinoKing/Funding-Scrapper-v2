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
