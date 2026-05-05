"""Primary HTTP fetcher with retry, throttling support hooks, and robots checks."""

from __future__ import annotations

import random
import re
import time
from typing import Dict, Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from scraper.config import ScraperSettings
from scraper.schemas import PageFetchResult
from scraper.utils.logging import get_logger
from scraper.utils.document_reader import DOCUMENT_KIND_IMAGE, compact_document_text, extract_local_document_text, infer_document_kind
from scraper.utils.urls import is_probably_document_url


TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class HttpFetcher:
    """HTTP client wrapper for resilient HTML retrieval."""

    def __init__(self, settings: ScraperSettings) -> None:
        self.settings = settings
        self.logger = get_logger(__name__)
        self.client = httpx.Client(timeout=settings.timeout_seconds, follow_redirects=True)
        self.robots_cache: Dict[str, RobotFileParser] = {}
        self._cache: Dict[str, PageFetchResult] = {}

    def close(self) -> None:
        self.client.close()

    def _headers(self) -> Dict[str, str]:
        return {
            "User-Agent": random.choice(self.settings.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-ZA,en;q=0.9,en-US;q=0.8",
            "Cache-Control": "no-cache",
        }

    def _load_robots(self, url: str) -> RobotFileParser:
        parsed = urlparse(url)
        key = "%s://%s" % (parsed.scheme, parsed.netloc)
        if key in self.robots_cache:
            return self.robots_cache[key]

        robots_url = urljoin(key, "/robots.txt")
        parser = RobotFileParser()
        try:
            response = self.client.get(robots_url, headers=self._headers())
            if response.status_code == 200:
                parser.parse(response.text.splitlines())
            else:
                parser.parse([])
        except Exception:
            parser.parse([])
        self.robots_cache[key] = parser
        return parser

    def can_fetch(self, url: str) -> bool:
        if not self.settings.respect_robots:
            return True
        parser = self._load_robots(url)
        user_agent = self._headers()["User-Agent"]
        return parser.can_fetch(user_agent, url)

    def fetch(self, url: str) -> PageFetchResult:
        start_time = time.monotonic()
        if self.settings.fetch_cache and url in self._cache:
            cached = self._cache[url].model_copy(deep=True)
            cached.notes = [*cached.notes, "Served from in-run fetch cache."]
            return cached

        if not self.can_fetch(url):
            return PageFetchResult(
                url=url,
                requested_url=url,
                canonical_url=url,
                status_code=None,
                html="",
                title=None,
                fetch_method="http",
                elapsed_seconds=round(time.monotonic() - start_time, 4),
                notes=["Blocked by robots.txt"],
            )

        headers = self._headers()
        response: Optional[httpx.Response] = None
        retry_count = 0
        try:
            attempts = max(1, self.settings.retries)
            for attempt_number in range(1, attempts + 1):
                try:
                    response = self.client.get(url, headers=headers)
                except (httpx.RequestError, httpx.TimeoutException):
                    if attempt_number >= attempts:
                        raise
                    retry_count += 1
                    time.sleep(min(8.0, (2 ** (attempt_number - 1))) + random.uniform(0, 0.5))
                    continue
                if response.status_code not in RETRYABLE_STATUS_CODES or attempt_number >= attempts:
                    break
                retry_count += 1
                retry_after = response.headers.get("retry-after")
                delay = None
                if retry_after:
                    try:
                        delay = min(float(retry_after), 8.0)
                    except ValueError:
                        delay = None
                if delay is None:
                    delay = min(8.0, (2 ** (attempt_number - 1))) + random.uniform(0, 0.5)
                time.sleep(delay)
            assert response is not None
            content_type = response.headers.get("content-type")
            content_type_lower = (content_type or "").lower()
            title = None
            if content_type_lower.startswith(("text/html", "application/xhtml+xml", "text/xml")):
                title_match = TITLE_RE.search(response.text or "")
                title = " ".join(title_match.group(1).split()) if title_match else None
            html = response.text if content_type_lower.startswith(("text/html", "application/xhtml+xml", "text/xml")) else ""
            document_kind = infer_document_kind(url, content_type)
            if is_probably_document_url(url) or document_kind in {DOCUMENT_KIND_IMAGE, "pdf", "docx", "xlsx"}:
                document_result = extract_local_document_text(response.content, url, content_type)
                if document_result.text:
                    html = compact_document_text(document_result.text, max_chars=12000)
                elif document_result.kind == DOCUMENT_KIND_IMAGE:
                    html = ""
                elif not html:
                    html = ""
            notes = []
            if is_probably_document_url(url) or "pdf" in (content_type or "").lower():
                notes.append("Fetched document-like URL.")
            if document_kind == DOCUMENT_KIND_IMAGE:
                notes.append("Image document detected; enhancement layer will read it with OpenAI.")
            elif document_kind != "unsupported":
                if html:
                    notes.append(f"{document_kind.upper()} text extracted.")
                else:
                    notes.append(f"{document_kind.upper()} text extraction yielded no readable text.")
            result = PageFetchResult(
                url=str(response.url),
                requested_url=url,
                canonical_url=str(response.url),
                final_url=str(response.url),
                status_code=response.status_code,
                content_type=content_type,
                html=html,
                title=title,
                fetch_method="http",
                headers=dict(response.headers),
                js_rendered=False,
                response_bytes=len(response.content or b""),
                retry_count=retry_count,
                elapsed_seconds=round(time.monotonic() - start_time, 4),
                notes=notes,
            )
            if self.settings.fetch_cache:
                self._cache[url] = result.model_copy(deep=True)
            return result
        except Exception as exc:
            self.logger.error("http_fetch_failed", url=url, error=str(exc))
            return PageFetchResult(
                url=url,
                requested_url=url,
                canonical_url=url,
                status_code=None,
                content_type=None,
                html="",
                title=None,
                fetch_method="http",
                headers={},
                js_rendered=False,
                retry_count=retry_count,
                elapsed_seconds=round(time.monotonic() - start_time, 4),
                notes=["HTTP fetch failed: %s" % exc],
            )
