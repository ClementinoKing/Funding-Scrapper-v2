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
from scraper.schemas import PageContentDocument, PageContentSection, PageFetchResult, PageInteractiveSection
from scraper.utils.text import clean_text, unique_preserve_order
from scraper.utils.urls import canonicalize_url, filter_and_sort_links, is_internal_url, looks_irrelevant_url


INLINE_NOISE_TAGS = {"script", "style", "noscript", "svg", "canvas", "iframe", "form", "template", "button"}
BLOCK_NOISE_TAGS = {"nav", "footer", "header", "aside", "dialog"}
INTERACTIVE_TYPE_HINTS = {
    "tab": ("tab", "tabs", "tabpanel", "tab-pane"),
    "accordion": ("accordion", "collapse", "collapsible", "faq", "toggle"),
    "card": ("card", "tile", "panel", "box", "content-box"),
    "table": ("table",),
    "list": ("list", "list-group"),
}
INTERACTIVE_CONTROL_SELECTORS = (
    '[role="tab"]',
    '[role="button"][aria-controls]',
    '[aria-controls]',
    '[data-bs-toggle="tab"]',
    '[data-toggle="tab"]',
    '[data-bs-toggle="collapse"]',
    '[data-toggle="collapse"]',
    '.tabs button',
    '.tabs a',
)
INTERACTIVE_PANEL_SELECTORS = (
    '[role="tabpanel"]',
    '.tab-content',
    '.tab-pane',
    '.accordion',
    '.accordion-item',
    '.accordion-body',
    '.collapse',
    '.card',
    '.panel',
    '.box',
    '.content-box',
    'table',
    'ul',
    'ol',
)


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


def _has_noise_ancestor(node: Tag) -> bool:
    for parent in node.parents:
        if not isinstance(parent, Tag):
            continue
        if parent.name in BLOCK_NOISE_TAGS:
            return True
        if _matches_noise_hint(parent):
            return True
    return False


def _is_layout_noise(node: Tag) -> bool:
    tokens = _node_class_tokens(node)
    if any(hint in tokens for hint in NOISE_CONTAINER_HINTS):
        return True
    text = clean_text(node.get_text(" ", strip=True))
    if node.name == "li" and len(text) < 120 and len(node.find_all("a")) > 1:
        return True
    return False


def _node_class_tokens(node: Tag) -> str:
    attrs = getattr(node, "attrs", None)
    if not attrs:
        return ""
    class_name = " ".join(attrs.get("class", []))
    id_name = str(attrs.get("id", ""))
    return f"{class_name} {id_name}".lower()


def _attr_text(node: Tag, attribute: str) -> str:
    value = node.get(attribute, "")
    if isinstance(value, (list, tuple, set)):
        value = " ".join(str(item) for item in value)
    return clean_text(str(value))


def _closest_heading_text(node: Tag) -> str:
    for sibling in node.previous_siblings:
        if isinstance(sibling, Tag) and _is_heading_tag(sibling):
            text = clean_text(sibling.get_text(" ", strip=True))
            if text:
                return text
        if isinstance(sibling, Tag) and sibling.name in {"p", "div", "section"}:
            heading = sibling.find(re.compile(r"^h[1-4]$"))
            if heading:
                text = clean_text(heading.get_text(" ", strip=True))
                if text:
                    return text
    parent = node.parent if isinstance(node.parent, Tag) else None
    if parent:
        heading = parent.find(re.compile(r"^h[1-4]$"))
        if heading and heading is not node:
            text = clean_text(heading.get_text(" ", strip=True))
            if text:
                return text
        caption = parent.find("caption")
        if caption:
            text = clean_text(caption.get_text(" ", strip=True))
            if text:
                return text
    return ""


def _extract_node_label(node: Tag) -> str:
    for attribute in ("aria-label", "title", "data-title", "data-label"):
        value = _attr_text(node, attribute)
        if value:
            return value
    text = clean_text(node.get_text(" ", strip=True))
    if text:
        return text
    return _closest_heading_text(node)


def _interactive_type_for_node(node: Tag) -> str:
    tokens = _node_class_tokens(node)
    role = _attr_text(node, "role").lower()
    if node.name == "table":
        return "table"
    if node.name in {"ul", "ol"}:
        return "list"
    if role in {"tab", "tabpanel"} or any(token in tokens for token in INTERACTIVE_TYPE_HINTS["tab"]):
        return "tab"
    if any(token in tokens for token in INTERACTIVE_TYPE_HINTS["accordion"]) or node.get("data-bs-toggle") == "collapse" or node.get("data-toggle") == "collapse":
        return "accordion"
    if any(token in tokens for token in INTERACTIVE_TYPE_HINTS["card"]):
        return "card"
    if any(token in tokens for token in INTERACTIVE_TYPE_HINTS["table"]):
        return "table"
    if any(token in tokens for token in INTERACTIVE_TYPE_HINTS["list"]):
        return "list"
    return "interactive"


def _target_ids_from_trigger(node: Tag) -> List[str]:
    targets: List[str] = []
    for attribute in ("aria-controls", "data-target", "data-bs-target", "href"):
        raw_value = _attr_text(node, attribute)
        if not raw_value:
            continue
        values = [raw_value]
        if attribute == "href" and raw_value.startswith("#"):
            values = [raw_value[1:]]
        for value in values:
            cleaned = value.lstrip("#").strip()
            if cleaned and cleaned not in targets:
                targets.append(cleaned)
    return targets


def _find_target_node(root: BeautifulSoup | Tag, trigger: Tag) -> Optional[Tag]:
    for target_id in _target_ids_from_trigger(trigger):
        match = root.find(id=target_id)
        if isinstance(match, Tag):
            return match
    if _attr_text(trigger, "role") == "tab":
        parent = trigger.parent if isinstance(trigger.parent, Tag) else None
        if parent:
            panel = parent.find(attrs={"role": "tabpanel"})
            if isinstance(panel, Tag):
                return panel
            tab_content = parent.find(class_=re.compile(r"(?:^|\s)tab-content(?:\s|$)", re.I))
            if isinstance(tab_content, Tag):
                panel = tab_content.find(attrs={"role": "tabpanel"})
                if isinstance(panel, Tag):
                    return panel
    if trigger.get("data-bs-toggle") == "collapse" or trigger.get("data-toggle") == "collapse":
        parent = trigger.parent if isinstance(trigger.parent, Tag) else None
        if parent:
            panel = parent.find(class_=re.compile(r"(?:^|\s)collapse(?:\s|$)", re.I))
            if isinstance(panel, Tag):
                return panel
    return None


def _extract_interactive_sections(root: BeautifulSoup) -> List[PageInteractiveSection]:
    sections: List[PageInteractiveSection] = []
    seen: set[tuple[str, str, str]] = set()
    controls = []
    for selector in INTERACTIVE_CONTROL_SELECTORS:
        try:
            controls.extend(root.select(selector))
        except Exception:
            continue
    for node in controls:
        if not isinstance(node, Tag) or _has_noise_ancestor(node) or _is_layout_noise(node):
            continue
        section_type = _interactive_type_for_node(node)
        target = _find_target_node(root, node) or node
        label = _extract_node_label(node)
        if not label:
            label = _closest_heading_text(target)
        content = _extract_text(target)
        if not content or len(content) < 30:
            continue
        signature = (section_type, label.casefold(), content[:240].casefold())
        if signature in seen:
            continue
        seen.add(signature)
        sections.append(PageInteractiveSection(type=section_type, label=label, content=content))

    panel_candidates = []
    for selector in INTERACTIVE_PANEL_SELECTORS:
        try:
            panel_candidates.extend(root.select(selector))
        except Exception:
            continue
    for node in panel_candidates:
        if not isinstance(node, Tag) or _has_noise_ancestor(node) or _is_layout_noise(node):
            continue
        section_type = _interactive_type_for_node(node)
        label = _extract_node_label(node) or _closest_heading_text(node)
        content = _extract_text(node)
        if not content or len(content) < 40:
            continue
        if section_type == "list" and len(node.find_all("li")) < 2:
            continue
        signature = (section_type, label.casefold(), content[:240].casefold())
        if signature in seen:
            continue
        seen.add(signature)
        sections.append(PageInteractiveSection(type=section_type, label=label, content=content))

    return sections


def _interactive_sections_text(interactive_sections: Sequence[PageInteractiveSection]) -> str:
    parts: List[str] = []
    for section in interactive_sections:
        if section.label:
            parts.append(section.label)
        if section.content:
            parts.append(section.content)
    return _dedupe_lines("\n".join(parts))


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


def _remove_duplicate_interactive_sections(sections: List[PageInteractiveSection]) -> List[PageInteractiveSection]:
    seen = set()
    deduped: List[PageInteractiveSection] = []
    for section in sections:
        key = (section.type.casefold(), section.label.casefold(), section.content.casefold())
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
                source_content_type=page.content_type,
                source_domain=urlparse(page.canonical_url).netloc.lower(),
            )

        soup = BeautifulSoup(page.html, "html.parser")
        profile = adapter.extraction_profile() if adapter else None
        scoped_root, main_content_hint = _select_content_root(
            soup,
            profile.content_scope_selectors if profile else (),
        )
        interactive_sections = _remove_duplicate_interactive_sections(_extract_interactive_sections(scoped_root))
        cleaned_root = _strip_noise(scoped_root, profile.content_exclude_selectors if profile else ())
        title = _title_from_page(soup, page.title)
        headings = _collect_headings(cleaned_root)
        structured_sections = _remove_duplicate_sections(_collect_sections(cleaned_root))
        full_body_text = _extract_text(cleaned_root)
        page_domain = urlparse(page.canonical_url).netloc.lower()
        document_context_text = " ".join(
            [
                title or "",
                page.title or "",
                " ".join(headings[:8]),
                page.canonical_url,
            ]
        )

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
        document_links = extract_document_links(cleaned_root, page.canonical_url, context_text=document_context_text)
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
            source_content_type=page.content_type,
            headings=headings,
            full_body_text=full_body_text,
            structured_sections=structured_sections,
            interactive_sections=interactive_sections,
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
