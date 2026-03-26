"""Crawler orchestration for funding programme discovery."""

from __future__ import annotations

import heapq
import random
import re
import time
from itertools import count
from typing import Dict, List, Optional, Sequence, Set, Tuple
from urllib.parse import urljoin
from xml.etree import ElementTree as ET

from scraper.config import ScraperSettings
from scraper.adapters.base import SiteAdapter
from scraper.fetchers.browser_fetcher import BrowserFetcher
from scraper.fetchers.http_fetcher import HttpFetcher
from scraper.parsers.generic_parser import GenericFundingParser
from scraper.schemas import CrawlTraceEntry, FundingProgrammeRecord, PageFetchResult
from scraper.storage.interfaces import StorageBackend
from scraper.utils.logging import get_logger
from scraper.utils.text import unique_preserve_order
from scraper.utils.urls import canonicalize_url, extract_domain, is_internal_url, looks_irrelevant_url, score_url_relevance


class Crawler:
    """Breadth-first crawler tuned for funding pages within allowed domains."""

    def __init__(
        self,
        settings: ScraperSettings,
        storage: StorageBackend,
        parser: GenericFundingParser,
        http_fetcher: HttpFetcher,
        browser_fetcher: Optional[BrowserFetcher] = None,
    ) -> None:
        self.settings = settings
        self.storage = storage
        self.parser = parser
        self.http_fetcher = http_fetcher
        self.browser_fetcher = browser_fetcher
        self.logger = get_logger(__name__)

    def _sleep(self) -> None:
        delay = random.uniform(self.settings.delay_min_seconds, self.settings.delay_max_seconds)
        time.sleep(delay)

    def _trace(self, **kwargs) -> CrawlTraceEntry:
        return CrawlTraceEntry(**kwargs)

    @staticmethod
    def _stripped_text_length(html: str) -> int:
        return len(re.sub(r"<[^>]+>", " ", html or " ").strip())

    def _should_try_browser(self, page: PageFetchResult) -> bool:
        if not self.browser_fetcher:
            return False
        if not page.succeeded:
            return True
        lowered = (page.html or "").lower()
        if "enable javascript" in lowered or "requires javascript" in lowered:
            return True
        if self._stripped_text_length(page.html) < 300 and lowered.count("<script") >= 5:
            return True
        return False

    def _should_try_browser_for_adapter(self, page: PageFetchResult, adapter: Optional[SiteAdapter]) -> bool:
        if not self.browser_fetcher:
            return False
        if adapter and adapter.should_use_browser(page):
            return True
        if page.status_code in {401, 403, 429}:
            return True
        return self._should_try_browser(page)

    def _fetch_sitemap_urls(self, domain: str) -> List[str]:
        if not hasattr(self.http_fetcher, "client") or not hasattr(self.http_fetcher, "_headers"):
            return []
        discovered: List[str] = []
        seen: Set[str] = set()

        def looks_like_sitemap(candidate: str) -> bool:
            lowered = candidate.lower()
            return lowered.endswith(".xml") and "sitemap" in lowered

        def collect(url: str, depth: int = 0) -> None:
            if depth > 2:
                return
            canonical = canonicalize_url(url)
            if canonical in seen:
                return
            seen.add(canonical)
            try:
                response = self.http_fetcher.client.get(canonical, headers=self.http_fetcher._headers())  # type: ignore[attr-defined]
                if response.status_code != 200 or not response.text:
                    return
                try:
                    root = ET.fromstring(response.text)
                except ET.ParseError:
                    return
                namespaces = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
                locs = [loc.text.strip() for loc in root.findall(".//sm:loc", namespaces=namespaces) if loc.text]
                if not locs:
                    locs = [loc.text.strip() for loc in root.iter() if loc.tag.endswith("loc") and loc.text]
                for loc in locs:
                    next_url = canonicalize_url(loc)
                    if looks_like_sitemap(next_url):
                        collect(next_url, depth + 1)
                    elif is_internal_url(next_url, [domain]):
                        discovered.append(next_url)
            except Exception:
                return

        collect(urljoin(f"https://{domain}", "/sitemap.xml"))
        collect(urljoin(f"https://{domain}", "/sitemap_index.xml"))
        return list(dict.fromkeys(discovered))

    def crawl(
        self,
        seed_urls: Sequence[str],
        adapter: Optional[SiteAdapter] = None,
    ) -> Tuple[List[FundingProgrammeRecord], Dict[str, object]]:
        allowed_domains = sorted({extract_domain(url) for url in seed_urls})
        queue: List[Tuple[float, int, str, int, str]] = []
        order = count()
        queued: Set[str] = set()
        visited: Set[str] = set()
        records: List[FundingProgrammeRecord] = []
        errors: List[str] = []
        warnings: List[str] = []
        pages_fetched_successfully = 0
        pages_failed = 0
        crawl_trace: List[CrawlTraceEntry] = []

        for seed_url in seed_urls:
            canonical = canonicalize_url(seed_url)
            heapq.heappush(queue, (-100.0, next(order), canonical, 0, "seed"))
            queued.add(canonical)
            crawl_trace.append(
                self._trace(
                    event="queued",
                    url=canonical,
                    adapter_name=adapter.key if adapter else None,
                    depth=0,
                    score=100.0,
                    reason="seed",
                )
            )

        for domain in allowed_domains:
            for sitemap_url in self._fetch_sitemap_urls(domain):
                if sitemap_url not in queued and sitemap_url not in visited and is_internal_url(sitemap_url, allowed_domains):
                    heapq.heappush(queue, (-25.0, next(order), sitemap_url, 0, "sitemap"))
                    queued.add(sitemap_url)
                    crawl_trace.append(
                        self._trace(
                            event="queued",
                            url=sitemap_url,
                            adapter_name=adapter.key if adapter else None,
                            depth=0,
                            score=25.0,
                            reason="sitemap",
                        )
                    )

        unlimited_pages = self.settings.max_pages <= 0
        while queue and (unlimited_pages or len(visited) < self.settings.max_pages):
            _priority, _order, current_url, depth, source = heapq.heappop(queue)
            queued.discard(current_url)
            if current_url in visited:
                continue
            if not is_internal_url(current_url, allowed_domains):
                crawl_trace.append(
                    self._trace(
                        event="skipped",
                        url=current_url,
                        adapter_name=adapter.key if adapter else None,
                        depth=depth,
                        reason="external",
                    )
                )
                continue
            if looks_irrelevant_url(current_url, self.settings.irrelevant_url_patterns):
                crawl_trace.append(
                    self._trace(
                        event="skipped",
                        url=current_url,
                        adapter_name=adapter.key if adapter else None,
                        depth=depth,
                        reason="irrelevant-url",
                    )
                )
                continue
            if adapter and not adapter.should_allow_url(current_url):
                crawl_trace.append(
                    self._trace(
                        event="skipped",
                        url=current_url,
                        adapter_name=adapter.key,
                        depth=depth,
                        reason="adapter-rule",
                    )
                )
                continue

            visited.add(current_url)
            crawl_trace.append(
                self._trace(
                    event="visited",
                    url=current_url,
                    adapter_name=adapter.key if adapter else None,
                    depth=depth,
                    reason=source,
                )
            )
            self._sleep()
            page = self.http_fetcher.fetch(current_url)
            if self._should_try_browser_for_adapter(page, adapter):
                browser_page = self.browser_fetcher.fetch(current_url)
                if browser_page.succeeded or not page.succeeded:
                    page = browser_page

            if not page.succeeded:
                pages_failed += 1
                message = "Failed to fetch %s (%s)" % (current_url, "; ".join(page.notes))
                errors.append(message)
                self.logger.error("page_fetch_failed", url=current_url, notes=page.notes)
                crawl_trace.append(
                    self._trace(
                        event="failed",
                        url=current_url,
                        adapter_name=adapter.key if adapter else None,
                        depth=depth,
                        reason="; ".join(page.notes),
                        status_code=page.status_code,
                    )
                )
                continue

            pages_fetched_successfully += 1
            self.storage.save_page_snapshot(page)
            extraction = self.parser.parse(page, allowed_domains=allowed_domains, adapter=adapter)
            page_role = adapter.page_role(
                page_url=page.canonical_url,
                page_title=page.title,
                text=" ".join(record.program_name or "" for record in extraction.records) or (page.html or ""),
                record_count=len(extraction.records),
                candidate_block_count=len(extraction.records),
                internal_link_count=len(extraction.internal_links),
                detail_link_count=len(extraction.discovered_links),
                application_link_count=len(extraction.application_links),
                document_link_count=len(extraction.document_links),
            ) if adapter else extraction.page_type
            self.storage.append_crawl_trace(
                self._trace(
                    event="parsed",
                    url=current_url,
                    adapter_name=adapter.key if adapter else None,
                    source_url=page.requested_url,
                    canonical_url=page.canonical_url,
                    depth=depth,
                    reason=extraction.page_type,
                    page_role=page_role,
                    status_code=page.status_code,
                    records_found=len(extraction.records),
                    discovered_links=len(extraction.internal_links),
                    document_links=len(extraction.document_links),
                    notes=extraction.notes + extraction.warnings,
                )
            )
            warnings.extend(extraction.warnings)
            if extraction.notes:
                self.logger.info("page_parsed", url=current_url, notes=extraction.notes, records=len(extraction.records))

            for record in list(extraction.records):
                normalized_record = (
                    adapter.normalize_record(
                        record,
                        page_type=extraction.page_type,
                        page_url=page.canonical_url,
                        page_title=page.title,
                    )
                    if adapter
                    else record
                )
                if adapter and not adapter.should_promote_record(normalized_record, extraction.page_type):
                    continue
                enriched_payload = normalized_record.model_dump(mode="python", exclude={"site_adapter", "page_type"})
                enriched_record = record.model_copy(update=enriched_payload)
                enriched_record = enriched_record.model_copy(
                    update={
                        "site_adapter": adapter.key if adapter else record.site_adapter,
                        "page_type": extraction.page_type,
                    }
                )
                records.append(enriched_record)
                self.storage.append_extracted_record(enriched_record)
                self.storage.append_crawl_trace(
                    self._trace(
                        event="extracted",
                        url=current_url,
                        adapter_name=adapter.key if adapter else None,
                        canonical_url=page.canonical_url,
                        depth=depth,
                        reason=enriched_record.program_name or enriched_record.funder_name,
                        page_type=extraction.page_type,
                        page_role=page_role,
                        records_found=1,
                        document_links=len(enriched_record.related_documents),
                        notes=enriched_record.notes,
                    )
                )

            if depth >= self.settings.depth_limit:
                continue

            ranked_links = extraction.internal_links + extraction.discovered_links + extraction.document_links
            for discovered_link in ranked_links:
                normalized = canonicalize_url(discovered_link)
                if not normalized:
                    continue
                if normalized in visited or normalized in queued:
                    continue
                if not is_internal_url(normalized, allowed_domains):
                    continue
                if adapter and not adapter.should_allow_url(normalized):
                    crawl_trace.append(
                        self._trace(
                            event="skipped",
                            url=normalized,
                            adapter_name=adapter.key,
                            source_url=current_url,
                            depth=depth + 1,
                            reason="adapter-rule",
                        )
                    )
                    continue
                score = score_url_relevance(
                    normalized,
                    "",
                    self.settings.relevant_keywords,
                    self.settings.irrelevant_url_patterns,
                )
                if normalized.endswith(".pdf"):
                    score += 6
                if any(term in normalized.lower() for term in ["fund", "grant", "loan", "finance", "apply", "program", "programme"]):
                    score += 8
                if depth == 0:
                    score += 3
                if adapter:
                    adapter_bonus, adapter_reason = adapter.queue_score_bonus(normalized)
                    score += adapter_bonus
                else:
                    adapter_reason = None
                heapq.heappush(queue, (-float(score), next(order), normalized, depth + 1, "page-link"))
                queued.add(normalized)
                crawl_trace.append(
                    self._trace(
                        event="queued",
                        url=normalized,
                        adapter_name=adapter.key if adapter else None,
                        source_url=current_url,
                        depth=depth + 1,
                        score=float(score),
                        reason=adapter_reason or extraction.page_type,
                    )
                )

        for entry in crawl_trace:
            self.storage.append_crawl_trace(entry)

        return records, {
            "total_urls_crawled": len(visited),
            "pages_fetched_successfully": pages_fetched_successfully,
            "pages_failed": pages_failed,
            "errors": errors,
            "warnings": warnings,
            "crawl_trace_entries": len(crawl_trace),
            "adapter_name": adapter.key if adapter else "generic",
        }
