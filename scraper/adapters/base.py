"""Core site adapter contract used by the shared scraper engine."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import urlparse

from scraper.schemas import FundingProgrammeRecord, PageFetchResult
from scraper.utils.text import clean_text, strip_leading_numbered_prefix, unique_preserve_order
from scraper.utils.urls import extract_domain
from scraper.parsers.normalization import classify_page_type


# These helpers are intentionally tiny and boring because the real behavior
# lives in the adapter fields. They just make the rule checks easier to read.
def _contains_any(haystack: str, terms: Sequence[str]) -> bool:
    lowered = (haystack or "").lower()
    return any(term.lower() in lowered for term in terms)


def _path_matches_prefix(path: str, prefix: str) -> bool:
    normalized_path = (path or "").rstrip("/").lower()
    normalized_prefix = (prefix or "").rstrip("/").lower()
    return normalized_path == normalized_prefix or normalized_path.startswith(normalized_prefix + "/")


# Supabase rows store JSON-ish values, so this normalizes strings, arrays,
# and null-ish values into the tuple form used by the adapter dataclass.
def _as_string_tuple(value: Any) -> Tuple[str, ...]:
    if not value:
        return ()
    if isinstance(value, str):
        cleaned = clean_text(value)
        return (cleaned,) if cleaned else ()
    if isinstance(value, (list, tuple, set)):
        items: List[str] = []
        for item in value:
            cleaned = clean_text(str(item))
            if cleaned:
                items.append(cleaned)
        return tuple(unique_preserve_order(items))
    cleaned = clean_text(str(value))
    return (cleaned,) if cleaned else ()


def _as_string_tuple_map(value: Any) -> Dict[str, Tuple[str, ...]]:
    if not isinstance(value, Mapping):
        return {}
    result: Dict[str, Tuple[str, ...]] = {}
    for key, item in value.items():
        key_text = clean_text(str(key))
        if not key_text:
            continue
        values = _as_string_tuple(item)
        if values:
            result[key_text] = values
    return result


# Some site-specific cleanup is easier to express as regex patterns than as
# a pile of site-specific subclasses. We keep the helper generic so rows can
# supply their own title cleanup rules.
def _apply_regex_patterns(value: Optional[str], patterns: Sequence[str]) -> Optional[str]:
    cleaned = clean_text(value or "")
    if not cleaned:
        return None
    result = cleaned
    for pattern in patterns:
        pattern_text = clean_text(pattern)
        if not pattern_text:
            continue
        try:
            result = re.sub(pattern_text, "", result, flags=re.I)
        except re.error:
            continue
    result = clean_text(result)
    return result or None


PARENT_HUB_SEGMENTS = {
    "products-services",
    "product-services",
    "products",
    "services",
    "funding",
    "funding-solutions",
    "programmes",
    "programs",
    "opportunities",
    "support",
}

PARENT_SUPPORT_SEGMENT_TERMS = (
    "apply",
    "application",
    "applications",
    "programme-guidelines",
    "program-guidelines",
    "guidelines",
    "eligibility",
    "criteria",
    "checklist",
    "documents",
    "required-documents",
    "how-to-apply",
    "application-form",
    "overview",
)


def _looks_like_numbered_slug(segment: str) -> bool:
    cleaned = clean_text(segment or "").lower()
    return bool(re.match(r"^\d+(?:[-_].+)?$", cleaned))


def _humanize_slug(segment: str) -> Optional[str]:
    cleaned = clean_text(segment or "").strip("/")
    if not cleaned:
        return None
    cleaned = re.sub(r"^\d+(?:[.)-]|[-_])?\s*", "", cleaned)
    parts = [part for part in re.split(r"[-_]+", cleaned) if part]
    if not parts:
        return None
    return " ".join(part.upper() if part.isalpha() and len(part) <= 3 else part.capitalize() for part in parts)


def _extract_case_preserved_match(candidate: str, text: Optional[str]) -> Optional[str]:
    cleaned_candidate = clean_text(candidate or "")
    haystack = clean_text(text or "")
    if not cleaned_candidate or not haystack:
        return None
    match = re.search(rf"\b{re.escape(cleaned_candidate)}\b", haystack, flags=re.I)
    return clean_text(match.group(0)) if match else None


def _infer_parent_programme_name(
    record: FundingProgrammeRecord,
    *,
    page_type: str,
    page_url: str,
    page_title: Optional[str] = None,
) -> Optional[str]:
    existing = clean_text(record.parent_programme_name or "")
    if existing:
        return existing

    path_segments = [clean_text(segment) for segment in urlparse(page_url).path.split("/") if clean_text(segment)]
    informative_segments = [segment for segment in path_segments if segment.lower() not in PARENT_HUB_SEGMENTS]
    if len(informative_segments) < 2:
        return None

    parent_segment = informative_segments[-2]
    leaf_segment = informative_segments[-1].lower()
    is_support_child = any(term in leaf_segment for term in PARENT_SUPPORT_SEGMENT_TERMS)
    is_child_like = page_type == "child" or _looks_like_numbered_slug(leaf_segment) or is_support_child
    if not is_child_like:
        return None

    parent_label = _humanize_slug(parent_segment)
    if not parent_label:
        return None

    case_preserved = (
        _extract_case_preserved_match(parent_label, page_title)
        or _extract_case_preserved_match(parent_label, record.source_page_title)
        or _extract_case_preserved_match(parent_label, record.source_url)
    )
    parent_name = case_preserved or parent_label

    if clean_text(parent_name).casefold() == clean_text(record.program_name or "").casefold():
        return None

    return parent_name


@dataclass(frozen=True)
class SiteExtractionProfile:
    """Parser/extraction hints that shape how a site is read once fetched."""

    content_scope_selectors: Tuple[str, ...] = ()
    content_exclude_selectors: Tuple[str, ...] = ()
    candidate_selectors: Tuple[str, ...] = ()
    section_heading_selectors: Tuple[str, ...] = ()
    section_aliases: Dict[str, Tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class SiteAdapter:
    """Domain-specific rules that bias the shared crawl and parsing engine.

    The design here is intentionally data-driven:
    - the generic code stays in this class
    - site rows in Supabase override the fields they care about
    - empty config values leave the built-in defaults in place
    """

    key: str
    domain: str

    # Crawl boundary controls.
    allowed_path_prefixes: Tuple[str, ...] = ()
    default_seed_urls: Tuple[str, ...] = ()
    include_url_terms: Tuple[str, ...] = ()
    exclude_url_terms: Tuple[str, ...] = ()
    strict_path_prefixes: bool = False
    allow_root_url: bool = True

    # Content-discovery hints used by the parser and queue ranking.
    discovery_terms: Tuple[str, ...] = ()
    content_selectors: Tuple[str, ...] = ()
    candidate_selectors: Tuple[str, ...] = ()
    content_exclude_selectors: Tuple[str, ...] = ()
    section_heading_selectors: Tuple[str, ...] = ()
    section_aliases: Dict[str, Tuple[str, ...]] = field(default_factory=dict)
    parent_page_terms: Tuple[str, ...] = ()
    child_page_terms: Tuple[str, ...] = ()
    application_support_terms: Tuple[str, ...] = ()
    supporting_programme_terms: Tuple[str, ...] = ()
    support_page_terms: Tuple[str, ...] = ()

    # Normalization knobs that let DB rows clean up site-specific title noise
    # without needing a dedicated Python subclass.
    program_name_strip_prefix_patterns: Tuple[str, ...] = ()
    program_name_strip_suffix_patterns: Tuple[str, ...] = ()
    suppress_support_record_terms: Tuple[str, ...] = ()

    # Merge/dedupe hints and crawl behavior flags.
    merge_aliases: Dict[str, str] = field(default_factory=dict)
    playwright_required_by_default: bool = False
    crawl_mode: str = "default"
    notes: Tuple[str, ...] = ()
    site_profile: SiteExtractionProfile = field(default_factory=SiteExtractionProfile)

    def matches_domain(self, candidate_domain: str) -> bool:
        normalized_candidate = extract_domain(candidate_domain)
        normalized_domain = extract_domain(self.domain)
        return (
            normalized_candidate == normalized_domain
            or normalized_candidate.endswith("." + normalized_domain)
            or normalized_domain.endswith("." + normalized_candidate)
        )

    def should_allow_url(self, url: str, anchor_text: str = "") -> bool:
        # This is the first gate in the crawl queue: reject obvious noise fast,
        # then progressively relax into prefix/include-term matching.
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
        if any(_path_matches_prefix(path, prefix) for prefix in self.allowed_path_prefixes):
            return True
        return _contains_any(haystack, self.include_url_terms)

    def should_use_browser(self, page: PageFetchResult) -> bool:
        if self.playwright_required_by_default:
            return True
        lowered = (page.html or "").lower()
        # We only spend browser-rendering effort when the page signals that
        # JavaScript may be needed.
        if "enable javascript" in lowered or "requires javascript" in lowered:
            return True
        return False

    def should_promote_records(self, page_type: str) -> bool:
        # Support-document pages are always suppressed unless a site-specific
        # override changes the page type earlier in the pipeline.
        if page_type == "support-document":
            return False
        # funding_only means "keep the funding pages, skip the extra support
        # content" for sites like NYDA.
        if self.crawl_mode == "funding_only" and page_type == "supporting_or_complementary_programme_page":
            return False
        return True

    def should_promote_record(self, record: FundingProgrammeRecord, page_type: str) -> bool:
        # Page-level filtering happens first. Record-level filtering is a second
        # pass for cases where a support page still contains mixed-use content.
        if not self.should_promote_records(page_type):
            return False
        if self.crawl_mode == "funding_only" and page_type in {"application_support_page", "child"} and self.suppress_support_record_terms:
            combined = clean_text(
                " ".join([record.program_name or "", record.source_page_title or "", " ".join(record.notes or [])])
            ).lower()
            if _contains_any(combined, self.suppress_support_record_terms):
                return False
        return True

    def normalize_record(
        self,
        record: FundingProgrammeRecord,
        *,
        page_type: str,
        page_url: str,
        page_title: Optional[str] = None,
    ) -> FundingProgrammeRecord:
        # Strip provider noise from the program title before dedupe runs. This is
        # where site rows can clean up the output without a custom subclass.
        program_name = _apply_regex_patterns(record.program_name, self.program_name_strip_prefix_patterns)
        program_name = _apply_regex_patterns(program_name, self.program_name_strip_suffix_patterns)
        program_name = strip_leading_numbered_prefix(program_name or "")
        if not program_name and page_title:
            program_name = _apply_regex_patterns(page_title, self.program_name_strip_prefix_patterns)
            program_name = _apply_regex_patterns(program_name, self.program_name_strip_suffix_patterns)
            program_name = strip_leading_numbered_prefix(program_name or "")
        if not program_name and page_title:
            program_name = strip_leading_numbered_prefix(page_title)
        parent_programme_name = _infer_parent_programme_name(
            record,
            page_type=page_type,
            page_url=page_url,
            page_title=page_title,
        )
        return record.model_copy(
            update={
                "program_name": program_name or record.program_name,
                "parent_programme_name": parent_programme_name or record.parent_programme_name,
            }
        )

    def extraction_profile(self) -> SiteExtractionProfile:
        return SiteExtractionProfile(
            content_scope_selectors=(
                self.site_profile.content_scope_selectors or self.content_selectors
            ),
            content_exclude_selectors=(
                self.site_profile.content_exclude_selectors or self.content_exclude_selectors
            ),
            candidate_selectors=(
                self.site_profile.candidate_selectors or self.candidate_selectors
            ),
            section_heading_selectors=(
                self.site_profile.section_heading_selectors or self.section_heading_selectors
            ),
            section_aliases=(
                dict(self.site_profile.section_aliases) if self.site_profile.section_aliases else dict(self.section_aliases)
            ),
        )

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
        # The page-role ladder is ordered from most-specific to most-generic so
        # DB overrides can force a site into the right bucket early.
        if _contains_any(lowered, self.child_page_terms):
            return "child"
        if _contains_any(lowered, self.parent_page_terms):
            return "parent"
        if _contains_any(lowered, self.application_support_terms):
            return "application_support_page"
        if _contains_any(lowered, self.supporting_programme_terms):
            return "supporting_or_complementary_programme_page"
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
        # Dedupe works better when provider-specific aliases collapse to one name.
        cleaned = strip_leading_numbered_prefix(program_name or "")
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

    def configured(self, config: Optional[Mapping[str, Any]]) -> "SiteAdapter":
        # Sparse DB rows are the common case. If no config is supplied, return
        # the adapter untouched so all built-in defaults remain active.
        if not config:
            return self

        clone = copy.copy(self)

        # Lists and selector strings replace the base values only when the DB row
        # actually provides something. Empty arrays are treated as "leave default".
        tuple_fields = (
            "allowed_path_prefixes",
            "default_seed_urls",
            "include_url_terms",
            "exclude_url_terms",
            "discovery_terms",
            "content_selectors",
            "candidate_selectors",
            "content_exclude_selectors",
            "section_heading_selectors",
            "parent_page_terms",
            "child_page_terms",
            "support_page_terms",
        )
        for field_name in tuple_fields:
            if field_name in config:
                values = _as_string_tuple(config.get(field_name))
                if values:
                    object.__setattr__(clone, field_name, values)

        # Booleans are different: explicit false is meaningful, so we always
        # write the value if the column exists.
        for field_name in (
            "strict_path_prefixes",
            "allow_root_url",
            "playwright_required_by_default",
        ):
            if field_name in config:
                object.__setattr__(clone, field_name, bool(config.get(field_name)))

        for field_name in (
            "program_name_strip_prefix_patterns",
            "program_name_strip_suffix_patterns",
            "suppress_support_record_terms",
            "application_support_terms",
            "supporting_programme_terms",
        ):
            if field_name in config:
                values = _as_string_tuple(config.get(field_name))
                if values:
                    object.__setattr__(clone, field_name, values)

        # crawl_mode is the one "behavior toggle" we keep as a plain string so a
        # site can opt into support-content crawling without a subclass.
        if "crawl_mode" in config:
            crawl_mode = clean_text(str(config.get("crawl_mode") or ""))
            if crawl_mode:
                object.__setattr__(clone, "crawl_mode", crawl_mode)

        # Merge aliases are additive because the base aliases are often still
        # useful even when a site adds its own cleanup rules.
        if "merge_aliases" in config and isinstance(config.get("merge_aliases"), Mapping):
            aliases = dict(self.merge_aliases)
            for alias, replacement in config["merge_aliases"].items():
                alias_text = clean_text(str(alias))
                if not alias_text:
                    continue
                aliases[alias_text] = clean_text(str(replacement)) if replacement is not None else ""
            object.__setattr__(clone, "merge_aliases", aliases)

        if "section_aliases" in config:
            section_aliases = _as_string_tuple_map(config.get("section_aliases"))
            if section_aliases:
                object.__setattr__(clone, "section_aliases", section_aliases)

        profile = copy.deepcopy(self.site_profile)
        profile_source = config.get("site_profile")
        if isinstance(profile_source, Mapping):
            if "content_scope_selectors" in profile_source:
                values = _as_string_tuple(profile_source.get("content_scope_selectors"))
                if values:
                    object.__setattr__(profile, "content_scope_selectors", values)
            elif clone.content_selectors and not profile.content_scope_selectors:
                object.__setattr__(profile, "content_scope_selectors", clone.content_selectors)

            if "content_exclude_selectors" in profile_source:
                values = _as_string_tuple(profile_source.get("content_exclude_selectors"))
                if values:
                    object.__setattr__(profile, "content_exclude_selectors", values)
            elif clone.content_exclude_selectors and not profile.content_exclude_selectors:
                object.__setattr__(profile, "content_exclude_selectors", clone.content_exclude_selectors)

            if "candidate_selectors" in profile_source:
                values = _as_string_tuple(profile_source.get("candidate_selectors"))
                if values:
                    object.__setattr__(profile, "candidate_selectors", values)
            elif clone.candidate_selectors and not profile.candidate_selectors:
                object.__setattr__(profile, "candidate_selectors", clone.candidate_selectors)

            if "section_heading_selectors" in profile_source:
                values = _as_string_tuple(profile_source.get("section_heading_selectors"))
                if values:
                    object.__setattr__(profile, "section_heading_selectors", values)
            elif clone.section_heading_selectors and not profile.section_heading_selectors:
                object.__setattr__(profile, "section_heading_selectors", clone.section_heading_selectors)

            if "section_aliases" in profile_source:
                aliases = _as_string_tuple_map(profile_source.get("section_aliases"))
                if aliases:
                    object.__setattr__(profile, "section_aliases", aliases)
            elif clone.section_aliases and not profile.section_aliases:
                object.__setattr__(profile, "section_aliases", dict(clone.section_aliases))
        else:
            if clone.content_selectors and not profile.content_scope_selectors:
                object.__setattr__(profile, "content_scope_selectors", clone.content_selectors)
            if clone.content_exclude_selectors and not profile.content_exclude_selectors:
                object.__setattr__(profile, "content_exclude_selectors", clone.content_exclude_selectors)
            if clone.candidate_selectors and not profile.candidate_selectors:
                object.__setattr__(profile, "candidate_selectors", clone.candidate_selectors)
            if clone.section_heading_selectors and not profile.section_heading_selectors:
                object.__setattr__(profile, "section_heading_selectors", clone.section_heading_selectors)
            if clone.section_aliases and not profile.section_aliases:
                object.__setattr__(profile, "section_aliases", dict(clone.section_aliases))

        object.__setattr__(clone, "site_profile", profile)

        return clone

    def default_seed_urls_for_domain(self, domain: str) -> List[str]:
        # The generic adapter does not own a domain-specific seed list. This only
        # returns something for adapters that were given explicit defaults.
        if not self.matches_domain(domain):
            return []
        return unique_preserve_order([str(url).strip() for url in self.default_seed_urls if str(url).strip()])
