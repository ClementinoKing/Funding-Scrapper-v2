from __future__ import annotations

import json

import httpx

from scraper.config import SupabaseSettings
from scraper.storage.supabase_store import SupabaseUploader, _sanitize_records_for_upload


class FakeResponse:
    def __init__(self, payload, status_code: int = 200, text: str = ""):
        self._payload = payload
        self.status_code = status_code
        self.text = text or json.dumps(payload)
        self.request = httpx.Request("POST", "https://example.supabase.co/rest/v1/rpc/ingest_funding_programmes")

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("HTTP error", request=self.request, response=self)


class TimeoutAwareClient:
    def __init__(self):
        self.request_sizes: list[int] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, headers=None, json=None):
        records = json.get("records", []) if isinstance(json, dict) else []
        self.request_sizes.append(len(records))
        if len(records) > 2:
            return FakeResponse(
                {"code": "57014", "message": "canceling statement due to statement timeout"},
                status_code=500,
                text='{"code":"57014","message":"canceling statement due to statement timeout"}',
            )
        return FakeResponse({"upserted_records": len(records), "status": "ok"}, status_code=200)


def test_supabase_uploader_splits_timeout_batches() -> None:
    settings = SupabaseSettings(url="https://example.supabase.co", anon_key="anon")
    client = TimeoutAwareClient()
    uploader = SupabaseUploader(
        settings,
        batch_size=4,
        client_factory=lambda **kwargs: client,
    )

    records = [
        {
            "source_url": f"https://example.org/programmes/{index}",
            "source_domain": "example.org",
            "program_name": f"Programme {index}",
            "funder_name": "Example Fund",
        }
        for index in range(5)
    ]

    result = uploader.upload(records)

    assert client.request_sizes == [4, 4, 2, 2, 1]
    assert result["upserted_records"] == 5
    assert result["_upload_meta"]["input_records"] == 5
    assert result["_upload_meta"]["sanitized_records"] == 5
    assert result["_upload_meta"]["batch_size"] == 4
    assert result["_upload_meta"]["batch_count"] == 3
    assert len(result["batch_results"]) == 3


def test_supabase_uploader_prefers_ai_enriched_records_on_tie() -> None:
    records = [
        {
            "source_url": "https://example.org/programmes/ai-preference",
            "source_domain": "example.org",
            "program_name": "AI Preference Grant",
            "funder_name": "Example Fund",
            "ai_enriched": False,
        },
        {
            "source_url": "https://example.org/programmes/ai-preference",
            "source_domain": "example.org",
            "program_name": "AI Preference Grant",
            "funder_name": "Example Fund",
            "ai_enriched": True,
        },
    ]

    payload, meta = _sanitize_records_for_upload(records)

    assert meta["discarded_duplicate_source_url_records"] == 1
    assert payload[0]["ai_enriched"] is True


def test_supabase_upload_sanitizer_normalizes_repayment_frequency_for_legacy_constraint() -> None:
    payload, meta = _sanitize_records_for_upload(
        [
            {
                "source_url": "https://example.org/programmes/once-off",
                "source_domain": "example.org",
                "program_name": "Once Off Incentive",
                "funder_name": "Example Fund",
                "repayment_frequency": "Once-off",
            }
        ]
    )

    assert meta["sanitized_records"] == 1
    assert payload[0]["repayment_frequency"] == "Variable"
    assert any("Once-off to Variable" in note for note in payload[0]["notes"])


def test_supabase_upload_sanitizer_removes_nested_null_bytes() -> None:
    payload, meta = _sanitize_records_for_upload(
        [
            {
                "source_url": "https://example.org/programmes/null-byte",
                "source_domain": "example.org",
                "program_name": "Null Byte\x00 Grant",
                "funder_name": "Example Fund",
                "raw_funding_offer_data": ["Funding support\x00 for qualifying firms."],
                "raw_eligibility_data": ["Registered\x00 businesses"],
                "raw_text_snippets": {"terms": ["Applications\x00 are open"]},
            }
        ]
    )

    serialized = json.dumps(payload)

    assert meta["sanitized_records"] == 1
    assert payload[0]["program_name"] == "Null Byte Grant"
    assert payload[0]["raw_funding_offer_data"] == ["Funding support for qualifying firms."]
    assert payload[0]["raw_eligibility_data"] == ["Registered businesses"]
    assert payload[0]["raw_text_snippets"]["terms"] == ["Applications are open"]
    assert "\\u0000" not in serialized


def test_supabase_upload_sanitizer_preserves_web_search_metadata() -> None:
    payload, meta = _sanitize_records_for_upload(
        [
            {
                "source_url": "https://example.org/programmes/search-programme",
                "source_domain": "example.org",
                "source_page_title": "Search Programme",
                "program_name": "Search Programme",
                "funder_name": "Example Fund",
                "raw_text_snippets": {
                    "web_search_metadata": [
                        "source_type=official_website",
                        "extracted_from_search=true",
                        "confidence_score=91",
                    ]
                },
                "evidence_by_field": {
                    "web_search_metadata": [
                        "source_type=official_website",
                        "extracted_from_search=true",
                    ]
                },
                "extraction_confidence": {"program_name": 0.91, "source_url": 0.91},
                "notes": ["OpenAI Web Search extraction.", "confidence_score=91"],
            }
        ]
    )

    assert meta["sanitized_records"] == 1
    assert payload[0]["raw_text_snippets"]["web_search_metadata"][1] == "extracted_from_search=true"
    assert payload[0]["evidence_by_field"]["web_search_metadata"][0] == "source_type=official_website"
    assert payload[0]["extraction_confidence"]["program_name"] == 0.91
    assert "confidence_score=91" in payload[0]["notes"]
