"""Supabase uploader for normalized scraper artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import NAMESPACE_URL, uuid5

import httpx

from scraper.config import SupabaseSettings
from scraper.schemas import FundingProgrammeRecord
from scraper.utils.quality import score_programme_quality
from scraper.utils.text import clean_text, generate_program_id, looks_like_support_title, slugify
from scraper.utils.urls import canonicalize_url


def _normalize_record_identity(record: FundingProgrammeRecord) -> FundingProgrammeRecord:
    normalized = record.model_copy(deep=True)
    normalized.program_id = generate_program_id(normalized.source_domain, normalized.funder_name, normalized.program_name)
    normalized.id = str(uuid5(NAMESPACE_URL, f"{normalized.source_domain}:{normalized.program_id}"))
    normalized.program_slug = slugify(normalized.program_name or normalized.program_id, max_length=80)
    normalized.funder_slug = slugify(normalized.funder_name or normalized.source_domain, max_length=80)
    return FundingProgrammeRecord.model_validate(normalized.model_dump(mode="python"))


def _record_rank(record: FundingProgrammeRecord) -> Tuple[int, int, int, int, int, int, int]:
    score, _reasons, blockers = score_programme_quality(record)
    program_name = clean_text(record.program_name or "")
    has_heading_like_title = looks_like_support_title(program_name) or program_name.endswith(":")
    has_sentence_like_title = len(program_name.split()) >= 10
    supporting_signal_count = sum(
        1
        for value in (
            record.ticket_min,
            record.ticket_max,
            record.program_budget_total,
            record.application_url,
            record.contact_email,
            record.contact_phone,
        )
        if value is not None
    )
    return (
        score,
        1 if record.ai_enriched else 0,
        int(record.overall_confidence() * 100),
        supporting_signal_count,
        -len(blockers),
        0 if has_heading_like_title else 1,
        0 if has_sentence_like_title else 1,
    )


def _sanitize_records_for_upload(records: Any) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    normalized_records = [_normalize_record_identity(FundingProgrammeRecord.model_validate(item)) for item in records]
    grouped: Dict[str, List[FundingProgrammeRecord]] = {}
    for record in normalized_records:
        grouped.setdefault(canonicalize_url(record.source_url), []).append(record)

    sanitized: List[FundingProgrammeRecord] = []
    collapsed_groups = 0
    discarded_records = 0

    for group in grouped.values():
        if len(group) == 1:
            sanitized.append(group[0])
            continue

        collapsed_groups += 1
        ranked = sorted(group, key=_record_rank, reverse=True)
        winner = ranked[0].model_copy(deep=True)
        winner.notes = list(
            dict.fromkeys(
                [
                    *winner.notes,
                    "Upload sanitizer kept the strongest programme candidate for this page and dropped weaker duplicates.",
                ]
            )
        )
        sanitized.append(winner)
        discarded_records += len(group) - 1

    payload = [record.model_dump(mode="json") for record in sanitized]
    meta = {
        "input_records": len(normalized_records),
        "sanitized_records": len(payload),
        "collapsed_source_url_groups": collapsed_groups,
        "discarded_duplicate_source_url_records": discarded_records,
    }
    return payload, meta


def _is_timeout_failure(exc: Exception) -> bool:
    message = str(exc)
    lowered = message.lower()
    return "57014" in message or "statement timeout" in lowered or "canceling statement due to statement timeout" in lowered


def _merge_upload_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not results:
        return {}

    merged: Dict[str, Any] = {}
    numeric_keys = {
        key
        for result in results
        for key, value in result.items()
        if key != "_upload_meta" and isinstance(value, (int, float))
    }

    for key in numeric_keys:
        merged[key] = sum(
            result.get(key, 0)
            for result in results
            if isinstance(result.get(key, 0), (int, float))
        )

    for result in results:
        for key, value in result.items():
            if key == "_upload_meta":
                continue
            if key in numeric_keys:
                continue
            if key not in merged:
                merged[key] = value
            elif isinstance(merged[key], list) and isinstance(value, list):
                merged[key].extend(item for item in value if item not in merged[key])

    return merged


class SupabaseUploader:
    """Push normalized scraper output into Supabase through an RPC function."""

    def __init__(
        self,
        settings: SupabaseSettings,
        *,
        batch_size: int = 5,
        client_factory: Callable[..., httpx.Client] = httpx.Client,
    ) -> None:
        self.settings = settings
        self.batch_size = max(1, int(batch_size))
        self.client_factory = client_factory

    def _headers(self) -> Dict[str, str]:
        return {
            "apikey": self.settings.anon_key,
            "Authorization": "Bearer %s" % self.settings.bearer_token,
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def _post_batch(
        self,
        client: httpx.Client,
        batch: List[Dict[str, Any]],
        run_summary: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload = {
            "records": batch,
            "run_summary": run_summary or {},
        }
        url = "%s/rest/v1/rpc/%s" % (self.settings.url, self.settings.rpc_name)
        response = client.post(url, headers=self._headers(), json=payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = response.text.strip()
            detail = body or "<empty response body>"
            raise RuntimeError(
                "Supabase RPC %s failed with HTTP %s. Response body: %s"
                % (self.settings.rpc_name, response.status_code, detail)
            ) from exc
        if response.text.strip():
            return response.json()
        return {"status_code": response.status_code}

    def _upload_prepared_batches(
        self,
        client: httpx.Client,
        prepared_records: List[Dict[str, Any]],
        run_summary: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if not prepared_records:
            return []
        if len(prepared_records) <= self.batch_size:
            try:
                return [self._post_batch(client, prepared_records, run_summary)]
            except RuntimeError as exc:
                if len(prepared_records) > 1 and _is_timeout_failure(exc):
                    midpoint = max(1, len(prepared_records) // 2)
                    left = self._upload_prepared_batches(client, prepared_records[:midpoint], run_summary)
                    right = self._upload_prepared_batches(client, prepared_records[midpoint:], run_summary)
                    return left + right
                raise

        results: List[Dict[str, Any]] = []
        for start in range(0, len(prepared_records), self.batch_size):
            batch = prepared_records[start : start + self.batch_size]
            try:
                results.append(self._post_batch(client, batch, run_summary))
            except RuntimeError as exc:
                if len(batch) > 1 and _is_timeout_failure(exc):
                    results.extend(self._upload_prepared_batches(client, batch, run_summary))
                    continue
                raise
        return results

    def upload(self, records: Any, run_summary: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        prepared_records, upload_meta = _sanitize_records_for_upload(records)
        run_summary_payload = run_summary or {}
        with self.client_factory(timeout=60, follow_redirects=True) as client:
            batch_results = self._upload_prepared_batches(client, prepared_records, run_summary_payload)

        result = _merge_upload_results(batch_results)
        result["_upload_meta"] = {
            **upload_meta,
            "batch_size": self.batch_size,
            "batch_count": len(batch_results),
        }
        result["batch_results"] = batch_results
        if not result:
            result = {"status_code": 200, "_upload_meta": upload_meta, "batch_results": batch_results}
        return result

    def upload_from_files(self, normalized_json_path: Path, run_summary_path: Optional[Path] = None) -> Dict[str, Any]:
        records = json.loads(normalized_json_path.read_text(encoding="utf-8"))
        run_summary = None
        if run_summary_path and run_summary_path.exists():
            run_summary = json.loads(run_summary_path.read_text(encoding="utf-8"))
        return self.upload(records=records, run_summary=run_summary)
