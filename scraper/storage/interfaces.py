"""Storage interface definitions."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Protocol

from scraper.schemas import (
    CrawlState,
    CrawlTraceEntry,
    FundingProgrammeRecord,
    PageContentDocument,
    PageDebugPackage,
    PageFetchResult,
    RunSummary,
)


class StorageBackend(Protocol):
    output_root: Path
    csv_path: Path

    def initialize_run(self, run_id: str) -> None:
        ...

    def save_page_snapshot(self, page: PageFetchResult) -> Path:
        ...

    def write_page_content_document(self, document: PageContentDocument) -> Path:
        ...

    def write_page_debug_package(self, package: PageDebugPackage) -> Path:
        ...

    def append_crawl_trace(self, entry: CrawlTraceEntry) -> None:
        ...

    def append_extracted_record(self, record: FundingProgrammeRecord) -> None:
        ...

    def write_ai_input(self, document: PageContentDocument, payload: object) -> Path:
        ...

    def write_ai_output(self, document: PageContentDocument, payload: object) -> Path:
        ...

    def write_ai_error(self, document: PageContentDocument, payload: object) -> Path:
        ...

    def save_programmes(self, records: List[FundingProgrammeRecord]) -> Path:
        ...

    def write_normalized_records(self, records: List[FundingProgrammeRecord]) -> Path:
        ...

    def write_low_confidence_review(self, records: List[FundingProgrammeRecord]) -> Path:
        ...

    def write_borderline_review(self, records: List[FundingProgrammeRecord]) -> Path:
        ...

    def write_merge_trace(self, trace: List[dict]) -> Path:
        ...

    def write_run_summary(self, summary: RunSummary) -> Path:
        ...

    def write_qa_coverage_report(self, report: List[Dict[str, Any]]) -> Path:
        ...

    def load_normalized_records(self) -> List[FundingProgrammeRecord]:
        ...

    def load_crawl_state(self) -> CrawlState:
        ...

    def write_crawl_state(self, state: CrawlState) -> Path:
        ...

    def load_borderline_review_records(self) -> List[FundingProgrammeRecord]:
        ...
