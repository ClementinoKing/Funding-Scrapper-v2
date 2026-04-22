"""Local JSON storage backend."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from scraper.schemas import CrawlState, CrawlTraceEntry, FundingProgrammeRecord, PageDebugPackage, PageFetchResult, RunSummary
from scraper.utils.text import slugify
from scraper.utils.urls import get_domain_slug


class LocalJsonStore:
    """Persist scraper artifacts into the local output directory."""

    def __init__(self, output_root: Path) -> None:
        self.output_root = output_root
        self.raw_dir = self.output_root / "raw"
        self.pages_dir = self.raw_dir / "pages"
        self.normalized_dir = self.output_root / "normalized"
        self.logs_dir = self.output_root / "logs"
        self.debug_dir = self.raw_dir / "debug"
        self.crawl_trace_path = self.logs_dir / "crawl_trace.jsonl"
        self.merge_trace_path = self.logs_dir / "merge_trace.json"
        self.extracted_jsonl_path = self.raw_dir / "extracted_programs.jsonl"
        self.normalized_json_path = self.normalized_dir / "funding_programmes.json"
        self.low_confidence_path = self.normalized_dir / "low_confidence_review.json"
        self.run_summary_path = self.logs_dir / "run_summary.json"
        self.crawl_state_path = self.logs_dir / "crawl_state.json"
        self.csv_path = self.normalized_dir / "funding_programmes.csv"

    def initialize_run(self, run_id: str) -> None:
        self.pages_dir.mkdir(parents=True, exist_ok=True)
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        self.normalized_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        if not self.extracted_jsonl_path.exists():
            self.extracted_jsonl_path.write_text("", encoding="utf-8")
        if not self.crawl_trace_path.exists():
            self.crawl_trace_path.write_text("", encoding="utf-8")
        if not self.merge_trace_path.exists():
            self.merge_trace_path.write_text("[]\n", encoding="utf-8")
        if not self.normalized_json_path.exists():
            self.normalized_json_path.write_text("[]\n", encoding="utf-8")
        if not self.low_confidence_path.exists():
            self.low_confidence_path.write_text("[]\n", encoding="utf-8")
        if not self.crawl_state_path.exists():
            self.write_crawl_state(CrawlState(run_id=run_id))
        self.run_summary_path.write_text(
            json.dumps({"run_id": run_id, "status": "initialized"}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _page_basename(self, page: PageFetchResult) -> str:
        domain_slug = get_domain_slug(page.canonical_url)
        path_slug = slugify(page.canonical_url.split("://", 1)[-1], max_length=80)
        return "%s_%s" % (domain_slug, path_slug)

    def save_page_snapshot(self, page: PageFetchResult) -> Path:
        basename = self._page_basename(page)
        html_path = self.pages_dir / ("%s.html" % basename)
        metadata_path = self.pages_dir / ("%s.json" % basename)
        html_path.write_text(page.html, encoding="utf-8")
        metadata_path.write_text(page.model_dump_json(indent=2), encoding="utf-8")
        return html_path

    def write_page_debug_package(self, package: PageDebugPackage) -> Path:
        basename = slugify(package.final_url or package.page_url, max_length=80)
        path = self.debug_dir / ("%s.json" % basename)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(package.model_dump_json(indent=2), encoding="utf-8")
        return path

    def append_extracted_record(self, record: FundingProgrammeRecord) -> None:
        with self.extracted_jsonl_path.open("a", encoding="utf-8") as handle:
            handle.write(record.model_dump_json())
            handle.write("\n")

    def append_crawl_trace(self, entry: CrawlTraceEntry) -> None:
        with self.crawl_trace_path.open("a", encoding="utf-8") as handle:
            handle.write(entry.model_dump_json())
            handle.write("\n")

    def save_programmes(self, records: List[FundingProgrammeRecord]) -> Path:
        payload = [record.model_dump(mode="json") for record in records]
        self.normalized_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return self.normalized_json_path

    def write_normalized_records(self, records: List[FundingProgrammeRecord]) -> Path:
        return self.save_programmes(records)

    def write_low_confidence_review(self, records: List[FundingProgrammeRecord]) -> Path:
        payload = [record.model_dump(mode="json") for record in records]
        self.low_confidence_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return self.low_confidence_path

    def write_borderline_review(self, records: List[FundingProgrammeRecord]) -> Path:
        return self.write_low_confidence_review(records)

    def load_borderline_review_records(self) -> List[FundingProgrammeRecord]:
        if not self.low_confidence_path.exists():
            return []
        payload = json.loads(self.low_confidence_path.read_text(encoding="utf-8"))
        return [FundingProgrammeRecord.model_validate(item) for item in payload]

    def write_merge_trace(self, trace: List[dict]) -> Path:
        self.merge_trace_path.write_text(json.dumps(trace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return self.merge_trace_path

    def write_run_summary(self, summary: RunSummary) -> Path:
        self.run_summary_path.write_text(summary.model_dump_json(indent=2), encoding="utf-8")
        return self.run_summary_path

    def load_normalized_records(self) -> List[FundingProgrammeRecord]:
        if not self.normalized_json_path.exists():
            return []
        payload = json.loads(self.normalized_json_path.read_text(encoding="utf-8"))
        return [FundingProgrammeRecord.model_validate(item) for item in payload]

    def load_crawl_state(self) -> CrawlState:
        if not self.crawl_state_path.exists():
            return CrawlState()
        payload = json.loads(self.crawl_state_path.read_text(encoding="utf-8"))
        return CrawlState.model_validate(payload)

    def write_crawl_state(self, state: CrawlState) -> Path:
        self.crawl_state_path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        return self.crawl_state_path
