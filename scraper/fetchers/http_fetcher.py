"""Primary HTTP fetcher with retry, throttling support hooks, and robots checks."""

from __future__ import annotations

import random
import re
from typing import Dict, Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from scraper.config import ScraperSettings
from scraper.schemas import PageFetchResult
from scraper.utils.logging import get_logger
from scraper.utils.pdf import extract_pdf_text
from scraper.utils.urls import is_probably_document_url


TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)


class HttpFetcher:
    """HTTP client wrapper for resilient HTML retrieval."""

    def __init__(self, settings: ScraperSettings) -> None:
        self.settings = settings
        self.logger = get_logger(__name__)
        self.client = httpx.Client(timeout=settings.timeout_seconds, follow_redirects=True)
        self.robots_cache: Dict[str, RobotFileParser] = {}

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
        if not self.can_fetch(url):
            return PageFetchResult(
                url=url,
                requested_url=url,
                canonical_url=url,
                status_code=None,
                html="",
                title=None,
                fetch_method="http",
                notes=["Blocked by robots.txt"],
            )

        headers = self._headers()
        response: Optional[httpx.Response] = None
        try:
            for attempt in Retrying(
                stop=stop_after_attempt(self.settings.retries),
                wait=wait_exponential(multiplier=1, min=1, max=8),
                retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException)),
                reraise=True,
            ):
                with attempt:
                    response = self.client.get(url, headers=headers)
            assert response is not None
            title_match = TITLE_RE.search(response.text or "")
            title = " ".join(title_match.group(1).split()) if title_match else None
            content_type = response.headers.get("content-type")
            content_type_lower = (content_type or "").lower()
            html = response.text if content_type_lower.startswith(("text/html", "application/xhtml+xml", "text/xml")) else ""
            if content_type_lower.startswith("application/pdf") or is_probably_document_url(url):
                extracted_text = extract_pdf_text(response.content)
                if extracted_text:
                    html = extracted_text
                elif not html:
                    html = ""
            notes = []
            if is_probably_document_url(url) or "pdf" in (content_type or "").lower():
                notes.append("Fetched document-like URL.")
            if content_type_lower.startswith("application/pdf"):
                if html:
                    notes.append("PDF text extracted.")
                else:
                    notes.append("PDF text extraction yielded no readable text.")
            return PageFetchResult(
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
                notes=notes,
            )
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
                notes=["HTTP fetch failed: %s" % exc],
            )
