"""Adapter registry and fallback resolution for funding sites."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence

from scraper.adapters.base import SiteAdapter
from scraper.adapters.sites import DEFAULT_SITE_ADAPTERS
from scraper.utils.urls import extract_domain
from scraper.utils.text import unique_preserve_order


def _normalize_domain(value: str) -> str:
    return extract_domain(value)


@dataclass
class SiteAdapterRegistry:
    """Resolve site-specific rules by domain, with a generic fallback."""

    adapters: Dict[str, SiteAdapter]
    generic_adapter: SiteAdapter

    @classmethod
    def default(cls) -> "SiteAdapterRegistry":
        adapters = {adapter.domain: adapter for adapter in DEFAULT_SITE_ADAPTERS}
        return cls(adapters=adapters, generic_adapter=SiteAdapter(
            key="generic",
            domain="*",
            include_url_terms=("fund", "grant", "loan", "finance", "programme", "program", "apply"),
            exclude_url_terms=("press", "news", "media", "publication", "blog", "careers", "privacy"),
            discovery_terms=("fund", "grant", "loan", "apply", "eligibility", "programme"),
            content_selectors=("main", "article", ".content", ".programme-content"),
            candidate_selectors=("article", "section.card", "section", ".card", ".tile", ".panel"),
        ))

    def register(self, adapter: SiteAdapter) -> None:
        self.adapters[adapter.domain] = adapter

    def resolve(self, domain_or_url: str) -> SiteAdapter:
        domain = _normalize_domain(domain_or_url)
        if not domain:
            return self.generic_adapter
        if domain in self.adapters:
            return self.adapters[domain]
        for registered_domain, adapter in self.adapters.items():
            normalized_registered = _normalize_domain(registered_domain)
            if domain == normalized_registered:
                return adapter
            if domain.endswith("." + normalized_registered) or normalized_registered.endswith("." + domain):
                return adapter
        return self.generic_adapter

    def default_seed_urls(self) -> List[str]:
        urls: List[str] = []
        for adapter in self.adapters.values():
            urls.extend(adapter.default_seed_urls)
        return unique_preserve_order(urls)


def build_default_registry() -> SiteAdapterRegistry:
    return SiteAdapterRegistry.default()
