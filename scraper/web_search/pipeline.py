"""Pipeline orchestration for OpenAI Web Search scraper mode."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from scraper.pipeline import build_run_id
from scraper.schemas import CrawlState, FundingProgrammeRecord, FundingType, RunSummary
from scraper.storage.csv_store import CSVStore
from scraper.storage.interfaces import StorageBackend
from scraper.storage.json_store import LocalJsonStore
from scraper.utils.logging import configure_logging, get_logger
from scraper.utils.text import unique_preserve_order
from scraper.web_search.client import OpenAIWebSearchExtractor
from scraper.web_search.mapper import draft_to_record
from scraper.web_search.models import FunderWebSearchResult, WebSearchFunder, WebSearchSource
from scraper.web_search.queries import generate_funder_queries


class WebSearchPipeline:
    """Discover and extract funding programmes through OpenAI Web Search."""

    def __init__(
        self,
        settings,
        *,
        storage: Optional[StorageBackend] = None,
        csv_store: Optional[CSVStore] = None,
        extractor: Optional[OpenAIWebSearchExtractor] = None,
    ) -> None:
        self.settings = settings
        configure_logging(self.settings.output_path / "logs")
        self.logger = get_logger(__name__)
        self.storage = storage or LocalJsonStore(self.settings.output_path)
        self.csv_store = csv_store or CSVStore()
        self.extractor = extractor or OpenAIWebSearchExtractor(model=self.settings.web_search_model)

    def run_funders(self, funders: Sequence[WebSearchFunder], max_funders: Optional[int] = None) -> RunSummary:
        run_seed_urls = [funder.website_url for funder in funders]
        run_id = build_run_id(run_seed_urls)
        self.storage.initialize_run(run_id)
        started_at = datetime.now(timezone.utc)
        crawl_state = self.storage.load_crawl_state()
        completed_funders = set(crawl_state.completed_domains)
        failed_funders = set(crawl_state.failed_domains)

        pending: List[Tuple[int, WebSearchFunder]] = []
        for index, funder in enumerate(funders, start=1):
            target_key = funder.site_key or funder.domain or funder.funder_name
            if target_key in completed_funders:
                continue
            if max_funders is not None and len(pending) >= max_funders:
                break
            pending.append((index, funder))

        can_parallelize = self.settings.web_search_concurrency > 1 and len(pending) > 1
        if can_parallelize:
            with ThreadPoolExecutor(max_workers=self.settings.web_search_concurrency) as executor:
                future_map = {executor.submit(self._process_funder, funder): index for index, funder in pending}
                ordered_results = [(future_map[future], future.result()) for future in as_completed(future_map)]
            ordered_results.sort(key=lambda item: item[0])
        else:
            ordered_results = [(index, self._process_funder(funder)) for index, funder in pending]

        existing_records = self.storage.load_normalized_records()
        existing_review_records = self.storage.load_borderline_review_records()
        accepted_by_key = {_dedupe_key(record): record for record in existing_records}
        review_by_key = {_dedupe_key(record): record for record in existing_review_records}

        errors: List[str] = []
        warnings: List[str] = []
        telemetry: List[Dict[str, object]] = []
        extracted_count = 0
        skipped_low_confidence = 0

        for _index, result in ordered_results:
            funder_key = result.funder.site_key or result.funder.domain or result.funder.funder_name
            errors.extend(result.errors)
            warnings.extend(result.warnings)
            skipped_low_confidence += result.skipped_low_confidence
            extracted_count += len(result.records) + len(result.review_records)

            if result.completed:
                completed_funders.add(funder_key)
                failed_funders.discard(funder_key)
            else:
                failed_funders.add(funder_key)

            for record in result.records:
                _merge_best_record(accepted_by_key, record)
            for record in result.review_records:
                _merge_best_record(review_by_key, record)

            telemetry.append(
                {
                    "site_key": result.funder.site_key,
                    "display_name": result.funder.funder_name,
                    "domain": result.funder.domain,
                    "adapter": "web_search",
                    "seed_urls": [result.funder.website_url],
                    "pages_fetched_successfully": result.candidate_sources_found,
                    "pages_failed": 0 if result.completed else 1,
                    "candidate_programme_pages": result.candidate_sources_found,
                    "records_extracted": len(result.records) + len(result.review_records),
                    "records_accepted": len(result.records),
                    "records_reviewed": len(result.review_records),
                    "records_rejected": result.skipped_low_confidence,
                    "browser_fallback_count": 0,
                    "queries_run": result.queries_run,
                    "source_urls": unique_preserve_order([record.source_url for record in [*result.records, *result.review_records]]),
                    "warnings": result.warnings,
                    "errors": result.errors,
                    "completed": result.completed,
                }
            )
            self.storage.write_crawl_state(
                CrawlState(
                    run_id=run_id,
                    completed_domains=sorted(completed_funders),
                    failed_domains=sorted(failed_funders),
                    last_processed_domain=result.funder.domain,
                )
            )

        accepted_records = list(accepted_by_key.values())
        review_records = list(review_by_key.values())
        self.storage.save_programmes(accepted_records)
        self.csv_store.write(accepted_records, self.storage.csv_path)  # type: ignore[attr-defined]
        self.storage.write_borderline_review(review_records)
        if hasattr(self.storage, "write_qa_coverage_report"):
            self.storage.write_qa_coverage_report(telemetry)

        status = "success"
        if errors and not accepted_records and not review_records:
            status = "failed"
        elif errors:
            status = "partial"

        summary = RunSummary(
            run_id=run_id,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            status=status,
            seed_urls=run_seed_urls,
            total_urls_crawled=sum(int(item.get("queries_run", 0)) for item in telemetry),
            pages_fetched_successfully=sum(int(item.get("pages_fetched_successfully", 0)) for item in telemetry),
            pages_failed=sum(int(item.get("pages_failed", 0)) for item in telemetry),
            programmes_extracted=extracted_count,
            programmes_after_dedupe=len(accepted_records),
            records_with_missing_program_name=sum(1 for record in accepted_records if not record.program_name),
            records_with_missing_funder_name=sum(1 for record in accepted_records if not record.funder_name),
            records_with_unknown_funding_type=sum(1 for record in accepted_records if record.funding_type == FundingType.UNKNOWN),
            records_with_no_application_route=0,
            records_with_low_confidence_extraction=len(review_records),
            records_with_borderline_review=len(review_records),
            records_rejected_for_quality=skipped_low_confidence,
            browser_fallback_count=0,
            retry_count=0,
            domain_telemetry=telemetry,
            low_confidence_threshold=self.settings.web_search_min_insert_confidence / 100,
            errors=errors,
            warnings=warnings,
        )
        self.storage.write_run_summary(summary)
        self.logger.info("web_search_pipeline_completed", message="[WEB_SEARCH] Pipeline completed", run_id=run_id, status=status)
        return summary

    def _process_funder(self, funder: WebSearchFunder) -> FunderWebSearchResult:
        self.logger.info("web_search_funder_started", message="[WEB_SEARCH] Starting funder: %s" % funder.funder_name)
        self.logger.info("web_search_domain", message="[WEB_SEARCH] Domain: %s" % funder.domain)
        queries = generate_funder_queries(
            funder,
            self.settings.web_search_max_queries_per_funder,
            programme_hints=funder.raw.get("programme_hints", []),
        )
        records: List[FundingProgrammeRecord] = []
        review_records: List[FundingProgrammeRecord] = []
        skipped_low_confidence = 0
        sources_by_url: Dict[str, WebSearchSource] = {}
        errors: List[str] = []
        warnings: List[str] = []
        queries_run = 0

        try:
            for query in queries:
                records_before_query = len(records)
                review_records_before_query = len(review_records)
                self.logger.info("web_search_query", message="[WEB_SEARCH] Query: %s" % query)
                queries_run += 1
                extraction, sources = self.extractor.extract(funder, query)
                for source in sources:
                    sources_by_url.setdefault(source.url, source)
                self.logger.info(
                    "web_search_candidate_sources",
                    message="[WEB_SEARCH] Candidate sources found: %s" % len(sources_by_url),
                )
                if extraction.status == "no_programmes_found" and extraction.notes:
                    warnings.append("%s: %s" % (funder.funder_name, extraction.notes))
                for draft in extraction.programmes:
                    source_matches = _sources_for_draft(draft_source_url=draft.source_url, all_sources=sources_by_url.values())
                    record = draft_to_record(draft, funder=funder, secondary_sources=source_matches)
                    if not record:
                        skipped_low_confidence += 1
                        warnings.append("Skipped programme without required source/name for %s" % funder.funder_name)
                        continue
                    if draft.confidence_score < self.settings.web_search_min_insert_confidence:
                        skipped_low_confidence += 1
                        self.logger.info(
                            "web_search_low_confidence_skipped",
                            message="[WEB_SEARCH] Skipped low-confidence programme: %s" % (draft.program_name or "Unknown"),
                        )
                        continue
                    if draft.is_sub_programme:
                        self.logger.info(
                            "web_search_sub_programme_extracted",
                            message="[WEB_SEARCH] Extracted sub-programme: %s" % record.program_name,
                        )
                    else:
                        self.logger.info(
                            "web_search_programme_extracted",
                            message="[WEB_SEARCH] Extracted programme: %s" % record.program_name,
                        )
                    self.logger.info("web_search_confidence", message="[WEB_SEARCH] Confidence: %s" % draft.confidence_score)
                    if draft.confidence_score < 70:
                        review_records.append(record)
                    else:
                        records.append(record)
                        self.logger.info("web_search_inserted", message="[WEB_SEARCH] Inserted: %s" % record.program_name)
                if (
                    self.settings.web_search_stop_after_success
                    and (len(records) > records_before_query or len(review_records) > review_records_before_query)
                ):
                    self.logger.info(
                        "web_search_stopped_after_success",
                        message="[WEB_SEARCH] Stopping further queries for %s after usable records were found." % funder.funder_name,
                    )
                    break
        except Exception as exc:
            errors.append("Web Search failed for %s: %s" % (funder.funder_name, exc))
            self.logger.exception("web_search_funder_failed", message="[WEB_SEARCH] Failed funder: %s" % funder.funder_name)
            return FunderWebSearchResult(
                funder=funder,
                records=list(_dedupe_records(records)),
                review_records=list(_dedupe_records(review_records)),
                skipped_low_confidence=skipped_low_confidence,
                candidate_sources_found=len(sources_by_url),
                queries_run=queries_run,
                errors=errors,
                warnings=warnings,
                completed=False,
            )

        self.logger.info("web_search_funder_completed", message="[WEB_SEARCH] Completed funder: %s" % funder.funder_name)
        return FunderWebSearchResult(
            funder=funder,
            records=list(_dedupe_records(records)),
            review_records=list(_dedupe_records(review_records)),
            skipped_low_confidence=skipped_low_confidence,
            candidate_sources_found=len(sources_by_url),
            queries_run=queries_run,
            errors=errors,
            warnings=warnings,
            completed=True,
        )


def _sources_for_draft(draft_source_url: Optional[str], all_sources: Iterable[WebSearchSource]) -> List[WebSearchSource]:
    source_url = draft_source_url or ""
    ordered = sorted(
        all_sources,
        key=lambda source: (
            0 if source.url == source_url else 1,
            source.official_rank,
            source.url,
        ),
    )
    return ordered[:8]


def _dedupe_key(record: FundingProgrammeRecord) -> tuple[str, str, str, str]:
    return (
        (record.funder_name or "").casefold(),
        (record.program_name or "").casefold(),
        (record.parent_programme_name or "").casefold(),
        record.source_url,
    )


def _record_confidence(record: FundingProgrammeRecord) -> float:
    return max(record.extraction_confidence.values(), default=0.0)


def _merge_best_record(records_by_key: Dict[tuple[str, str, str, str], FundingProgrammeRecord], record: FundingProgrammeRecord) -> None:
    key = _dedupe_key(record)
    existing = records_by_key.get(key)
    if existing is None or _record_confidence(record) > _record_confidence(existing):
        records_by_key[key] = record


def _dedupe_records(records: Sequence[FundingProgrammeRecord]) -> Iterable[FundingProgrammeRecord]:
    by_key: Dict[tuple[str, str, str, str], FundingProgrammeRecord] = {}
    for record in records:
        _merge_best_record(by_key, record)
    return by_key.values()
