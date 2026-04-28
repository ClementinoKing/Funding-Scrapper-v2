"""Playwright-based fetcher for JavaScript-rendered pages."""

from __future__ import annotations

from typing import Any, Optional

from scraper.config import ScraperSettings
from scraper.schemas import PageFetchResult
from scraper.utils.logging import get_logger


class BrowserFetcher:
    """Lazy Playwright wrapper used as a JS-rendering fallback."""

    def __init__(self, settings: ScraperSettings) -> None:
        self.settings = settings
        self.logger = get_logger(__name__)
        self._playwright = None
        self._browser = None

    def _ensure_browser(self) -> None:
        if self._browser is not None:
            return
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:  # pragma: no cover - depends on runtime install
            raise RuntimeError("Playwright is not available: %s" % exc) from exc

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.settings.headless)

    def close(self) -> None:
        if self._browser is not None:
            self._browser.close()
            self._browser = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None

    @staticmethod
    def _interactive_discovery_sweep(page: Any) -> None:
        selectors = (
            '[role="tab"]',
            '[data-bs-toggle="tab"]',
            '[data-toggle="tab"]',
            '[data-bs-toggle="collapse"]',
            '[data-toggle="collapse"]',
            ".accordion-button",
            ".tabs button",
            ".tabs a",
        )
        for selector in selectors:
            try:
                locator = page.locator(selector)
                count = locator.count()
            except Exception:
                continue
            for index in range(count):
                try:
                    item = locator.nth(index)
                    if not item.is_visible():
                        continue
                    item.scroll_into_view_if_needed(timeout=500)
                    item.click(timeout=1000)
                    page.wait_for_timeout(200)
                except Exception:
                    continue

    @staticmethod
    def _scroll_discovery_sweep(page: Any) -> None:
        try:
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(150)
            page.evaluate("window.scrollTo(0, Math.max(document.body.scrollHeight, document.documentElement.scrollHeight))")
            page.wait_for_timeout(250)
            page.evaluate("window.scrollTo(0, Math.max((document.body.scrollHeight || 0) * 0.5, 0))")
            page.wait_for_timeout(150)
            page.evaluate("window.scrollTo(0, 0)")
        except Exception:
            return

    def fetch(self, url: str) -> PageFetchResult:
        try:
            self._ensure_browser()
            context = self._browser.new_context()
            page = context.new_page()
            response = page.goto(url, wait_until=self.settings.browser_wait_until, timeout=self.settings.timeout_seconds * 1000)
            page.wait_for_timeout(750)
            self._scroll_discovery_sweep(page)
            self._interactive_discovery_sweep(page)
            html = page.content()
            title = page.title()
            final_url = page.url
            status_code = response.status if response else 200
            headers = response.headers if response else {}
            context.close()
            return PageFetchResult(
                url=final_url,
                requested_url=url,
                canonical_url=final_url,
                final_url=final_url,
                status_code=status_code,
                content_type=headers.get("content-type"),
                html=html,
                title=title,
                fetch_method="browser",
                headers=dict(headers),
                js_rendered=True,
                notes=[],
            )
        except Exception as exc:
            self.logger.error("browser_fetch_failed", url=url, error=str(exc))
            return PageFetchResult(
                url=url,
                requested_url=url,
                canonical_url=url,
                status_code=None,
                content_type=None,
                html="",
                title=None,
                fetch_method="browser",
                headers={},
                js_rendered=True,
                notes=["Browser fetch failed: %s" % exc],
            )
