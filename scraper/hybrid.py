"""Crawler-first hybrid scraper orchestration."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Callable, Dict, Iterable, List, Optional, Sequence

from rapidfuzz import fuzz

from scraper.adapters.registry import SiteAdapterRegistry, build_default_registry
from scraper.pipeline import ScraperPipeline
from scraper.schemas import ApplicationChannel, FundingProgrammeRecord, FundingType, RunSummary
from scraper.storage.csv_store import CSVStore
from scraper.storage.interfaces import StorageBackend
from scraper.storage.json_store import LocalJsonStore
from scraper.storage.site_repository import SiteDefinition
from scraper.utils.logging import configure_logging, get_logger
from scraper.utils.text import clean_text, unique_preserve_order
from scraper.utils.urls import extract_host, hosts_match
from scraper.web_search import WebSearchFunder, WebSearchPipeline
from scraper.web_search.models import FunderWebSearchResult


FallbackReason = str


@dataclass(frozen=True)
class HybridRecordQuality:
    """Quality signals used to decide hybrid fallback and merge precedence."""

    confidence: float
    completeness: float
    official_source_score: int
    reasons: tuple[FallbackReason, ...]


@dataclass(frozen=True)
class HybridDecision:
    """One funder's hybrid fallback decision."""

    funder: WebSearchFunder
    crawler_records: tuple[FundingProgrammeRecord, ...]
    should_use_web_search: bool
    reasons: tuple[FallbackReason, ...]
    web_search_status: str = "not_needed"
    web_search_calls_used: int = 0


class HybridScraperPipeline:
    """Run crawler extraction first, then targeted Web Search fallback."""

    def __init__(
        self,
        settings,
        *,
        storage: Optional[StorageBackend] = None,
        csv_store: Optional[CSVStore] = None,
        adapter_registry: Optional[SiteAdapterRegistry] = None,
        crawler_runner: Optional[Callable[[Sequence[SiteDefinition], Optional[int]], RunSummary]] = None,
        web_search_pipeline: Optional[WebSearchPipeline] = None,
    ) -> None:
        self.settings = settings
        configure_logging(self.settings.output_path / "logs")
        self.logger = get_logger(__name__)
        self.storage = storage or LocalJsonStore(self.settings.output_path)
        self.csv_store = csv_store or CSVStore()
        self.adapter_registry = adapter_registry or build_default_registry()
        self.crawler_runner = crawler_runner
        self.web_search_pipeline = web_search_pipeline

    def run_sites(self, sites: Sequence[SiteDefinition], max_sites: Optional[int] = None) -> RunSummary:
        selected_sites = list(sites[:max_sites] if max_sites is not None else sites)
        crawler_summary = self._run_crawler(selected_sites, max_sites=max_sites)
        crawler_records = self.storage.load_normalized_records()
        crawler_review_records = self.storage.load_borderline_review_records()
        records_by_funder = self._records_by_funder(crawler_records, selected_sites)
        decisions: List[HybridDecision] = []
        web_results: List[FunderWebSearchResult] = []

        for site in selected_sites:
            funder = WebSearchFunder.from_site(site)
            decision = self._decide_fallback(funder, records_by_funder.get(site.site_key, []), crawler_summary)
            decisions.append(decision)
            if not decision.should_use_web_search:
                self.logger.info(
                    "hybrid_fallback_skipped",
                    message="Hybrid fallback skipped for %s reason=strong_crawler_results" % funder.funder_name,
                    funder=funder.funder_name,
                    reason="strong_crawler_results",
                )
                continue
            if self.settings.hybrid_web_search_max_calls_per_funder <= 0:
                continue
            self.logger.info(
                "hybrid_fallback_triggered",
                message="Hybrid fallback triggered for %s reason=%s crawler_records=%s web_search_calls_used=0"
                % (funder.funder_name, ",".join(decision.reasons), len(decision.crawler_records)),
                funder=funder.funder_name,
                reason=list(decision.reasons),
                crawler_records=len(decision.crawler_records),
            )
            result = self._get_web_search_pipeline()._process_funder(funder)
            web_results.append(result)
            if _is_quota_result(result):
                self.logger.warning(
                    "hybrid_web_search_quota_skipped",
                    message="Hybrid Web Search skipped for %s reason=insufficient_quota preserving_crawler_records=true"
                    % funder.funder_name,
                    funder=funder.funder_name,
                    preserving_crawler_records=True,
                )

        merged_records = merge_hybrid_records(crawler_records, web_results, selected_sites)
        merged_records = [
            record
            for record in merged_records
            if _valid_for_persistence(record, min_confidence=self.settings.hybrid_min_confidence)
        ]
        self.storage.save_programmes(merged_records)
        self.csv_store.write(merged_records, self.storage.csv_path)  # type: ignore[attr-defined]
        self.storage.write_borderline_review(crawler_review_records)

        telemetry = _hybrid_telemetry(crawler_summary, decisions, web_results)
        if hasattr(self.storage, "write_qa_coverage_report"):
            self.storage.write_qa_coverage_report(telemetry)

        errors = [*crawler_summary.errors]
        warnings = [*crawler_summary.warnings]
        for result in web_results:
            errors.extend(result.errors)
            warnings.extend(result.warnings)
        status = "success"
        if errors and not merged_records:
            status = "failed"
        elif errors:
            status = "partial"

        summary = crawler_summary.model_copy(
            update={
                "completed_at": datetime.now(timezone.utc),
                "status": status,
                "programmes_after_dedupe": len(merged_records),
                "records_with_missing_program_name": sum(1 for record in merged_records if not record.program_name),
                "records_with_missing_funder_name": sum(1 for record in merged_records if not record.funder_name),
                "records_with_unknown_funding_type": sum(1 for record in merged_records if record.funding_type == FundingType.UNKNOWN),
                "records_with_no_application_route": sum(
                    1 for record in merged_records if record.application_channel == ApplicationChannel.UNKNOWN
                ),
                "records_with_low_confidence_extraction": sum(
                    1 for record in merged_records if record.overall_confidence() < self.settings.hybrid_min_confidence
                ),
                "domain_telemetry": telemetry,
                "errors": errors,
                "warnings": warnings,
            }
        )
        self.storage.write_run_summary(summary)
        self.logger.info("hybrid_pipeline_completed", run_id=summary.run_id, status=summary.status)
        return summary

    def _get_web_search_pipeline(self) -> WebSearchPipeline:
        if self.web_search_pipeline is None:
            self.web_search_pipeline = WebSearchPipeline(
                replace(
                    self.settings,
                    web_search_max_queries_per_funder=max(1, self.settings.hybrid_web_search_max_calls_per_funder),
                    web_search_stop_after_success=True,
                    web_search_concurrency=1,
                ),
                storage=self.storage,
                csv_store=self.csv_store,
            )
        return self.web_search_pipeline

    def _run_crawler(self, sites: Sequence[SiteDefinition], max_sites: Optional[int]) -> RunSummary:
        if self.crawler_runner:
            return self.crawler_runner(sites, max_sites)
        pipeline = ScraperPipeline(self.settings, storage=self.storage, csv_store=self.csv_store, adapter_registry=self.adapter_registry)
        return pipeline.run_sites(sites, max_sites=max_sites)

    @staticmethod
    def _records_by_funder(
        records: Sequence[FundingProgrammeRecord],
        sites: Sequence[SiteDefinition],
    ) -> Dict[str, List[FundingProgrammeRecord]]:
        grouped: Dict[str, List[FundingProgrammeRecord]] = {site.site_key: [] for site in sites}
        for record in records:
            for site in sites:
                funder_name = (record.funder_name or "").casefold()
                if record.source_domain and hosts_match(record.source_domain, site.primary_domain):
                    grouped.setdefault(site.site_key, []).append(record)
                    break
                if funder_name and funder_name == (site.display_name or site.site_key).casefold():
                    grouped.setdefault(site.site_key, []).append(record)
                    break
        return grouped

    def _decide_fallback(
        self,
        funder: WebSearchFunder,
        crawler_records: Sequence[FundingProgrammeRecord],
        crawler_summary: RunSummary,
    ) -> HybridDecision:
        reasons: List[FallbackReason] = []
        if any(not item.get("completed", True) for item in crawler_summary.domain_telemetry if item.get("site_key") == funder.site_key):
            reasons.append("crawl_failed")
        if len(crawler_records) < self.settings.hybrid_min_accepted_records:
            reasons.append("zero_accepted_records")
        for record in crawler_records:
            quality = score_hybrid_record(record, funder_domain=funder.domain)
            reasons.extend(quality.reasons)
        reasons = unique_preserve_order(reasons)
        should_use = bool(reasons) and (
            self.settings.hybrid_enrich_low_confidence or any(reason != "low_confidence" for reason in reasons)
        )
        return HybridDecision(
            funder=funder,
            crawler_records=tuple(crawler_records),
            should_use_web_search=should_use,
            reasons=tuple(reasons),
            web_search_status="not_needed" if not should_use else "failed",
        )


def score_hybrid_record(record: FundingProgrammeRecord, *, funder_domain: str) -> HybridRecordQuality:
    official = 1 if _is_official_record(record, funder_domain) else 0
    factors = {
        "program_name": bool(record.program_name),
        "funder_name": bool(record.funder_name),
        "source_url": bool(record.source_url),
        "official_source": bool(official),
        "eligibility": bool(record.raw_eligibility_criteria or record.raw_eligibility_data),
        "funding_type": record.funding_type != FundingType.UNKNOWN,
        "funding_amount": record.ticket_min is not None or record.ticket_max is not None,
        "content": bool(record.raw_funding_offer_data or record.raw_terms_data or record.raw_text_snippets),
        "structured": bool(record.evidence_by_field or record.field_evidence),
    }
    confidence = max(record.overall_confidence(), sum(1 for value in factors.values() if value) / len(factors))
    required_fields = (
        record.program_name,
        record.funder_name,
        record.source_url,
        record.raw_eligibility_criteria or record.raw_eligibility_data,
        record.funding_type if record.funding_type != FundingType.UNKNOWN else None,
        record.ticket_min if record.ticket_min is not None else record.ticket_max,
    )
    completeness = sum(1 for value in required_fields if value) / len(required_fields)
    reasons: List[FallbackReason] = []
    if not record.source_url:
        reasons.append("missing_source_url")
    if record.ticket_min is None and record.ticket_max is None:
        reasons.append("missing_funding_amount")
    if not record.raw_eligibility_criteria and not record.raw_eligibility_data:
        reasons.append("missing_eligibility")
    if not record.raw_funding_offer_data and not record.raw_terms_data and not record.raw_text_snippets:
        reasons.append("missing_programme_details")
    if confidence < 0.70:
        reasons.append("low_confidence")
    return HybridRecordQuality(
        confidence=round(confidence, 4),
        completeness=round(completeness, 4),
        official_source_score=official,
        reasons=tuple(reasons),
    )


def merge_hybrid_records(
    crawler_records: Sequence[FundingProgrammeRecord],
    web_results: Sequence[FunderWebSearchResult],
    sites: Sequence[SiteDefinition],
) -> List[FundingProgrammeRecord]:
    merged: List[FundingProgrammeRecord] = [record.model_copy(deep=True) for record in crawler_records]
    for result in web_results:
        for web_record in [*result.records, *result.review_records]:
            match = _find_duplicate_record(merged, web_record)
            if match is None:
                merged.append(_with_hybrid_metadata(web_record, method="web_search", reason=_reason_for_result(result), status=_status_for_result(result)))
                continue
            index = merged.index(match)
            site = _site_for_record(match, sites)
            merged[index] = merge_hybrid_record(
                match,
                web_record,
                funder_domain=site.primary_domain if site else result.funder.domain,
                fallback_reason=_reason_for_result(result),
                web_search_status=_status_for_result(result),
            )
    return merged


def merge_hybrid_record(
    crawler_record: FundingProgrammeRecord,
    web_record: FundingProgrammeRecord,
    *,
    funder_domain: str,
    fallback_reason: str,
    web_search_status: str,
) -> FundingProgrammeRecord:
    merged = crawler_record.model_copy(deep=True)
    crawler_quality = score_hybrid_record(crawler_record, funder_domain=funder_domain)
    web_quality = score_hybrid_record(web_record, funder_domain=funder_domain)
    web_is_official = web_quality.official_source_score > 0
    crawler_is_official = crawler_quality.official_source_score > 0

    for field_name in _SCALAR_MERGE_FIELDS:
        current = getattr(merged, field_name)
        candidate = getattr(web_record, field_name)
        if _missing(current) and not _missing(candidate):
            setattr(merged, field_name, candidate)
        elif field_name == "source_url" and web_is_official and not crawler_is_official and not _missing(candidate):
            setattr(merged, field_name, candidate)
    for field_name in _LIST_MERGE_FIELDS:
        setattr(merged, field_name, unique_preserve_order([*getattr(merged, field_name), *getattr(web_record, field_name)]))
    merged.raw_text_snippets = _merge_dict_lists(merged.raw_text_snippets, web_record.raw_text_snippets)
    merged.evidence_by_field = _merge_dict_lists(merged.evidence_by_field, web_record.evidence_by_field)
    merged.extraction_confidence = {
        **merged.extraction_confidence,
        **{
            key: max(value, merged.extraction_confidence.get(key, 0.0))
            for key, value in web_record.extraction_confidence.items()
        },
    }
    return _with_hybrid_metadata(merged, method="playwright+web_search", reason=fallback_reason, status=web_search_status)


_SCALAR_MERGE_FIELDS = (
    "source_url",
    "source_page_title",
    "ticket_min",
    "ticket_max",
    "currency",
    "program_budget_total",
    "payback_raw_text",
    "payback_structure",
    "application_url",
    "contact_email",
    "contact_phone",
)
_LIST_MERGE_FIELDS = (
    "source_urls",
    "raw_eligibility_criteria",
    "raw_funding_offer_data",
    "raw_terms_data",
    "raw_documents_data",
    "raw_application_data",
    "funding_lines",
    "industries",
    "use_of_funds",
    "business_stage_eligibility",
    "required_documents",
    "related_documents",
)


def normalized_programme_key(value: str, funder_name: str = "") -> str:
    text = re.sub(r"[^a-z0-9\s]+", " ", (value or "").casefold())
    text = re.sub(r"\b(programme|program|funding|fund)\b", " ", text)
    for token in re.split(r"[^a-z0-9]+", (funder_name or "").casefold()):
        if token:
            text = re.sub(r"\b%s\b" % re.escape(token), " ", text)
    return " ".join(text.split())


def _find_duplicate_record(
    records: Sequence[FundingProgrammeRecord],
    candidate: FundingProgrammeRecord,
) -> Optional[FundingProgrammeRecord]:
    candidate_name = normalized_programme_key(candidate.program_name or "", candidate.funder_name or "")
    candidate_parent = normalized_programme_key(candidate.parent_programme_name or "", candidate.funder_name or "")
    for record in records:
        if (record.funder_name or "").casefold() != (candidate.funder_name or "").casefold():
            continue
        parent_name = normalized_programme_key(record.parent_programme_name or "", record.funder_name or "")
        if parent_name != candidate_parent:
            continue
        record_name = normalized_programme_key(record.program_name or "", record.funder_name or "")
        if record.source_url == candidate.source_url:
            return record
        if record_name and candidate_name and fuzz.token_sort_ratio(record_name, candidate_name) >= 88:
            return record
    return None


def _valid_for_persistence(record: FundingProgrammeRecord, *, min_confidence: float) -> bool:
    if not record.program_name or not record.funder_name or not record.source_url:
        return False
    if record.overall_confidence() and record.overall_confidence() < min_confidence:
        record.needs_review = True
        record.needs_review_reasons = unique_preserve_order([*record.needs_review_reasons, "hybrid_confidence_below_threshold"])
    return True


def _with_hybrid_metadata(
    record: FundingProgrammeRecord,
    *,
    method: str,
    reason: str,
    status: str,
) -> FundingProgrammeRecord:
    payload = record.model_dump(mode="python")
    snippets = dict(payload.get("raw_text_snippets") or {})
    extraction_sources = _unique_values(
        [
            *snippets.get("extraction_sources", []),
            json.dumps(
                {
                "method": method,
                "source_url": record.source_url,
                "confidence": record.overall_confidence(),
                "official_domain": _is_official_record(record, record.source_domain),
                },
                sort_keys=True,
            ),
        ]
    )
    snippets["extraction_sources"] = extraction_sources
    snippets["hybrid_fallback_reason"] = [reason] if reason else []
    snippets["web_search_status"] = [status]
    payload["raw_text_snippets"] = snippets
    payload["evidence_by_field"] = _merge_dict_lists(
        payload.get("evidence_by_field") or {},
        {
            "hybrid_fallback_reason": [reason] if reason else [],
            "web_search_status": [status],
        },
    )
    payload["notes"] = unique_preserve_order([*payload.get("notes", []), "hybrid_fallback_reason=%s" % reason, "web_search_status=%s" % status])
    return FundingProgrammeRecord.model_validate(payload)


def _merge_dict_lists(left: Dict[str, object], right: Dict[str, object]) -> Dict[str, List[object]]:
    merged: Dict[str, List[object]] = {}
    for source in (left or {}, right or {}):
        for key, value in source.items():
            values = value if isinstance(value, list) else [value]
            merged[key] = _unique_values([*merged.get(key, []), *values])
    return {key: value for key, value in merged.items() if value}


def _unique_values(values: Iterable[object]) -> List[object]:
    seen: set[str] = set()
    result: List[object] = []
    for value in values:
        key = json.dumps(value, sort_keys=True, default=str) if isinstance(value, (dict, list)) else str(value).casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _missing(value: object) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _is_official_record(record: FundingProgrammeRecord, funder_domain: str) -> bool:
    if not record.source_url or not funder_domain:
        return False
    return hosts_match(extract_host(record.source_url), funder_domain)


def _site_for_record(record: FundingProgrammeRecord, sites: Sequence[SiteDefinition]) -> Optional[SiteDefinition]:
    for site in sites:
        if record.source_domain and hosts_match(record.source_domain, site.primary_domain):
            return site
        if (record.funder_name or "").casefold() == (site.display_name or site.site_key).casefold():
            return site
    return None


def _reason_for_result(result: FunderWebSearchResult) -> str:
    if result.errors:
        return "web_search_failed"
    if result.records or result.review_records:
        return "web_search_enrichment"
    return "web_search_no_results"


def _status_for_result(result: FunderWebSearchResult) -> str:
    if _is_quota_result(result):
        return "skipped_quota"
    if result.records or result.review_records:
        return "used_successfully"
    if result.completed:
        return "used_no_results"
    return "failed"


def _is_quota_result(result: FunderWebSearchResult) -> bool:
    return any("insufficient_quota" in error or "429" in error for error in result.errors)


def _hybrid_telemetry(
    crawler_summary: RunSummary,
    decisions: Sequence[HybridDecision],
    web_results: Sequence[FunderWebSearchResult],
) -> List[Dict[str, object]]:
    by_site = {item.get("site_key"): dict(item) for item in crawler_summary.domain_telemetry}
    result_by_key = {result.funder.site_key: result for result in web_results}
    for decision in decisions:
        row = by_site.setdefault(
            decision.funder.site_key,
            {
                "site_key": decision.funder.site_key,
                "display_name": decision.funder.funder_name,
                "domain": decision.funder.domain,
            },
        )
        result = result_by_key.get(decision.funder.site_key)
        row["hybrid_fallback_reason"] = list(decision.reasons)
        row["web_search_status"] = _status_for_result(result) if result else "not_needed"
        row["web_search_calls_used"] = result.queries_run if result else 0
    return list(by_site.values())
