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
