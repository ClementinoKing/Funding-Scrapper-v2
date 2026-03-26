"""Reusable parsing heuristics and candidate block extraction rules."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Sequence, Tuple
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from scraper.utils.text import clean_text, split_lines, unique_preserve_order
from scraper.utils.urls import canonicalize_url, is_internal_url, is_probably_document_url


PROGRAM_HEADING_HINTS = [
    "fund",
    "grant",
    "loan",
    "finance",
    "facility",
    "scheme",
    "programme",
    "program",
    "support",
]

APPLICATION_HINTS = ["apply", "application", "register", "submit", "online form"]
NOISE_CONTAINER_TAGS = {"nav", "aside", "footer", "header"}
NOISE_CONTAINER_HINTS = (
    "menu",
    "sidebar",
    "footer",
    "header",
    "nav",
    "breadcrumb",
    "toolbar",
    "masthead",
    "site-nav",
)
SECTION_KEYWORDS: Dict[str, Sequence[str]] = {
    "eligibility": ["eligibility", "who can apply", "criteria", "requirements", "qualifying criteria"],
    "documents": ["documents", "documentation", "required documents", "supporting documents"],
    "exclusions": ["exclusions", "not eligible", "who cannot apply", "not supported"],
    "funding": ["funding", "loan size", "grant size", "offer", "funding products", "facilities"],
    "application": ["apply", "application", "how to apply", "application process"],
    "timing": ["deadline", "closing date", "turnaround time", "processing time"],
}
ARCHIVE_TERMS = ["archived", "archive", "applications closed", "closed for applications", "expired"]
GENERIC_SECTION_HEADINGS = {
    "eligibility",
    "funding",
    "funding offer",
    "funding details",
    "funding offer details",
    "apply",
    "application",
    "how to apply",
    "timing",
    "geography",
    "required documents",
    "documents",
    "contact",
}


@dataclass
class CandidateBlock:
    heading: str
    text: str
    source_url: str
    section_map: Dict[str, List[str]] = field(default_factory=dict)
    detail_links: List[str] = field(default_factory=list)
    application_links: List[str] = field(default_factory=list)
    document_links: List[str] = field(default_factory=list)


def looks_like_programme_heading(text: str) -> bool:
    lowered = clean_text(text).lower()
    if not lowered or len(lowered) < 4:
        return False
    return any(keyword in lowered for keyword in PROGRAM_HEADING_HINTS)


def detect_archive_signals(text: str) -> List[str]:
    lowered = (text or "").lower()
    return [term for term in ARCHIVE_TERMS if term in lowered]


def collect_anchor_candidates(soup: BeautifulSoup, base_url: str) -> List[Tuple[str, str]]:
    candidates: List[Tuple[str, str]] = []
    for anchor in soup.find_all("a", href=True):
        href = canonicalize_url(anchor["href"], base_url=base_url)
        label = clean_text(anchor.get_text(" ", strip=True))
        if href:
            candidates.append((href, label))
    return candidates


def collect_internal_anchor_candidates(
    soup: BeautifulSoup,
    base_url: str,
    allowed_domains: Sequence[str],
) -> List[Tuple[str, str]]:
    candidates: List[Tuple[str, str]] = []
    for href, label in collect_anchor_candidates(soup, base_url):
        if is_internal_url(href, allowed_domains):
            candidates.append((href, label))
    return candidates


def _has_noise_ancestor(node: Tag) -> bool:
    for parent in node.parents:
        if not isinstance(parent, Tag):
            continue
        if parent.name in NOISE_CONTAINER_TAGS:
            return True
        class_name = " ".join(parent.get("class", [])) if hasattr(parent, "get") else ""
        id_name = str(parent.get("id", "")) if hasattr(parent, "get") else ""
        combined = f"{class_name} {id_name}".lower()
        if any(hint in combined for hint in NOISE_CONTAINER_HINTS):
            return True
    return False


def _is_layout_noise(node: Tag) -> bool:
    class_name = " ".join(node.get("class", [])) if hasattr(node, "get") else ""
    id_name = str(node.get("id", "")) if hasattr(node, "get") else ""
    combined = f"{class_name} {id_name}".lower()
    if any(hint in combined for hint in NOISE_CONTAINER_HINTS):
        return True
    text = clean_text(node.get_text(" ", strip=True))
    if node.name == "li" and len(text) < 120 and len(node.find_all("a")) > 1:
        return True
    return False


def extract_document_links(soup: BeautifulSoup, base_url: str) -> List[str]:
    documents: List[str] = []
    for anchor in soup.find_all("a", href=True):
        if _has_noise_ancestor(anchor):
            continue
        href = canonicalize_url(anchor["href"], base_url=base_url)
        label = clean_text(anchor.get_text(" ", strip=True)).lower()
        if is_probably_document_url(href) or any(term in label for term in ["pdf", "application form", "download"]):
            documents.append(href)
    return unique_preserve_order(documents)


def extract_application_links(soup: BeautifulSoup, base_url: str) -> List[str]:
    links: List[str] = []
    for anchor in soup.find_all("a", href=True):
        label = clean_text(anchor.get_text(" ", strip=True)).lower()
        href = canonicalize_url(anchor["href"], base_url=base_url)
        if any(keyword in label for keyword in APPLICATION_HINTS) or any(keyword in href.lower() for keyword in APPLICATION_HINTS):
            links.append(href)
    return unique_preserve_order(links)


def _extract_text_items(node: Tag, limit: int = 18) -> List[str]:
    items: List[str] = []
    for child in node.find_all(["p", "li", "td", "th", "dd", "dt"], recursive=True):
        text = clean_text(child.get_text(" ", strip=True))
        if text:
            items.append(text)
        if len(items) >= limit:
            break
    if not items:
        items = split_lines(node.get_text("\n", strip=True))
    return unique_preserve_order(items[:limit])


def group_sections_from_soup(soup: BeautifulSoup) -> Dict[str, List[str]]:
    sections: Dict[str, List[str]] = {}
    headings = soup.find_all(re.compile(r"^h[1-4]$"))
    for heading in headings:
        title = clean_text(heading.get_text(" ", strip=True))
        if not title:
            continue
        collected: List[str] = []
        for sibling in heading.next_siblings:
            if isinstance(sibling, Tag) and sibling.name and re.match(r"^h[1-4]$", sibling.name):
                break
            if isinstance(sibling, Tag):
                collected.extend(_extract_text_items(sibling, limit=10))
            if len(collected) >= 12:
                break
        if collected:
            sections[title] = unique_preserve_order(collected[:12])
    return sections


def extract_candidate_blocks(
    soup: BeautifulSoup,
    base_url: str,
    relevant_keywords: Sequence[str],
    candidate_selectors: Sequence[str] = (),
) -> List[CandidateBlock]:
    candidates: List[CandidateBlock] = []
    seen = set()
    selector_selected_nodes = set()
    candidate_nodes = []
    for selector in candidate_selectors:
        for node in soup.select(selector):
            if _has_noise_ancestor(node) or _is_layout_noise(node):
                continue
            node_id = id(node)
            if node_id in selector_selected_nodes:
                continue
            selector_selected_nodes.add(node_id)
            candidate_nodes.append(node)
    candidate_nodes.extend(soup.find_all(["article", "section", "li", "div"]))
    for node in candidate_nodes:
        if _has_noise_ancestor(node) or _is_layout_noise(node):
            continue
        class_name = " ".join(node.get("class", [])) if hasattr(node, "get") else ""
        class_hint = any(hint in class_name.lower() for hint in ["card", "panel", "tile", "accordion", "content"])
        if node.name == "div" and not class_hint and id(node) not in selector_selected_nodes:
            continue
        heading_node = node.find(["h1", "h2", "h3", "h4", "strong", "b"])
        heading = clean_text(heading_node.get_text(" ", strip=True)) if heading_node else ""
        text = clean_text(node.get_text(" ", strip=True))
        if heading and heading.lower() in GENERIC_SECTION_HEADINGS:
            continue
        if node.name == "section" and not class_hint and not looks_like_programme_heading(heading):
            continue
        if len(text) < 40 or len(text) > 3500:
            continue
        lowered = text.lower()
        keyword_hits = sum(1 for keyword in relevant_keywords if keyword.lower() in lowered)
        if keyword_hits == 0 and not looks_like_programme_heading(heading) and len(text) < 120:
            continue
        signature = text[:180].lower()
        if signature in seen:
            continue
        seen.add(signature)

        node_soup = BeautifulSoup(str(node), "html.parser")
        detail_links = []
        application_links = []
        for href, label in collect_anchor_candidates(node_soup, base_url):
            if any(term in label.lower() for term in APPLICATION_HINTS):
                application_links.append(href)
            else:
                detail_links.append(href)

        candidates.append(
            CandidateBlock(
                heading=heading,
                text=text,
                source_url=base_url,
                section_map=group_sections_from_soup(node_soup),
                detail_links=unique_preserve_order(detail_links),
                application_links=extract_application_links(node_soup, base_url) or unique_preserve_order(application_links),
                document_links=extract_document_links(node_soup, base_url),
            )
        )
    return candidates


def find_section_values(section_map: Dict[str, List[str]], section_name: str) -> List[str]:
    keywords = SECTION_KEYWORDS.get(section_name, [])
    matches: List[str] = []
    for heading, values in section_map.items():
        lowered = heading.lower()
        if any(keyword in lowered for keyword in keywords):
            matches.extend(values)
    return unique_preserve_order(matches)
