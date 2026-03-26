"""Supabase uploader for normalized scraper artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from scraper.config import SupabaseSettings


class SupabaseUploader:
    """Push normalized scraper output into Supabase through an RPC function."""

    def __init__(self, settings: SupabaseSettings) -> None:
        self.settings = settings

    def _headers(self) -> Dict[str, str]:
        return {
            "apikey": self.settings.anon_key,
            "Authorization": "Bearer %s" % self.settings.bearer_token,
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def upload(self, records: Any, run_summary: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = {
            "records": records,
            "run_summary": run_summary or {},
        }
        url = "%s/rest/v1/rpc/%s" % (self.settings.url, self.settings.rpc_name)
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            response = client.post(url, headers=self._headers(), json=payload)
            response.raise_for_status()
            if response.text.strip():
                return response.json()
            return {"status_code": response.status_code}

    def upload_from_files(self, normalized_json_path: Path, run_summary_path: Optional[Path] = None) -> Dict[str, Any]:
        records = json.loads(normalized_json_path.read_text(encoding="utf-8"))
        run_summary = None
        if run_summary_path and run_summary_path.exists():
            run_summary = json.loads(run_summary_path.read_text(encoding="utf-8"))
        return self.upload(records=records, run_summary=run_summary)

