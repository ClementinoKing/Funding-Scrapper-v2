"""Crawler orchestration for funding programme discovery."""

from __future__ import annotations

import heapq
import gzip
import random
import re
import time
from collections import defaultdict
from itertools import count
from typing import DefaultDict, Dict, List, Optional, Sequence, Set, Tuple
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
from scraper.utils.urls import canonicalize_url, extract_host, is_internal_url, is_probably_document_url, looks_irrelevant_url, score_url_relevance
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
        self._last_fetch_by_host: Dict[str, float] = {}

    def _sleep(self, url: str = "") -> None:
        delay = random.uniform(self.settings.delay_min_seconds, self.settings.delay_max_seconds)
        host = extract_host(url)
        if not host:
            time.sleep(delay)
            return
        now = time.monotonic()
        next_allowed_at = self._last_fetch_by_host.get(host, 0.0) + delay
        sleep_for = max(0.0, next_allowed_at - now)
        if sleep_for:
            time.sleep(sleep_for)
        self._last_fetch_by_host[host] = time.monotonic()

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
        return self._browser_fallback_reason(page, adapter) is not None

    def _browser_fallback_reason(self, page: PageFetchResult, adapter: Optional[SiteAdapter]) -> Optional[str]:
        if not self.browser_fetcher:
            return None
        if is_probably_document_url(page.requested_url or page.canonical_url or page.final_url or page.url):
            return None
        if adapter and adapter.should_use_browser(page):
            return "adapter-browser-rule"
        if page.status_code in {401, 403, 429}:
            return "restricted-or-rate-limited-status"
        if not page.succeeded:
            return "http-fetch-failed"
        lowered = (page.html or "").lower()
        if any(term in lowered for term in ("checking your browser", "cf-browser-verification", "cf-challenge", "just a moment")):
            return "browser-challenge"
        if "enable javascript" in lowered or "requires javascript" in lowered:
            return "javascript-required"
        stripped_length = self._stripped_text_length(page.html)
        if stripped_length < 220:
            return "thin-html"
        if stripped_length < 450 and lowered.count("<script") >= 2:
            return "spa-shell"
        shell_signals = ("data-reactroot", 'id="root"', "id='root'", 'id="app"', "id='app'", "ng-app", "__next", "gatsby", "vue")
        if stripped_length < 650 and any(signal in lowered for signal in shell_signals):
            return "app-shell"
        return None

    def _fetch_sitemap_urls(self, domain: str) -> List[str]:
        if not hasattr(self.http_fetcher, "client") or not hasattr(self.http_fetcher, "_headers"):
            return []
        discovered: List[str] = []
        seen: Set[str] = set()

        def looks_like_sitemap(candidate: str) -> bool:
            lowered = candidate.lower()
            return (lowered.endswith(".xml") or lowered.endswith(".xml.gz")) and "sitemap" in lowered

        def response_text(response) -> str:
            body = getattr(response, "content", b"") or b""
            if str(getattr(response, "url", "")).lower().endswith(".gz") or urlparse_content_type(response).endswith("gzip"):
                try:
                    body = gzip.decompress(body)
                except Exception:
                    pass
            if body:
                try:
                    return body.decode(getattr(response, "encoding", None) or "utf-8", errors="replace")
                except Exception:
                    return getattr(response, "text", "") or ""
            return getattr(response, "text", "") or ""

        def urlparse_content_type(response) -> str:
            return (getattr(response, "headers", {}) or {}).get("content-type", "").lower()

        def collect(url: str, depth: int = 0) -> None:
            if depth > 2:
                return
            canonical = canonicalize_url(url)
            if canonical in seen:
                return
            seen.add(canonical)
            try:
                response = self.http_fetcher.client.get(canonical, headers=self.http_fetcher._headers())  # type: ignore[attr-defined]
                text = response_text(response)
                if response.status_code != 200 or not text:
                    return
                try:
                    root = ET.fromstring(text)
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

        def collect_robots_sitemaps() -> None:
            try:
                robots_url = urljoin(f"https://{domain}", "/robots.txt")
                response = self.http_fetcher.client.get(robots_url, headers=self.http_fetcher._headers())  # type: ignore[attr-defined]
                if response.status_code != 200:
                    return
                for line in (response.text or "").splitlines():
                    if line.lower().startswith("sitemap:"):
                        sitemap_url = line.split(":", 1)[1].strip()
                        if sitemap_url:
                            collect(sitemap_url)
            except Exception:
                return

        collect_robots_sitemaps()
        collect(urljoin(f"https://{domain}", "/sitemap.xml"))
        collect(urljoin(f"https://{domain}", "/sitemap_index.xml"))
        collect(urljoin(f"https://{domain}", "/sitemap.xml.gz"))
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
        allowed_hosts = sorted(
            {
                host
                for host in [
                    *[extract_host(url) for url in seed_urls],
                    *([extract_host(host) for host in adapter.allowed_hosts] if adapter else []),
                ]
                if host
            }
        )
        queue: List[Tuple[float, int, str, int, str]] = []
        order = count()
        queued: Set[str] = set()
        visited: Set[str] = set()
        documents: List[PageContentDocument] = []
        errors: List[str] = []
        warnings: List[str] = []
        pages_fetched_successfully = 0
        pages_failed = 0
        browser_fallback_count = 0
        retry_count = 0
        fetch_time_total = 0.0
        skipped_url_counts: DefaultDict[str, int] = defaultdict(int)
        queue_saturation_count = 0
        crawl_trace: List[CrawlTraceEntry] = []
        max_pages = adapter.max_pages if adapter and adapter.max_pages else self.settings.max_pages
        depth_limit = adapter.depth_limit if adapter and adapter.depth_limit else self.settings.depth_limit
        max_queue_urls = adapter.max_queue_urls if adapter and adapter.max_queue_urls else self.settings.max_queue_urls
        max_links_per_page = (
            adapter.max_links_per_page if adapter and adapter.max_links_per_page else self.settings.max_links_per_page
        )

        def note_skipped(reason: str) -> None:
            skipped_url_counts[reason or "filtered"] += 1

        def enqueue_url(url: str, depth: int, source: str, score: float, reason: str, source_url: Optional[str] = None) -> bool:
            nonlocal queue_saturation_count
            if len(queue) >= max_queue_urls:
                queue_saturation_count += 1
                note_skipped("queue-saturated")
                crawl_trace.append(
                    self._trace(
                        event="skipped",
                        url=url,
                        adapter_name=adapter.key if adapter else None,
                        source_url=source_url,
                        depth=depth,
                        score=score,
                        reason="queue-saturated",
                    )
                )
                return False
            heapq.heappush(queue, (-score, next(order), url, depth, source))
            queued.add(url)
            crawl_trace.append(
                self._trace(
                    event="queued",
                    url=url,
                    adapter_name=adapter.key if adapter else None,
                    source_url=source_url,
                    depth=depth,
                    score=score,
                    reason=reason,
                )
            )
            return True

        for seed_url in seed_urls:
            canonical = canonicalize_url(seed_url)
            enqueue_url(canonical, 0, "seed", 100.0, "seed")

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
                        note_skipped(skip_reason)
                        continue
                    note_skipped(skip_reason or "filtered")
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
                enqueue_url(sitemap_url, 0, "sitemap", score, adapter_reason or skip_reason or "sitemap")

        unlimited_pages = max_pages <= 0
        while queue and (unlimited_pages or len(visited) < max_pages):
            _priority, _order, current_url, depth, source = heapq.heappop(queue)
            queued.discard(current_url)
            if current_url in visited:
                continue
            if not is_internal_url(current_url, allowed_hosts):
                note_skipped("external")
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
                note_skipped("irrelevant-url")
                continue
            if adapter and not adapter.should_allow_url(current_url):
                note_skipped("adapter-rule")
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
            self._sleep(current_url)
            page = self.http_fetcher.fetch(current_url)
            browser_reason = self._browser_fallback_reason(page, adapter)
            if browser_reason:
                try:
                    browser_page = self.browser_fetcher.fetch(
                        current_url,
                        wait_selectors=adapter.browser_wait_selectors if adapter else None,
                    )
                except TypeError:
                    browser_page = self.browser_fetcher.fetch(current_url)
                if browser_page.succeeded or not page.succeeded:
                    browser_page.browser_fallback_reason = browser_reason
                    browser_page.notes = [*browser_page.notes, f"Browser fallback reason: {browser_reason}."]
                    page = browser_page
                    browser_fallback_count += 1
                    crawl_trace.append(
                        self._trace(
                            event="browser_fallback",
                            url=current_url,
                            adapter_name=adapter.key if adapter else None,
                            depth=depth,
                            reason=browser_reason,
                            status_code=page.status_code,
                        )
                    )
            retry_count += page.retry_count
            fetch_time_total += page.elapsed_seconds

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

            if depth >= depth_limit:
                continue

            ranked_links = unique_preserve_order(
                [*page_content.internal_links, *page_content.discovered_links, *page_content.document_links]
            )[:max_links_per_page]
            for discovered_link in ranked_links:
                normalized = canonicalize_url(discovered_link)
                if not normalized:
                    continue
                if normalized in visited or normalized in queued:
                    continue
                if not is_internal_url(normalized, allowed_hosts):
                    note_skipped("external")
                    continue
                score, skip_reason, adapter_reason = self._score_candidate_url(
                    normalized,
                    depth=depth,
                    source="page-link",
                    adapter=adapter,
                )
                if score is None:
                    if skip_reason == "irrelevant-url":
                        note_skipped(skip_reason)
                        continue
                    note_skipped(skip_reason or "filtered")
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
                enqueue_url(normalized, depth + 1, "page-link", score, adapter_reason or "content-extracted", current_url)

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
            "browser_fallback_count": browser_fallback_count,
            "retry_count": retry_count,
            "skipped_url_counts": dict(skipped_url_counts),
            "queue_saturation_count": queue_saturation_count,
            "average_fetch_time_seconds": round(fetch_time_total / pages_fetched_successfully, 4)
            if pages_fetched_successfully
            else 0.0,
        }
