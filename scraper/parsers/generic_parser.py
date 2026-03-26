"""Generic page parser for funding programme extraction."""

from __future__ import annotations

import warnings
from typing import List, Optional, Sequence

from bs4 import BeautifulSoup
try:
    from bs4 import XMLParsedAsHTMLWarning
except Exception:  # pragma: no cover - older bs4 versions
    XMLParsedAsHTMLWarning = None
from selectolax.parser import HTMLParser

from scraper.config import ScraperSettings
from scraper.adapters.base import SiteAdapter
from scraper.parsers.extractor_rules import (
    CandidateBlock,
    collect_anchor_candidates,
    collect_internal_anchor_candidates,
    extract_application_links,
    extract_candidate_blocks,
    extract_document_links,
    looks_like_programme_heading,
    group_sections_from_soup,
)
from scraper.parsers.normalization import build_programme_record, classify_page_type
from scraper.schemas import ExtractionResult, PageFetchResult
from scraper.utils.text import clean_text
from scraper.utils.urls import filter_and_sort_links


if XMLParsedAsHTMLWarning is not None:
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


class GenericFundingParser:
    """Parse static HTML into one or more candidate funding programme records."""

    def __init__(self, settings: ScraperSettings) -> None:
        self.settings = settings

    def parse(
        self,
        page: PageFetchResult,
        allowed_domains: Sequence[str],
        adapter: Optional[SiteAdapter] = None,
    ) -> ExtractionResult:
        if not page.html:
            return ExtractionResult(page_url=page.canonical_url, page_title=page.title, warnings=["Empty HTML payload."])

        tree = HTMLParser(page.html)
        soup = BeautifulSoup(page.html, "html.parser")
        page_title = page.title or (clean_text(tree.css_first("title").text()) if tree.css_first("title") else None)
        page_text = clean_text(soup.get_text(" ", strip=True))
        if adapter and adapter.content_selectors:
            scoped_text_parts = []
            for selector in adapter.content_selectors:
                for node in soup.select(selector):
                    scoped_text_parts.append(clean_text(node.get_text(" ", strip=True)))
            scoped_text = clean_text(" ".join(scoped_text_parts))
            if scoped_text:
                page_text = scoped_text

        all_links = collect_anchor_candidates(soup, page.canonical_url)
        internal_links = collect_internal_anchor_candidates(soup, page.canonical_url, allowed_domains)
        discovered_links = filter_and_sort_links(
            all_links,
            base_url=page.canonical_url,
            allowed_domains=allowed_domains,
            relevant_keywords=self.settings.relevant_keywords,
            irrelevant_patterns=self.settings.irrelevant_url_patterns,
        )
        document_links = extract_document_links(soup, page.canonical_url)
        page_application_links = [
            link for link in extract_application_links(soup, page.canonical_url) if link not in document_links
        ]
        discovered_links = [link for link in discovered_links if link not in page_application_links]

        candidate_blocks = extract_candidate_blocks(
            soup,
            page.canonical_url,
            self.settings.relevant_keywords,
            candidate_selectors=adapter.candidate_selectors if adapter else (),
        )
        notes: List[str] = []
        warnings: List[str] = []
        if not candidate_blocks:
            if len(page_text) < 120 and not looks_like_programme_heading(page_title or page_text):
                notes.append("Skipped low-information page fallback.")
                return ExtractionResult(
                    page_url=page.canonical_url,
                    page_title=page_title,
                    discovered_links=discovered_links,
                    internal_links=list(dict.fromkeys([href for href, _label in internal_links] + discovered_links)),
                    application_links=page_application_links,
                    document_links=document_links,
                    records=[],
                    evidence=[],
                    page_type="support",
                    notes=notes,
                    warnings=warnings,
                )
            candidate_blocks = [
                CandidateBlock(
                    heading=page_title or "",
                    text=page_text,
                    source_url=page.canonical_url,
                    section_map=group_sections_from_soup(soup),
                    detail_links=[],
                    application_links=page_application_links,
                    document_links=document_links,
                )
            ]
            notes.append("Used whole-page fallback block.")

        records = []
        evidence = []
        for block in candidate_blocks:
            block.document_links = list(dict.fromkeys(block.document_links))
            block.application_links = list(dict.fromkeys(block.application_links))
            if len(candidate_blocks) == 1 and not block.document_links:
                block.document_links = document_links
            if len(candidate_blocks) == 1 and not block.application_links:
                block.application_links = page_application_links
            record, record_evidence = build_programme_record(
                block=block,
                page_url=page.canonical_url,
                page_title=page_title,
                settings=self.settings,
            )
            if record:
                records.append(record)
                evidence.extend(record_evidence)
            else:
                warnings.append("Skipped a low-information block on %s." % page.canonical_url)

        for block in candidate_blocks:
            discovered_links.extend(block.detail_links)
        discovered_links = list(dict.fromkeys(discovered_links))
        internal_links = list(dict.fromkeys([href for href, _label in internal_links] + discovered_links + document_links))
        internal_links = [link for link in internal_links if link not in page_application_links]

        detail_link_count = sum(len(block.detail_links) for block in candidate_blocks)
        application_link_count = sum(len(block.application_links) for block in candidate_blocks)
        document_link_count = len(document_links)
        page_type = classify_page_type(
            record_count=len(records),
            candidate_block_count=len(candidate_blocks),
            internal_link_count=len(internal_links),
            detail_link_count=detail_link_count,
            application_link_count=application_link_count,
            document_link_count=document_link_count,
            text=page_text,
        )
        if adapter:
            page_type = adapter.page_role(
                page_url=page.canonical_url,
                page_title=page_title,
                text=page_text,
                record_count=len(records),
                candidate_block_count=len(candidate_blocks),
                internal_link_count=len(internal_links),
                detail_link_count=detail_link_count,
                application_link_count=application_link_count,
                document_link_count=document_link_count,
            )

        return ExtractionResult(
            page_url=page.canonical_url,
            page_title=page_title,
            discovered_links=discovered_links,
            internal_links=internal_links,
            application_links=page_application_links,
            document_links=document_links,
            records=records,
            evidence=evidence,
            page_type=page_type,
            notes=notes,
            warnings=warnings,
        )
