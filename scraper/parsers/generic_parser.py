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
    build_scoped_soup,
    build_section_bundle,
    build_section_tree_from_soup,
    collect_anchor_candidates,
    collect_internal_anchor_candidates,
    extract_application_links,
    extract_candidate_blocks,
    extract_document_links,
    looks_like_programme_heading,
    group_sections_from_soup,
)
from scraper.parsers.normalization import build_programme_record, classify_page_type
from scraper.schemas import ExtractionResult, PageDebugPackage, PageFetchResult, PageDebugRecord
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
        profile = adapter.extraction_profile() if adapter else None
        page_title = page.title or (clean_text(tree.css_first("title").text()) if tree.css_first("title") else None)
        scoped_soup = build_scoped_soup(
            soup,
            include_selectors=profile.content_scope_selectors if profile else (),
            exclude_selectors=profile.content_exclude_selectors if profile else (),
        )
        page_text = clean_text(scoped_soup.get_text(" ", strip=True)) or clean_text(soup.get_text(" ", strip=True))

        all_links = collect_anchor_candidates(soup, page.canonical_url)
        internal_links = collect_internal_anchor_candidates(soup, page.canonical_url, allowed_domains)
        discovered_links = filter_and_sort_links(
            all_links,
            base_url=page.canonical_url,
            allowed_domains=allowed_domains,
            relevant_keywords=self.settings.relevant_keywords,
            irrelevant_patterns=self.settings.irrelevant_url_patterns,
        )
        document_links = extract_document_links(scoped_soup, page.canonical_url)
        page_application_links = [
            link for link in extract_application_links(scoped_soup, page.canonical_url) if link not in document_links
        ]
        discovered_links = [link for link in discovered_links if link not in page_application_links]

        candidate_blocks = extract_candidate_blocks(
            scoped_soup,
            page.canonical_url,
            self.settings.relevant_keywords,
            candidate_selectors=profile.candidate_selectors if profile else (),
            section_heading_selectors=profile.section_heading_selectors if profile else (),
            section_aliases=profile.section_aliases if profile else None,
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
                    section_map=group_sections_from_soup(
                        scoped_soup,
                        heading_selectors=profile.section_heading_selectors if profile else (),
                    ),
                    section_tree=build_section_tree_from_soup(
                        scoped_soup,
                        heading_selectors=profile.section_heading_selectors if profile else (),
                        source_url=page.canonical_url,
                    ),
                    section_bundle=build_section_bundle(
                        group_sections_from_soup(
                            scoped_soup,
                            heading_selectors=profile.section_heading_selectors if profile else (),
                        ),
                        section_aliases=profile.section_aliases if profile else None,
                    ),
                    section_aliases=dict(profile.section_aliases) if profile else {},
                    detail_links=[],
                    application_links=page_application_links,
                    document_links=document_links,
                )
            ]
            notes.append("Used whole-page fallback block.")

        records = []
        evidence = []
        record_packages = []
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
                if record.page_debug_package:
                    record_packages.append(record.page_debug_package)
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

        combined_evidence_map = {}
        for item in evidence:
            combined_evidence_map.setdefault(item.field_name, []).append(item)
        combined_confidence_map = {
            field_name: max((item.confidence for item in items), default=0.0)
            for field_name, items in combined_evidence_map.items()
        }
        combined_records = []
        for package in record_packages:
            combined_records.extend(package.records)
        if not combined_records and records:
            combined_records = [
                PageDebugRecord(
                    program_name=record.program_name,
                    parent_programme_name=record.parent_programme_name,
                    source_scope=record.source_scope,
                    evidence_map=record.field_evidence,
                    confidence_map=record.field_confidence,
                    notes=record.notes,
                )
                for record in records
            ]
        page_debug_package = PageDebugPackage(
            page_url=page.canonical_url,
            final_url=page.final_url or page.canonical_url,
            page_title=page_title,
            cleaned_text=page_text,
            section_tree=candidate_blocks[0].section_tree if candidate_blocks else [],
            extracted_evidence_map=combined_evidence_map,
            confidence_map=combined_confidence_map,
            records=combined_records,
        )

        return ExtractionResult(
            page_url=page.canonical_url,
            page_title=page_title,
            cleaned_text=page_text,
            section_tree=candidate_blocks[0].section_tree if candidate_blocks else [],
            discovered_links=discovered_links,
            internal_links=internal_links,
            application_links=page_application_links,
            document_links=document_links,
            records=records,
            evidence=evidence,
            page_debug_package=page_debug_package,
            page_type=page_type,
            notes=notes,
            warnings=warnings,
        )
