"""Generic page-content extractor for AI-first funding programme scraping."""

from __future__ import annotations

import re
from typing import List, Optional, Sequence, Tuple
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from scraper.adapters.base import SiteAdapter
from scraper.config import ScraperSettings
from scraper.parsers.extractor_rules import (
    APPLICATION_HINTS,
    NOISE_CONTAINER_HINTS,
    collect_anchor_candidates,
    extract_application_links,
    extract_document_links,
)
from scraper.schemas import PageContentDocument, PageContentSection, PageFetchResult
from scraper.utils.text import clean_text, unique_preserve_order
from scraper.utils.urls import canonicalize_url, filter_and_sort_links, is_internal_url, looks_irrelevant_url


INLINE_NOISE_TAGS = {"script", "style", "noscript", "svg", "canvas", "iframe", "form", "template", "button"}
BLOCK_NOISE_TAGS = {"nav", "footer", "header", "aside", "dialog"}


def _is_heading_tag(node: Tag) -> bool:
    return bool(node.name and re.match(r"^h[1-3]$", node.name))


def _heading_level(node: Tag) -> int:
    if not node.name:
        return 1
    match = re.match(r"^h([1-3])$", node.name)
    return int(match.group(1)) if match else 1


def _matches_noise_hint(node: Tag) -> bool:
    attrs = getattr(node, "attrs", None)
    if not attrs:
        return False
    class_name = " ".join(attrs.get("class", []))
    id_name = str(attrs.get("id", ""))
    combined = f"{class_name} {id_name}".lower()
    return any(hint in combined for hint in NOISE_CONTAINER_HINTS)


def _clone_soup(node: Tag | BeautifulSoup) -> BeautifulSoup:
    return BeautifulSoup(str(node), "html.parser")


def _dedupe_lines(text: str) -> str:
    lines = [clean_text(line) for line in (text or "").splitlines()]
    filtered = [line for line in lines if line and len(line) > 1]
    return "\n".join(unique_preserve_order(filtered))


def _extract_text(node: Tag | BeautifulSoup) -> str:
    parts: List[str] = []
    if node is None:
        return ""
    for child in node.descendants:
        if isinstance(child, Tag) and child.name in INLINE_NOISE_TAGS:
            continue
        if isinstance(child, Tag) and child.name in {"br", "hr"}:
            parts.append("\n")
            continue
        if isinstance(child, Tag) and child.name in {"p", "li", "dt", "dd", "th", "td", "blockquote"}:
            text = clean_text(child.get_text(" ", strip=True))
            if text:
                parts.append(text)
                parts.append("\n")
    if not parts:
        text = node.get_text("\n", strip=True) if hasattr(node, "get_text") else ""
        return _dedupe_lines(text)
    return _dedupe_lines("\n".join(parts))


def _select_content_root(soup: BeautifulSoup, selectors: Sequence[str]) -> Tuple[BeautifulSoup, Optional[str]]:
    if not selectors:
        return soup, None
    for selector in selectors:
        try:
            match = soup.select_one(selector)
        except Exception:
            continue
        if match is not None:
            return _clone_soup(match), selector
    return soup, None


def _strip_noise(root: BeautifulSoup, exclude_selectors: Sequence[str]) -> BeautifulSoup:
    clone = _clone_soup(root)
    for selector in exclude_selectors:
        try:
            for node in clone.select(selector):
                node.decompose()
        except Exception:
            continue
    for node in list(clone.find_all(True)):
        if node.name in INLINE_NOISE_TAGS or node.name in BLOCK_NOISE_TAGS:
            node.decompose()
            continue
        if _matches_noise_hint(node):
            node.decompose()
    return clone


def _title_from_page(soup: BeautifulSoup, fallback: Optional[str]) -> Optional[str]:
    title = clean_text(soup.title.get_text(" ", strip=True)) if soup.title else ""
    if title:
        return title
    if fallback:
        return clean_text(fallback) or None
    h1 = soup.find("h1")
    return clean_text(h1.get_text(" ", strip=True)) if h1 else None


def _collect_headings(root: BeautifulSoup) -> List[str]:
    headings: List[str] = []
    for tag in root.find_all(re.compile(r"^h[1-3]$")):
        text = clean_text(tag.get_text(" ", strip=True))
        if text:
            headings.append(text)
    return unique_preserve_order(headings)


def _collect_sections(root: BeautifulSoup) -> List[PageContentSection]:
    sections: List[PageContentSection] = []
    headings = list(root.find_all(re.compile(r"^h[1-3]$")))
    for index, heading in enumerate(headings):
        heading_text = clean_text(heading.get_text(" ", strip=True))
        if not heading_text:
            continue
        content_parts: List[str] = []
        for sibling in heading.next_siblings:
            if isinstance(sibling, Tag) and _is_heading_tag(sibling):
                break
            if isinstance(sibling, Tag):
                text = _extract_text(sibling)
                if text:
                    content_parts.append(text)
            elif isinstance(sibling, str):
                text = clean_text(sibling)
                if text:
                    content_parts.append(text)
        content = clean_text(" ".join(content_parts))
        if content:
            sections.append(PageContentSection(heading=heading_text, content=content))
    return sections


def _remove_duplicate_sections(sections: List[PageContentSection]) -> List[PageContentSection]:
    seen = set()
    deduped: List[PageContentSection] = []
    for section in sections:
        key = (section.heading.casefold(), section.content.casefold())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(section)
    return deduped


class GenericFundingParser:
    """Extract clean, semantically ordered page content for the AI layer."""

    def __init__(self, settings: ScraperSettings) -> None:
        self.settings = settings

    def extract(
        self,
        page: PageFetchResult,
        allowed_domains: Sequence[str],
        adapter: Optional[SiteAdapter] = None,
    ) -> PageContentDocument:
        if not page.html:
            return PageContentDocument(
                page_url=page.canonical_url,
                title=page.title,
                page_title=page.title,
                source_domain=urlparse(page.canonical_url).netloc.lower(),
            )

        soup = BeautifulSoup(page.html, "html.parser")
        profile = adapter.extraction_profile() if adapter else None
        scoped_root, main_content_hint = _select_content_root(
            soup,
            profile.content_scope_selectors if profile else (),
        )
        cleaned_root = _strip_noise(scoped_root, profile.content_exclude_selectors if profile else ())
        title = _title_from_page(soup, page.title)
        headings = _collect_headings(cleaned_root)
        structured_sections = _remove_duplicate_sections(_collect_sections(cleaned_root))
        full_body_text = _extract_text(cleaned_root)
        page_domain = urlparse(page.canonical_url).netloc.lower()

        all_links = collect_anchor_candidates(soup, page.canonical_url)
        internal_links = [
            href
            for href, _label in all_links
            if is_internal_url(href, allowed_domains) and not looks_irrelevant_url(href, self.settings.irrelevant_url_patterns)
        ]
        discovered_links = filter_and_sort_links(
            all_links,
            base_url=page.canonical_url,
            allowed_domains=allowed_domains,
            relevant_keywords=self.settings.relevant_keywords,
            irrelevant_patterns=self.settings.irrelevant_url_patterns,
        )
        document_links = extract_document_links(cleaned_root, page.canonical_url)
        application_links = [
            link for link in extract_application_links(cleaned_root, page.canonical_url) if link not in document_links
        ]
        internal_links = [link for link in internal_links if link not in application_links and link not in document_links]
        discovered_links = [link for link in discovered_links if link not in application_links and link not in document_links]
        internal_links = unique_preserve_order([*internal_links, *discovered_links, *document_links])

        return PageContentDocument(
            page_url=page.canonical_url,
            title=title,
            page_title=title,
            headings=headings,
            full_body_text=full_body_text,
            structured_sections=structured_sections,
            discovered_links=discovered_links,
            internal_links=internal_links,
            application_links=application_links,
            document_links=document_links,
            main_content_hint=main_content_hint,
            source_domain=page_domain,
        )

    def parse(
        self,
        page: PageFetchResult,
        allowed_domains: Sequence[str],
        adapter: Optional[SiteAdapter] = None,
    ) -> PageContentDocument:
        return self.extract(page, allowed_domains=allowed_domains, adapter=adapter)
