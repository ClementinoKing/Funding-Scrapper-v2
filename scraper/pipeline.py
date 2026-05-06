"""High-level pipeline orchestration."""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence

from scraper.ai.ai_enhancement import AIClassifier
from scraper.adapters.registry import SiteAdapterRegistry, build_default_registry
from scraper.crawler import Crawler
from scraper.fetchers.browser_fetcher import BrowserFetcher
from scraper.fetchers.http_fetcher import HttpFetcher
from scraper.parsers.generic_parser import GenericFundingParser
from scraper.schemas import ApplicationChannel, CrawlState, FundingProgrammeRecord, FundingType, PageContentDocument, RunSummary
from scraper.storage.csv_store import CSVStore
from scraper.storage.interfaces import StorageBackend
from scraper.storage.json_store import LocalJsonStore
from scraper.storage.site_repository import SiteDefinition
from scraper.utils.dedupe import dedupe_records_with_trace
from scraper.utils.logging import configure_logging, get_logger
from scraper.utils.quality import is_borderline_programme_record, is_real_programme_record, score_programme_quality
from scraper.utils.page_classification import mark_review_reasons, should_persist_record
from scraper.utils.validators import add_application_verification_note, is_low_confidence
from scraper.utils.urls import canonicalize_url, extract_host
from scraper.utils.text import unique_preserve_order

if TYPE_CHECKING:
    from scraper.ai.ai_enhancement import AIClassifier as AIClassifierType


def build_run_id(seed_urls: Sequence[str]) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    digest = hashlib.blake2b("|".join(seed_urls).encode("utf-8"), digest_size=4).hexdigest()
    return "run_%s_%s" % (timestamp, digest)


@dataclass(frozen=True)
class CrawlTarget:
    """One crawl unit, either from a direct URL or a DB site row."""

    key: str
    label: str
    primary_domain: str
    adapter_key: str
    adapter_config: Dict[str, Any]
    seed_urls: tuple[str, ...]
    ai_enrichment_required: bool = False


@dataclass
class DomainRunResult:
    target: CrawlTarget
    adapter_key: str
    documents: List[PageContentDocument]
    classified_records: List[FundingProgrammeRecord]
    accepted_records: List[FundingProgrammeRecord]
    borderline_records: List[FundingProgrammeRecord]
    merge_trace: List[dict]
    crawl_stats: Dict[str, Any]
    errors: List[str]
    warnings: List[str]
    rejected_count: int
    completed: bool = False


class LockedStorageBackend:
    """Serialize artifact writes while domains are processed concurrently."""

    def __init__(self, storage: StorageBackend, lock: threading.Lock) -> None:
        self._storage = storage
        self._lock = lock

    def __getattr__(self, name: str):
        attr = getattr(self._storage, name)
        if not callable(attr):
            return attr

        def locked(*args, **kwargs):
            with self._lock:
                return attr(*args, **kwargs)

        return locked


class ScraperPipeline:
    """Run a crawl, classify raw content with AI, and persist normalized records."""

    def __init__(
        self,
        settings,
        storage: Optional[StorageBackend] = None,
        csv_store: Optional[CSVStore] = None,
        parser: Optional[GenericFundingParser] = None,
        http_fetcher: Optional[HttpFetcher] = None,
        browser_fetcher: Optional[BrowserFetcher] = None,
        adapter_registry: Optional[SiteAdapterRegistry] = None,
        ai_enhancer: Optional["AIClassifierType"] = None,
    ) -> None:
        self.settings = settings
        configure_logging(self.settings.output_path / "logs")
        self.logger = get_logger(__name__)
        self.storage = storage or LocalJsonStore(self.settings.output_path)
        self.csv_store = csv_store or CSVStore()
        self._custom_parser = parser is not None
        self._custom_http_fetcher = http_fetcher is not None
        self._custom_browser_fetcher = browser_fetcher is not None
        self._custom_ai_enhancer = ai_enhancer is not None
        self.parser = parser or GenericFundingParser(self.settings)
        self.http_fetcher = http_fetcher or HttpFetcher(self.settings)
        self.browser_fetcher = browser_fetcher or (BrowserFetcher(self.settings) if self.settings.browser_fallback else None)
        self.adapter_registry = adapter_registry or build_default_registry()
        self.ai_enhancer = ai_enhancer or self._build_ai_classifier()

    def close(self) -> None:
        self.http_fetcher.close()
        if self.browser_fetcher:
            self.browser_fetcher.close()

    def _build_ai_classifier(self) -> AIClassifier:
        try:
            return AIClassifier(
                {
                    "aiProvider": self.settings.ai_provider,
                    "aiModel": self.settings.ai_model,
                    "disableRemoteAi": not self.settings.ai_enrichment,
                    "requireRemoteAi": self.settings.ai_enrichment,
                    "industry_taxonomy": self.settings.industry_taxonomy,
                    "use_of_funds_taxonomy": self.settings.use_of_funds_taxonomy,
                    "ownership_target_keywords": self.settings.ownership_target_keywords,
                    "entity_type_keywords": self.settings.entity_type_keywords,
                    "certification_keywords": self.settings.certification_keywords,
                },
                storage=self.storage,
            )
        except Exception as exc:
            self.logger.warning("ai_classifier_disabled", error=str(exc))
            return AIClassifier(
                {
                    "aiProvider": self.settings.ai_provider,
                    "aiModel": self.settings.ai_model,
                    "disableRemoteAi": True,
                    "requireRemoteAi": self.settings.ai_enrichment,
                    "industry_taxonomy": self.settings.industry_taxonomy,
                    "use_of_funds_taxonomy": self.settings.use_of_funds_taxonomy,
                    "ownership_target_keywords": self.settings.ownership_target_keywords,
                    "entity_type_keywords": self.settings.entity_type_keywords,
                    "certification_keywords": self.settings.certification_keywords,
                },
                storage=None,
            )

    @staticmethod
    def _group_seed_urls_by_domain(seed_urls: Sequence[str]) -> List[tuple[str, str]]:
        grouped: List[tuple[str, str]] = []
        seen_hosts: set[str] = set()
        for seed_url in seed_urls:
            canonical = canonicalize_url(seed_url)
            host = extract_host(canonical)
            if not host or host in seen_hosts:
                continue
            seen_hosts.add(host)
            grouped.append((host, canonical))
        return grouped

    def _build_targets_from_seed_urls(self, seed_urls: Sequence[str]) -> List[CrawlTarget]:
        targets: List[CrawlTarget] = []
        for host, domain_seed_url in self._group_seed_urls_by_domain(seed_urls):
            targets.append(
                CrawlTarget(
                    key=host,
                    label=host,
                    primary_domain=host,
                    adapter_key=self.adapter_registry.generic_adapter.key,
                    adapter_config={},
                    seed_urls=(domain_seed_url,),
                )
            )
        return targets

    def run(self, seed_urls: Sequence[str], max_domains: Optional[int] = None) -> RunSummary:
        return self._run_targets(
            targets=self._build_targets_from_seed_urls(seed_urls),
            run_seed_urls=seed_urls,
            max_domains=max_domains,
        )

    def run_sites(self, sites: Sequence[SiteDefinition], max_sites: Optional[int] = None) -> RunSummary:
        targets: List[CrawlTarget] = []
        run_seed_urls: List[str] = []
        for site in sites:
            seed_urls = unique_preserve_order(
                [canonicalize_url(seed_url) for seed_url in site.seed_urls if canonicalize_url(seed_url)]
            )
            if not seed_urls:
                continue
            primary_domain = extract_host(site.primary_domain or (seed_urls[0] if seed_urls else ""))
            target_key = site.site_key or primary_domain or self.adapter_registry.generic_adapter.key
            targets.append(
                CrawlTarget(
                    key=target_key,
                    label=site.display_name or target_key,
                    primary_domain=primary_domain or target_key,
                    adapter_key=site.adapter_key or self.adapter_registry.generic_adapter.key,
                    adapter_config=site.adapter_config,
                    seed_urls=tuple(seed_urls),
                    ai_enrichment_required=site.ai_enrichment_required,
                )
            )
            run_seed_urls.extend(seed_urls)
        if any(target.ai_enrichment_required for target in targets) and self.ai_enhancer is None:
            self.ai_enhancer = self._build_ai_classifier()
        return self._run_targets(targets=targets, run_seed_urls=run_seed_urls, max_domains=max_sites)

    def _classify_documents(
        self,
        documents: Sequence[PageContentDocument],
        ai_enhancer: Optional["AIClassifierType"] = None,
    ) -> List[FundingProgrammeRecord]:
        records: List[FundingProgrammeRecord] = []
        classifier = ai_enhancer or self.ai_enhancer
        for document in documents:
            try:
                if hasattr(classifier, "classify_document"):
                    classified = classifier.classify_document(document)
                elif hasattr(classifier, "classify_documents"):
                    classified = classifier.classify_documents([document])
                else:
                    classified = []
                for item in classified:
                    if isinstance(item, FundingProgrammeRecord):
                        records.append(FundingProgrammeRecord.model_validate(item.model_dump(mode="python")))
                    else:
                        records.append(FundingProgrammeRecord.model_validate(item))
            except Exception as exc:
                self.logger.warning("ai_classification_failed", page_url=document.page_url, error=str(exc))
        return records

    def _process_target(
        self,
        *,
        target: CrawlTarget,
        storage: StorageBackend,
        parser: GenericFundingParser,
        http_fetcher: HttpFetcher,
        browser_fetcher: Optional[BrowserFetcher],
        ai_enhancer: "AIClassifierType",
    ) -> DomainRunResult:
        adapter = self.adapter_registry.build_for_site(
            adapter_key=target.adapter_key,
            primary_domain=target.primary_domain,
            config=target.adapter_config,
        )
        domain_seed_urls = unique_preserve_order(
            [
                *target.seed_urls,
                *adapter.default_seed_urls_for_domain(target.primary_domain),
            ]
        )
        crawler = Crawler(
            settings=self.settings,
            storage=storage,
            parser=parser,
            http_fetcher=http_fetcher,
            browser_fetcher=browser_fetcher,
        )
        errors: List[str] = []
        warnings: List[str] = []
        rejected_count = 0
        documents: List[PageContentDocument] = []
        classified_records: List[FundingProgrammeRecord] = []
        accepted_records: List[FundingProgrammeRecord] = []
        borderline_records: List[FundingProgrammeRecord] = []
        merge_trace: List[dict] = []
        crawl_stats: Dict[str, Any] = {
            "total_urls_crawled": 0,
            "pages_fetched_successfully": 0,
            "pages_failed": 0,
            "errors": [],
            "warnings": [],
        }

        try:
            documents, crawl_stats = crawler.crawl(domain_seed_urls, adapter=adapter)
            classified_records = self._classify_documents(documents, ai_enhancer=ai_enhancer)
            classified_records = [
                record.model_copy(update={"site_adapter": adapter.key})
                if record.site_adapter != adapter.key
                else record
                for record in classified_records
            ]
            if target.ai_enrichment_required:
                if any(not record.ai_enriched for record in classified_records):
                    raise RuntimeError(
                        "AI enrichment is required for %s but some records were not AI enriched." % target.label
                    )

            validated_records = [
                add_application_verification_note(
                    record,
                    timeout_seconds=self.settings.application_verification_timeout_seconds,
                )
                for record in classified_records
            ]
            validated_records = [
                FundingProgrammeRecord.model_validate(record.model_dump(mode="python"))
                for record in validated_records
            ]

            deduped_records, merge_trace = dedupe_records_with_trace(
                validated_records,
                adapter=adapter,
                merge_decider=ai_enhancer,
            )

            for record in deduped_records:
                record = mark_review_reasons(record)
                should_persist, reject_reason = should_persist_record(record)
                if not should_persist:
                    rejected_count += 1
                    if reject_reason:
                        warnings.append("%s: %s" % (record.source_url, reject_reason))
                    continue
                quality_score, quality_reasons, quality_blockers = score_programme_quality(record)
                if is_low_confidence(record, self.settings.low_confidence_threshold):
                    record.needs_review = True
                    record.validation_errors = unique_preserve_order(
                        [
                            *record.validation_errors,
                            "low overall extraction confidence (< %.2f)." % self.settings.low_confidence_threshold,
                        ]
                    )
                if is_real_programme_record(record, self.settings.programme_accept_threshold):
                    accepted_records.append(record)
                    continue
                if is_borderline_programme_record(
                    record,
                    accept_threshold=self.settings.programme_accept_threshold,
                    review_threshold=self.settings.programme_review_threshold,
                ):
                    review_record = record.model_copy(deep=True)
                    review_record.notes = unique_preserve_order(
                        [
                            *review_record.notes,
                            "Review candidate: quality score %s/100." % quality_score,
                            "Reasons: %s" % ", ".join(quality_reasons) if quality_reasons else "Reasons: not captured",
                            "Blockers: %s" % ", ".join(quality_blockers) if quality_blockers else "Blockers: none",
                        ]
                    )
                    review_record.needs_review = True
                    review_record.validation_errors = unique_preserve_order(
                        [
                            *review_record.validation_errors,
                            "borderline quality score requiring manual review",
                        ]
                    )
                    borderline_records.append(review_record)
                    continue
                rejected_count += 1

            return DomainRunResult(
                target=target,
                adapter_key=adapter.key,
                documents=list(documents),
                classified_records=list(classified_records),
                accepted_records=accepted_records,
                borderline_records=borderline_records,
                merge_trace=merge_trace,
                crawl_stats=dict(crawl_stats),
                errors=[*list(crawl_stats.get("errors", [])), *errors],
                warnings=[*list(crawl_stats.get("warnings", [])), *warnings],
                rejected_count=rejected_count,
                completed=True,
            )
        except Exception as exc:
            errors.append("Domain failed for %s: %s" % (target.label, exc))
            self.logger.exception("domain_failed", domain=target.primary_domain)
            return DomainRunResult(
                target=target,
                adapter_key=adapter.key,
                documents=list(documents),
                classified_records=list(classified_records),
                accepted_records=[],
                borderline_records=[],
                merge_trace=merge_trace,
                crawl_stats=dict(crawl_stats),
                errors=[*list(crawl_stats.get("errors", [])), *errors],
                warnings=[*list(crawl_stats.get("warnings", [])), *warnings],
                rejected_count=rejected_count,
                completed=False,
            )

    def _run_targets(
        self,
        *,
        targets: Sequence[CrawlTarget],
        run_seed_urls: Sequence[str],
        max_domains: Optional[int] = None,
    ) -> RunSummary:
        run_id = build_run_id(run_seed_urls)
        self.storage.initialize_run(run_id)
        started_at = datetime.now(timezone.utc)
        self.logger.info("pipeline_started", run_id=run_id, seeds=list(run_seed_urls))

        try:
            crawl_state = self.storage.load_crawl_state()
            completed_domains = set(crawl_state.completed_domains)
            failed_domains = set(crawl_state.failed_domains)
            persisted_records = self.storage.load_normalized_records()
            review_records = self.storage.load_borderline_review_records()
            total_domains = len(targets)

            aggregate_total_urls_crawled = 0
            aggregate_pages_fetched_successfully = 0
            aggregate_pages_failed = 0
            aggregate_programmes_extracted = 0
            aggregate_errors: List[str] = []
            aggregate_warnings: List[str] = []
            domain_merge_traces: List[dict] = []
            borderline_count = 0
            rejected_count = 0
            attempted_domains = 0
            browser_fallback_count = 0
            retry_count = 0
            queue_saturation_count = 0
            skipped_url_counts: Dict[str, int] = {}
            fetch_time_weighted_total = 0.0
            fetch_time_weight = 0
            domain_telemetry: List[Dict[str, Any]] = []
            qa_coverage_report: List[Dict[str, Any]] = []

            pending_targets: List[tuple[int, CrawlTarget]] = []
            for index, target in enumerate(targets, start=1):
                target_key = target.key or target.primary_domain
                if target_key in completed_domains:
                    self.logger.info(
                        "domain_skipped",
                        message=f"[{index}/{total_domains}] Skipping completed domain: {target.label}",
                        domain=target.primary_domain,
                        progress="%d/%d" % (index, total_domains),
                    )
                    continue
                if max_domains is not None and attempted_domains >= max_domains:
                    break
                pending_targets.append((index, target))
                attempted_domains += 1

            storage_lock = threading.Lock()
            worker_storage = LockedStorageBackend(self.storage, storage_lock)
            can_parallelize = (
                self.settings.domain_concurrency > 1
                and not self._custom_parser
                and not self._custom_http_fetcher
                and not self._custom_browser_fetcher
                and not self._custom_ai_enhancer
                and len(pending_targets) > 1
            )

            def process(index_and_target: tuple[int, CrawlTarget]) -> tuple[int, DomainRunResult]:
                index, target = index_and_target
                self.logger.info(
                    "domain_started",
                    message=f"[{index}/{total_domains}] Processing domain: {target.label}",
                    domain=target.primary_domain,
                    seed_url=target.seed_urls[0] if target.seed_urls else None,
                    progress="%d/%d" % (index, total_domains),
                )
                if can_parallelize:
                    http_fetcher = HttpFetcher(self.settings)
                    browser_fetcher = BrowserFetcher(self.settings) if self.settings.browser_fallback else None
                    parser = GenericFundingParser(self.settings)
                    ai_enhancer = self._build_ai_classifier()
                    try:
                        return index, self._process_target(
                            target=target,
                            storage=worker_storage,
                            parser=parser,
                            http_fetcher=http_fetcher,
                            browser_fetcher=browser_fetcher,
                            ai_enhancer=ai_enhancer,
                        )
                    finally:
                        http_fetcher.close()
                        if browser_fetcher:
                            browser_fetcher.close()
                return index, self._process_target(
                    target=target,
                    storage=self.storage,
                    parser=self.parser,
                    http_fetcher=self.http_fetcher,
                    browser_fetcher=self.browser_fetcher,
                    ai_enhancer=self.ai_enhancer,
                )

            ordered_results: List[tuple[int, DomainRunResult]] = []
            if can_parallelize:
                with ThreadPoolExecutor(max_workers=self.settings.domain_concurrency) as executor:
                    future_map = {executor.submit(process, item): item[0] for item in pending_targets}
                    for future in as_completed(future_map):
                        ordered_results.append(future.result())
                ordered_results.sort(key=lambda item: item[0])
            else:
                ordered_results = [process(item) for item in pending_targets]

            for index, result in ordered_results:
                target = result.target
                target_key = target.key or target.primary_domain
                stats = result.crawl_stats
                aggregate_total_urls_crawled += int(stats.get("total_urls_crawled", 0))
                aggregate_pages_fetched_successfully += int(stats.get("pages_fetched_successfully", 0))
                aggregate_pages_failed += int(stats.get("pages_failed", 0))
                aggregate_programmes_extracted += len(result.classified_records)
                aggregate_errors.extend(result.errors)
                aggregate_warnings.extend(result.warnings)
                domain_merge_traces.extend(result.merge_trace)
                borderline_count += len(result.borderline_records)
                rejected_count += result.rejected_count
                browser_fallback_count += int(stats.get("browser_fallback_count", 0))
                retry_count += int(stats.get("retry_count", 0))
                queue_saturation_count += int(stats.get("queue_saturation_count", 0))
                pages_for_timing = int(stats.get("pages_fetched_successfully", 0))
                fetch_time_weighted_total += float(stats.get("average_fetch_time_seconds", 0.0)) * pages_for_timing
                fetch_time_weight += pages_for_timing
                for reason, count_value in dict(stats.get("skipped_url_counts", {})).items():
                    skipped_url_counts[reason] = skipped_url_counts.get(reason, 0) + int(count_value)

                if result.completed:
                    persisted_records = [record for record in persisted_records if record.source_domain != target.primary_domain]
                    persisted_records.extend(result.accepted_records)
                    review_records = [record for record in review_records if record.source_domain != target.primary_domain]
                    review_records.extend(result.borderline_records)
                    completed_domains.add(target_key)
                    failed_domains.discard(target_key)
                else:
                    failed_domains.add(target_key)

                self.storage.save_programmes(persisted_records)
                self.csv_store.write(persisted_records, self.storage.csv_path)  # type: ignore[attr-defined]
                self.storage.write_borderline_review(review_records)
                self.storage.write_merge_trace(domain_merge_traces)
                self.storage.write_crawl_state(
                    CrawlState(
                        run_id=run_id,
                        completed_domains=sorted(completed_domains),
                        failed_domains=sorted(failed_domains),
                        last_processed_domain=target.primary_domain,
                    )
                )
                record_source_urls = unique_preserve_order(
                    [
                        url
                        for record in [
                            *result.classified_records,
                            *result.accepted_records,
                            *result.borderline_records,
                        ]
                        for url in [record.source_url, *record.source_urls]
                        if url
                    ]
                )
                records_per_source_page: Dict[str, int] = {}
                for record in result.classified_records:
                    if not record.source_url:
                        continue
                    records_per_source_page[record.source_url] = records_per_source_page.get(record.source_url, 0) + 1
                multi_program_pages_detected = sum(1 for count in records_per_source_page.values() if count > 1)
                max_records_from_single_page = max(records_per_source_page.values()) if records_per_source_page else 0
                domain_report = {
                    "site_key": target.key,
                    "display_name": target.label,
                    "domain": target.primary_domain,
                    "adapter": result.adapter_key,
                    "seed_urls": list(target.seed_urls),
                    "pages_fetched_successfully": int(stats.get("pages_fetched_successfully", 0)),
                    "pages_failed": int(stats.get("pages_failed", 0)),
                    "candidate_programme_pages": len({record.source_url for record in result.classified_records if record.source_url}),
                    "multi_program_pages_detected": multi_program_pages_detected,
                    "records_per_source_page": dict(sorted(records_per_source_page.items())),
                    "max_records_from_single_page": max_records_from_single_page,
                    "records_extracted": len(result.classified_records),
                    "records_accepted": len(result.accepted_records),
                    "records_reviewed": len(result.borderline_records),
                    "records_rejected": result.rejected_count,
                    "records_missing_funding_type": sum(
                        1 for record in [*result.accepted_records, *result.borderline_records] if record.funding_type == FundingType.UNKNOWN
                    ),
                    "records_missing_application_route": sum(
                        1
                        for record in [*result.accepted_records, *result.borderline_records]
                        if record.application_channel == ApplicationChannel.UNKNOWN and not record.application_url
                    ),
                    "browser_fallback_count": int(stats.get("browser_fallback_count", 0)),
                    "retry_count": int(stats.get("retry_count", 0)),
                    "queue_saturation_count": int(stats.get("queue_saturation_count", 0)),
                    "source_urls": record_source_urls,
                    "warnings": result.warnings,
                    "errors": result.errors,
                    "completed": result.completed,
                }
                domain_telemetry.append(domain_report)
                qa_coverage_report.append(domain_report)

                self.logger.info(
                    "domain_completed" if result.completed else "domain_failed",
                    message=f"[{index}/{total_domains}] Completed domain: {target.label}" if result.completed else f"[{index}/{total_domains}] Failed domain: {target.label}",
                    domain=target.primary_domain,
                    records=len(result.classified_records),
                    extracted=len(result.documents),
                    adapter=result.adapter_key,
                )

            deduped_records = persisted_records
            low_confidence_records = [
                record for record in deduped_records if is_low_confidence(record, self.settings.low_confidence_threshold)
            ]
            status = "success"
            if not aggregate_pages_fetched_successfully and aggregate_errors:
                status = "failed"
            elif aggregate_errors:
                status = "partial"

            summary = RunSummary(
                run_id=run_id,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                status=status,
                seed_urls=list(run_seed_urls),
                total_urls_crawled=aggregate_total_urls_crawled,
                pages_fetched_successfully=aggregate_pages_fetched_successfully,
                pages_failed=aggregate_pages_failed,
                programmes_extracted=aggregate_programmes_extracted,
                programmes_after_dedupe=len(deduped_records),
                records_with_missing_program_name=sum(1 for record in deduped_records if not record.program_name),
                records_with_missing_funder_name=sum(1 for record in deduped_records if not record.funder_name),
                records_with_unknown_funding_type=sum(1 for record in deduped_records if record.funding_type == FundingType.UNKNOWN),
                records_with_no_application_route=sum(
                    1 for record in deduped_records if record.application_channel == ApplicationChannel.UNKNOWN
                ),
                records_with_low_confidence_extraction=len(low_confidence_records),
                records_with_borderline_review=borderline_count,
                records_rejected_for_quality=rejected_count,
                browser_fallback_count=browser_fallback_count,
                retry_count=retry_count,
                skipped_url_counts=skipped_url_counts,
                queue_saturation_count=queue_saturation_count,
                average_fetch_time_seconds=round(fetch_time_weighted_total / fetch_time_weight, 4)
                if fetch_time_weight
                else 0.0,
                domain_telemetry=domain_telemetry,
                low_confidence_threshold=self.settings.low_confidence_threshold,
                errors=aggregate_errors,
                warnings=aggregate_warnings,
            )
            self.storage.write_run_summary(summary)
            if hasattr(self.storage, "write_qa_coverage_report"):
                self.storage.write_qa_coverage_report(qa_coverage_report)
            self.logger.info("pipeline_completed", run_id=run_id, summary=summary.model_dump(mode="json"))
            return summary
        finally:
            self.close()

    def export_csv(self, output_path: Optional[Path] = None) -> Path:
        records = self.storage.load_normalized_records()
        target_path = output_path or self.storage.csv_path  # type: ignore[attr-defined]
        return self.csv_store.write(records, target_path)


def load_seed_urls(seed_path: Path) -> List[str]:
    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    urls: List[str] = []
    for item in payload:
        if isinstance(item, str):
            urls.append(item)
        elif isinstance(item, dict) and item.get("url"):
            urls.append(str(item["url"]))
    return unique_preserve_order(urls)


def build_settings_from_options(
    output_path: Optional[Path],
    max_pages: Optional[int],
    depth_limit: Optional[int],
    headless: Optional[bool],
    browser_fallback: Optional[bool],
    respect_robots: Optional[bool],
    ai_enrichment: Optional[bool] = None,
    domain_concurrency: Optional[int] = None,
    max_queue_urls: Optional[int] = None,
    max_links_per_page: Optional[int] = None,
    fetch_cache: Optional[bool] = None,
):
    from scraper.config import RuntimeOptions, ScraperSettings

    base = ScraperSettings.from_env()
    return base.with_overrides(
        RuntimeOptions(
            output_path=output_path,
            max_pages=max_pages,
            depth_limit=depth_limit,
            headless=headless,
            browser_fallback=browser_fallback,
            respect_robots=respect_robots,
            ai_enrichment=ai_enrichment,
            domain_concurrency=domain_concurrency,
            max_queue_urls=max_queue_urls,
            max_links_per_page=max_links_per_page,
            fetch_cache=fetch_cache,
        )
    )
