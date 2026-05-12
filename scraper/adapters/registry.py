"""Adapter registry for the generic DB-driven scraper rules."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from scraper.adapters.base import SiteAdapter, SiteExtractionProfile
from scraper.utils.text import unique_preserve_order
from scraper.utils.urls import extract_domain


def _build_generic_adapter() -> SiteAdapter:
    # This is the one canonical adapter used by the runtime. The registry still
    # exists for compatibility, but all sites now start from this generic rule
    # set and then layer DB overrides on top.
    return SiteAdapter(
        key="generic",
        domain="*",
        include_url_terms=("fund", "grant", "loan", "finance", "programme", "program", "apply"),
        exclude_url_terms=("press", "news", "media", "publication", "blog", "careers", "privacy"),
        discovery_terms=("fund", "grant", "loan", "apply", "eligibility", "programme"),
        content_selectors=(
            "main",
            "[role='main']",
            "article",
            ".content",
            ".programme-content",
            ".entry-content",
            ".page-content",
            ".post-content",
            ".elementor",
            "[class*='wp-block']",
            ".views-row",
            ".field-content",
        ),
        candidate_selectors=(
            "article",
            "section.card",
            "section",
            ".card",
            ".tile",
            ".panel",
            ".views-row",
            ".field-content",
            "[class*='wp-block']",
            ".elementor-widget",
            ".accordion",
            ".tab-content",
            ".tab-pane",
            "tr",
        ),
        site_profile=SiteExtractionProfile(
            content_scope_selectors=(
                "main",
                "[role='main']",
                "article",
                ".content",
                ".programme-content",
                ".entry-content",
                ".page-content",
                ".post-content",
                ".elementor",
                "[class*='wp-block']",
                ".views-row",
                ".field-content",
            ),
            candidate_selectors=(
                "article",
                "section.card",
                "section",
                ".card",
                ".tile",
                ".panel",
                ".views-row",
                ".field-content",
                "[class*='wp-block']",
                ".elementor-widget",
                ".accordion",
                ".tab-content",
                ".tab-pane",
                "tr",
            ),
            section_heading_selectors=("h1", "h2", "h3", "h4"),
        ),
    )


def _build_sharepoint_portal_adapter() -> SiteAdapter:
    # Public institutions often expose programme content through SharePoint or
    # ShortPoint-style shells. This profile keeps the crawl generic while
    # widening the selectors and route hints for that CMS shape.
    return SiteAdapter(
        key="sharepoint_portal",
        domain="*",
        allowed_path_prefixes=("/Pages/", "/pic/", "/apply-for-funding/"),
        include_url_terms=(
            "fund",
            "funding",
            "investment",
            "portfolio",
            "properties",
            "isibaya",
            "early-stage",
            "programme",
            "program",
            "apply",
            "site map",
            "sitemap",
        ),
        exclude_url_terms=("news", "media", "press", "blog", "careers", "privacy", "terms", "login", "sign in", "cookie"),
        discovery_terms=("fund", "funding", "investment", "portfolio", "properties", "isibaya", "early-stage", "apply"),
        content_selectors=(
            "main",
            "article",
            ".content",
            ".programme-content",
            ".entry-content",
            ".ms-rtestate-field",
            ".spPageContent",
            ".shortpoint-content",
            ".shortpoint-block",
            ".shortpoint-section",
        ),
        candidate_selectors=(
            "article",
            "section",
            "section.card",
            ".card",
            ".tile",
            ".panel",
            ".accordion",
            ".tab-content",
            ".tab-pane",
            "[role='tabpanel']",
            ".ms-rtestate-field",
            ".shortpoint-content",
            ".shortpoint-block",
        ),
        content_exclude_selectors=(
            "nav",
            "footer",
            "header",
            "aside",
            ".sidebar",
            ".breadcrumbs",
            ".breadcrumb",
            ".cookie",
            ".cookie-banner",
            ".ms-ToolPane",
            ".ribbon",
            ".search",
            ".social",
        ),
        section_heading_selectors=(
            "h1",
            "h2",
            "h3",
            "h4",
            ".accordion-title",
            ".tab-title",
            ".panel-title",
            ".shortpoint-title",
        ),
        site_profile=SiteExtractionProfile(
            content_scope_selectors=(
                "main",
                "article",
                ".content",
                ".programme-content",
                ".entry-content",
                ".ms-rtestate-field",
                ".spPageContent",
                ".shortpoint-content",
                ".shortpoint-block",
                ".shortpoint-section",
            ),
            content_exclude_selectors=(
                "nav",
                "footer",
                "header",
                "aside",
                ".sidebar",
                ".breadcrumbs",
                ".breadcrumb",
                ".cookie",
                ".cookie-banner",
                ".ms-ToolPane",
                ".ribbon",
                ".search",
                ".social",
            ),
            candidate_selectors=(
                "article",
                "section",
                "section.card",
                ".card",
                ".tile",
                ".panel",
                ".accordion",
                ".tab-content",
                ".tab-pane",
                "[role='tabpanel']",
                ".ms-rtestate-field",
                ".shortpoint-content",
                ".shortpoint-block",
            ),
            section_heading_selectors=(
                "h1",
                "h2",
                "h3",
                "h4",
                ".accordion-title",
                ".tab-title",
                ".panel-title",
                ".shortpoint-title",
            ),
        ),
    )


def _build_pic_adapter() -> SiteAdapter:
    adapter = _build_sharepoint_portal_adapter()
    return SiteAdapter(
        key="pic",
        domain="www.pic.gov.za",
        allowed_path_prefixes=(
            "/isibaya",
            "/early-stage-fund",
            "/unlisted-investments",
            "/properties",
            "/apply-for-funding",
            "/pic/site/site-map",
            "/Pages",
        ),
        allowed_hosts=("www.pic.gov.za", "pic.gov.za"),
        default_seed_urls=(
            "https://www.pic.gov.za/",
            "https://www.pic.gov.za/isibaya",
            "https://www.pic.gov.za/apply-for-funding/isibaya",
            "https://www.pic.gov.za/early-stage-fund",
            "https://www.pic.gov.za/properties",
            "https://www.pic.gov.za/pic/site/site-map",
        ),
        include_url_terms=adapter.include_url_terms,
        exclude_url_terms=adapter.exclude_url_terms,
        discovery_terms=adapter.discovery_terms,
        content_selectors=adapter.content_selectors,
        candidate_selectors=adapter.candidate_selectors,
        content_exclude_selectors=adapter.content_exclude_selectors,
        section_heading_selectors=adapter.section_heading_selectors,
        force_browser_url_terms=("pic.gov.za",),
        playwright_required_by_default=True,
        site_profile=adapter.site_profile,
    )


@dataclass
class SiteAdapterRegistry:
    """Compatibility wrapper around the generic adapter.

    Older call sites still expect a registry object, so we keep the shape while
    letting the DB drive the active adapter profile for each site row.
    """

    adapters: Dict[str, SiteAdapter] = field(default_factory=dict)
    generic_adapter: SiteAdapter = field(default_factory=_build_generic_adapter)
    adapters_by_key: Dict[str, SiteAdapter] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Normalize any caller-supplied dicts so lookups are consistent.
        self.adapters = dict(self.adapters)
        if not self.adapters_by_key:
            self.adapters_by_key = {adapter.key: adapter for adapter in self.adapters.values()}
        else:
            self.adapters_by_key = dict(self.adapters_by_key)

    @classmethod
    def default(cls) -> "SiteAdapterRegistry":
        # The default registry keeps the generic adapter and a reusable portal
        # profile available for site rows that need SharePoint-style crawling.
        return cls(
            adapters_by_key={
                "sharepoint_portal": _build_sharepoint_portal_adapter(),
                "pic": _build_pic_adapter(),
            }
        )

    def register(self, adapter: SiteAdapter) -> None:
        # Still supported for tests or edge cases, but not used by the normal
        # runtime flow anymore.
        self.adapters[adapter.domain] = adapter
        self.adapters_by_key[adapter.key] = adapter

    def resolve(self, domain_or_url: str) -> SiteAdapter:
        # Any unknown domain falls back to the generic adapter.
        domain = extract_domain(domain_or_url)
        if not domain:
            return self.generic_adapter
        for registered_domain, adapter in self.adapters.items():
            normalized_registered = extract_domain(registered_domain)
            if domain == normalized_registered:
                return adapter
            if domain.endswith("." + normalized_registered) or normalized_registered.endswith("." + domain):
                return adapter
        return self.generic_adapter

    def get_by_key(self, adapter_key: str) -> SiteAdapter:
        # Runtime safety still matters, so unknown keys fall back to generic.
        if not adapter_key:
            return self.generic_adapter
        return self.adapters_by_key.get(adapter_key, self.generic_adapter)

    def build_for_site(
        self,
        *,
        adapter_key: str,
        primary_domain: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> SiteAdapter:
        # The DB is authoritative for site selection. If a row names an
        # unregistered adapter profile, we still honor that profile name by
        # cloning the generic baseline and attaching the DB key/domain.
        normalized_key = (adapter_key or "").strip() or self.generic_adapter.key
        base_adapter = self.adapters_by_key.get(normalized_key)
        if base_adapter is None:
            base_adapter = copy.copy(self.generic_adapter)
            object.__setattr__(base_adapter, "key", normalized_key)
            if primary_domain:
                object.__setattr__(base_adapter, "domain", primary_domain)
        return base_adapter.configured(config)

    def default_seed_urls(self) -> List[str]:
        # In the one-adapter world this is only useful if tests or custom code
        # manually registers extra adapters.
        urls: List[str] = []
        for adapter in self.adapters.values():
            urls.extend(adapter.default_seed_urls)
        return unique_preserve_order(urls)


def build_default_registry() -> SiteAdapterRegistry:
    return SiteAdapterRegistry.default()
