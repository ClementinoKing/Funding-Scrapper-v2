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
from scraper.schemas import CrawlTraceEntry, PageContentDocument, PageFetchResult
from scraper.storage.interfaces import StorageBackend
from scraper.utils.logging import get_logger
from scraper.utils.text import unique_preserve_order
from scraper.utils.urls import canonicalize_url, extract_host, is_internal_url, looks_irrelevant_url, score_url_relevance
from scraper.utils.quality import score_programme_quality


DISCOVERY_URL_HINTS = (
    "fund",
    "funding",
    "investment",
    "portfolio",
    "properties",
    "isibaya",
    "early-stage",
    "early stage",
    "unlisted",
    "development",
    "procurement",
)


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
        stripped_length = self._stripped_text_length(page.html)
        shell_signals = (
            "data-reactroot",
            'id="root"',
            "id='root'",
            'id="app"',
            "id='app'",
            "ng-app",
            "__next",
            "gatsby",
            "vue",
        )
        if stripped_length < 220:
            return True
        if stripped_length < 450 and (lowered.count("<script") >= 2 or any(signal in lowered for signal in shell_signals)):
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

    def _score_candidate_url(
        self,
        url: str,
        *,
        depth: int,
        source: str,
        adapter: Optional[SiteAdapter] = None,
        anchor_text: str = "",
    ) -> Tuple[Optional[float], Optional[str], Optional[str]]:
        if looks_irrelevant_url(url, self.settings.irrelevant_url_patterns):
            return None, "irrelevant-url", None
        if adapter and not adapter.should_allow_url(url, anchor_text):
            return None, "adapter-rule", None

        score = float(
            score_url_relevance(
                url,
                anchor_text,
                self.settings.relevant_keywords,
                self.settings.irrelevant_url_patterns,
            )
        )
        if source == "sitemap":
            # Sitemap discovery is a useful fallback, but it should not outrank
            # explicit seed paths or page-linked discoveries by default.
            score += 4
        if url.endswith(".pdf"):
            score += 6
        if any(term in url.lower() for term in ["fund", "grant", "loan", "finance", "apply", "program", "programme"]):
            score += 8
        if any(term in "%s %s" % (url.lower(), anchor_text.lower()) for term in DISCOVERY_URL_HINTS):
            score += 7
        if source == "page-link" and depth == 0:
            score += 3

        adapter_reason = None
        if adapter:
            adapter_bonus, adapter_reason = adapter.queue_score_bonus(url, anchor_text)
            score += adapter_bonus

        return score, None, adapter_reason

    def _effective_record_page_type(
        self,
        *,
        adapter: Optional[SiteAdapter],
        page: PageFetchResult,
        extraction_page_type: str,
        record: FundingProgrammeRecord,
    ) -> str:
        if not adapter or extraction_page_type != "support-document":
            return extraction_page_type

        quality_score, _quality_reasons, _quality_blockers = score_programme_quality(record)
        if adapter.should_allow_url(page.canonical_url) and quality_score >= self.settings.programme_accept_threshold:
            return "detail"

        return extraction_page_type

    @staticmethod
    def _source_scope_for_page_type(page_type: Optional[str], current_scope: Optional[str] = None) -> Optional[str]:
        if page_type == "parent":
            return "parent_page"
        if page_type in {"support-document", "application_support_page", "supporting_or_complementary_programme_page"}:
            return "support_page"
        if current_scope:
            return current_scope
        return "product_page"

    def crawl(
        self,
        seed_urls: Sequence[str],
        adapter: Optional[SiteAdapter] = None,
    ) -> Tuple[List[PageContentDocument], Dict[str, object]]:
        allowed_hosts = sorted({extract_host(url) for url in seed_urls})
        queue: List[Tuple[float, int, str, int, str]] = []
        order = count()
        queued: Set[str] = set()
        visited: Set[str] = set()
        documents: List[PageContentDocument] = []
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

        for domain in allowed_hosts:
            for sitemap_url in self._fetch_sitemap_urls(domain):
                if sitemap_url in queued or sitemap_url in visited or not is_internal_url(sitemap_url, allowed_hosts):
                    continue
                score, skip_reason, adapter_reason = self._score_candidate_url(
                    sitemap_url,
                    depth=0,
                    source="sitemap",
                    adapter=adapter,
                )
                if score is None:
                    if skip_reason == "irrelevant-url":
                        continue
                    crawl_trace.append(
                        self._trace(
                            event="skipped",
                            url=sitemap_url,
                            adapter_name=adapter.key if adapter else None,
                            depth=0,
                            reason=skip_reason or "filtered",
                        )
                    )
                    continue
                heapq.heappush(queue, (-score, next(order), sitemap_url, 0, "sitemap"))
                queued.add(sitemap_url)
                crawl_trace.append(
                    self._trace(
                        event="queued",
                        url=sitemap_url,
                        adapter_name=adapter.key if adapter else None,
                        depth=0,
                        score=score,
                        reason=adapter_reason or skip_reason or "sitemap",
                    )
                )

        unlimited_pages = self.settings.max_pages <= 0
        while queue and (unlimited_pages or len(visited) < self.settings.max_pages):
            _priority, _order, current_url, depth, source = heapq.heappop(queue)
            queued.discard(current_url)
            if current_url in visited:
                continue
            if not is_internal_url(current_url, allowed_hosts):
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
            page_content = self.parser.parse(page, allowed_domains=allowed_hosts, adapter=adapter)
            self.storage.write_page_content_document(page_content)
            self.storage.append_crawl_trace(
                self._trace(
                    event="content_extracted",
                    url=current_url,
                    adapter_name=adapter.key if adapter else None,
                    source_url=page.requested_url,
                    canonical_url=page.canonical_url,
                    depth=depth,
                    reason=page_content.title or page_content.page_title or "content",
                    status_code=page.status_code,
                    records_found=0,
                    discovered_links=len(page_content.internal_links),
                    document_links=len(page_content.document_links),
                    notes=[page_content.title or "", page_content.main_content_hint or ""],
                )
            )
            documents.append(page_content)
            if page_content.headings:
                self.logger.info("page_content_extracted", url=current_url, headings=len(page_content.headings))

            if depth >= self.settings.depth_limit:
                continue

            ranked_links = page_content.internal_links + page_content.discovered_links + page_content.document_links
            for discovered_link in ranked_links:
                normalized = canonicalize_url(discovered_link)
                if not normalized:
                    continue
                if normalized in visited or normalized in queued:
                    continue
                if not is_internal_url(normalized, allowed_hosts):
                    continue
                score, skip_reason, adapter_reason = self._score_candidate_url(
                    normalized,
                    depth=depth,
                    source="page-link",
                    adapter=adapter,
                )
                if score is None:
                    if skip_reason == "irrelevant-url":
                        continue
                    crawl_trace.append(
                        self._trace(
                            event="skipped",
                            url=normalized,
                            adapter_name=adapter.key if adapter else None,
                            source_url=current_url,
                            depth=depth + 1,
                            reason=skip_reason or "filtered",
                        )
                    )
                    continue
                heapq.heappush(queue, (-score, next(order), normalized, depth + 1, "page-link"))
                queued.add(normalized)
                crawl_trace.append(
                    self._trace(
                        event="queued",
                        url=normalized,
                        adapter_name=adapter.key if adapter else None,
                        source_url=current_url,
                        depth=depth + 1,
                        score=score,
                        reason=adapter_reason or "content-extracted",
                    )
                )

        for entry in crawl_trace:
            self.storage.append_crawl_trace(entry)

        return documents, {
            "total_urls_crawled": len(visited),
            "pages_fetched_successfully": pages_fetched_successfully,
            "pages_failed": pages_failed,
            "errors": errors,
            "warnings": warnings,
            "crawl_trace_entries": len(crawl_trace),
            "adapter_name": adapter.key if adapter else "generic",
        }
