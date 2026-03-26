"""Core site adapter contract used by the shared scraper engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

from scraper.schemas import FundingProgrammeRecord, PageFetchResult
from scraper.utils.text import clean_text, unique_preserve_order
from scraper.utils.urls import extract_domain
from scraper.parsers.normalization import classify_page_type


def _contains_any(haystack: str, terms: Sequence[str]) -> bool:
    lowered = (haystack or "").lower()
    return any(term.lower() in lowered for term in terms)


def _path_matches_prefix(path: str, prefix: str) -> bool:
    normalized_path = (path or "").rstrip("/").lower()
    normalized_prefix = (prefix or "").rstrip("/").lower()
    return normalized_path == normalized_prefix or normalized_path.startswith(normalized_prefix + "/")


@dataclass(frozen=True)
class SiteAdapter:
    """Domain-specific rules that bias the shared crawl and parsing engine."""

    key: str
    domain: str
    allowed_path_prefixes: Tuple[str, ...] = ()
    default_seed_urls: Tuple[str, ...] = ()
    include_url_terms: Tuple[str, ...] = ()
    exclude_url_terms: Tuple[str, ...] = ()
    strict_path_prefixes: bool = False
    allow_root_url: bool = True
    discovery_terms: Tuple[str, ...] = ()
    content_selectors: Tuple[str, ...] = ()
    candidate_selectors: Tuple[str, ...] = ()
    parent_page_terms: Tuple[str, ...] = ()
    child_page_terms: Tuple[str, ...] = ()
    support_page_terms: Tuple[str, ...] = ()
    merge_aliases: Dict[str, str] = field(default_factory=dict)
    playwright_required_by_default: bool = False
    notes: Tuple[str, ...] = ()

    def matches_domain(self, candidate_domain: str) -> bool:
        normalized_candidate = extract_domain(candidate_domain)
        normalized_domain = extract_domain(self.domain)
        return (
            normalized_candidate == normalized_domain
            or normalized_candidate.endswith("." + normalized_domain)
            or normalized_domain.endswith("." + normalized_candidate)
        )

    def should_allow_url(self, url: str, anchor_text: str = "") -> bool:
        lowered = (url or "").lower()
        path = urlparse(url).path.lower()
        haystack = "%s %s" % (lowered, (anchor_text or "").lower())
        if _contains_any(haystack, self.exclude_url_terms):
            return False
        if not self.allowed_path_prefixes:
            return True
        if path in {"", "/"}:
            return self.allow_root_url
        if self.strict_path_prefixes:
            return any(_path_matches_prefix(path, prefix) for prefix in self.allowed_path_prefixes)
        return True
        if any(path.startswith(prefix.lower()) for prefix in self.allowed_path_prefixes):
            return True
        if _contains_any(haystack, self.include_url_terms):
            return True
        return False

    def should_use_browser(self, page: PageFetchResult) -> bool:
        if self.playwright_required_by_default:
            return True
        lowered = (page.html or "").lower()
        if "enable javascript" in lowered or "requires javascript" in lowered:
            return True
        return False

    def should_promote_records(self, page_type: str) -> bool:
        return page_type != "support-document"

    def should_promote_record(self, record: FundingProgrammeRecord, page_type: str) -> bool:
        return self.should_promote_records(page_type)

    def normalize_record(
        self,
        record: FundingProgrammeRecord,
        *,
        page_type: str,
        page_url: str,
        page_title: Optional[str] = None,
    ) -> FundingProgrammeRecord:
        return record

    def queue_score_bonus(self, url: str, anchor_text: str = "") -> Tuple[int, Optional[str]]:
        lowered = (url or "").lower()
        path = urlparse(url).path.lower()
        haystack = "%s %s" % (lowered, (anchor_text or "").lower())
        if _contains_any(haystack, self.exclude_url_terms):
            return -100, "adapter-excluded"
        score = 0
        reason: Optional[str] = None
        if any(_path_matches_prefix(path, prefix) for prefix in self.allowed_path_prefixes):
            score += 12
            reason = "adapter-prefix"
        if _contains_any(haystack, self.include_url_terms):
            score += 10
            reason = "adapter-include-term"
        if _contains_any(haystack, self.discovery_terms):
            score += 4
        return score, reason

    def page_role(
        self,
        page_url: str,
        page_title: Optional[str],
        text: str,
        record_count: int,
        candidate_block_count: int,
        internal_link_count: int,
        detail_link_count: int,
        application_link_count: int,
        document_link_count: int,
    ) -> str:
        lowered = " ".join([(page_url or "").lower(), (page_title or "").lower(), (text or "").lower()])
        if _contains_any(lowered, self.child_page_terms):
            return "child"
        if _contains_any(lowered, self.parent_page_terms):
            return "parent"
        if _contains_any(lowered, self.support_page_terms):
            return "support-document" if record_count <= 1 else "detail"
        if any(_path_matches_prefix(urlparse(page_url).path, path) for path in self.allowed_path_prefixes):
            return "programme_index_page"
        if record_count > 1:
            return "listing"
        if candidate_block_count > 1:
            return "mixed"
        if application_link_count or document_link_count:
            return "detail" if record_count else "support"
        if detail_link_count > 0 and record_count <= 1:
            return "listing" if detail_link_count > 2 else "detail"
        if internal_link_count > 8 and record_count <= 1:
            return "listing"
        return classify_page_type(
            record_count=record_count,
            candidate_block_count=candidate_block_count,
            internal_link_count=internal_link_count,
            detail_link_count=detail_link_count,
            application_link_count=application_link_count,
            document_link_count=document_link_count,
            text=text,
        )

    def program_name_for_merge(self, program_name: Optional[str]) -> Optional[str]:
        cleaned = clean_text(program_name or "")
        if not cleaned:
            return None
        merged = cleaned
        for alias, replacement in self.merge_aliases.items():
            merged = merged.replace(alias, replacement)
        merged = clean_text(merged)
        return merged or cleaned

    def funder_name_for_merge(self, funder_name: Optional[str]) -> Optional[str]:
        cleaned = clean_text(funder_name or "")
        return cleaned or None

    def default_seed_urls_for_domain(self, domain: str) -> List[str]:
        if not self.matches_domain(domain):
            return []
        return unique_preserve_order([str(url).strip() for url in self.default_seed_urls if str(url).strip()])
