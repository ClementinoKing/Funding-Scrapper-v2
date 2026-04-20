"""Supabase-backed site registry used to load crawl seeds."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

import httpx

from scraper.adapters.registry import SiteAdapterRegistry, build_default_registry
from scraper.config import SupabaseSettings
from scraper.utils.text import clean_text, unique_preserve_order
from scraper.utils.urls import canonicalize_url, extract_domain


def _coerce_text_list(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        result: List[str] = []
        for item in value:
            if isinstance(item, str):
                cleaned = clean_text(item)
                if cleaned:
                    result.append(cleaned)
            elif isinstance(item, dict):
                candidate = item.get("url") or item.get("value") or item.get("text")
                if candidate:
                    cleaned = clean_text(str(candidate))
                    if cleaned:
                        result.append(cleaned)
            else:
                cleaned = clean_text(str(item))
                if cleaned:
                    result.append(cleaned)
        return unique_preserve_order(result)
    if isinstance(value, str):
        cleaned = clean_text(value)
        return [cleaned] if cleaned else []
    return []


def _coerce_seed_urls(value: Any) -> List[str]:
    return unique_preserve_order(
        [
            canonicalize_url(url)
            for url in _coerce_text_list(value)
            if canonicalize_url(url)
        ]
    )


def _coerce_adapter_config(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}


def _load_seed_urls_from_file(seed_file: Path) -> List[str]:
    payload = json.loads(seed_file.read_text(encoding="utf-8"))
    urls: List[str] = []
    for item in payload:
        if isinstance(item, str):
            urls.append(item)
        elif isinstance(item, dict) and item.get("url"):
            urls.append(str(item["url"]))
    return unique_preserve_order(urls)


@dataclass(frozen=True)
class SiteDefinition:
    """One crawl target loaded from the `sites` table."""

    site_key: str
    display_name: str
    primary_domain: str
    adapter_key: str
    seed_urls: tuple[str, ...] = ()
    adapter_config: Dict[str, Any] = field(default_factory=dict)
    active: bool = True
    notes: tuple[str, ...] = ()
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_row(cls, row: Dict[str, Any], adapter_registry: Optional[SiteAdapterRegistry] = None) -> "SiteDefinition":
        registry = adapter_registry or build_default_registry()
        seed_urls = _coerce_seed_urls(row.get("seed_urls"))
        primary_domain = clean_text(str(row.get("primary_domain") or "")) or (
            extract_domain(seed_urls[0]) if seed_urls else ""
        )
        primary_domain = extract_domain(primary_domain) if primary_domain else ""
        adapter_key = clean_text(str(row.get("adapter_key") or "")) or registry.generic_adapter.key
        site_key = clean_text(str(row.get("site_key") or row.get("key") or "")) or (
            adapter_key if adapter_key else primary_domain
        )
        display_name = clean_text(str(row.get("display_name") or row.get("name") or "")) or site_key or primary_domain
        notes = tuple(_coerce_text_list(row.get("notes")))
        adapter_config = _coerce_adapter_config(row.get("adapter_config"))
        return cls(
            site_key=site_key or primary_domain or adapter_key or "unknown-site",
            display_name=display_name or primary_domain or adapter_key or "Unknown site",
            primary_domain=primary_domain or (extract_domain(seed_urls[0]) if seed_urls else ""),
            adapter_key=adapter_key or registry.generic_adapter.key,
            seed_urls=tuple(seed_urls),
            adapter_config=adapter_config,
            active=bool(row.get("active", True)),
            notes=notes,
            raw=dict(row),
        )


class SiteRepository:
    """Load active crawl sites from Supabase, with local fallback support."""

    def __init__(
        self,
        settings: Optional[SupabaseSettings] = None,
        *,
        adapter_registry: Optional[SiteAdapterRegistry] = None,
        table_name: str = "sites",
        client_factory: Callable[..., httpx.Client] = httpx.Client,
    ) -> None:
        self.settings = settings
        self.adapter_registry = adapter_registry or build_default_registry()
        self.table_name = table_name
        self.client_factory = client_factory

    def _headers(self) -> Dict[str, str]:
        if not self.settings:
            raise ValueError("Supabase settings are not configured.")
        return {
            "apikey": self.settings.anon_key,
            "Authorization": "Bearer %s" % self.settings.bearer_token,
            "Accept": "application/json",
        }

    def _fetch_rows(self, active_only: bool = True) -> List[Dict[str, Any]]:
        if not self.settings:
            raise ValueError("Supabase settings are not configured.")
        query = "select=site_key,display_name,primary_domain,seed_urls,adapter_key,adapter_config,active,notes"
        if active_only:
            query += "&active=eq.true"
        query += "&order=display_name.asc"
        url = "%s/rest/v1/%s?%s" % (self.settings.url, self.table_name, query)
        with self.client_factory(timeout=30, follow_redirects=True) as client:
            response = client.get(url, headers=self._headers())
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                raise ValueError("Expected a JSON array from the sites table.")
            return [row for row in payload if isinstance(row, dict)]

    def _load_local_sites(self, seed_file: Path) -> List[SiteDefinition]:
        seed_urls = _load_seed_urls_from_file(seed_file)
        grouped: Dict[str, Dict[str, Any]] = {}
        for seed_url in seed_urls:
            canonical = canonicalize_url(seed_url)
            primary_domain = extract_domain(canonical)
            if not primary_domain:
                continue
            bucket = grouped.setdefault(
                primary_domain,
                {
                    "site_key": primary_domain,
                    "display_name": primary_domain,
                    "primary_domain": primary_domain,
                    "adapter_key": self.adapter_registry.generic_adapter.key,
                    "seed_urls": [],
                    "adapter_config": {},
                    "active": True,
                    "notes": [],
                },
            )
            bucket["seed_urls"].append(canonical)
        return [
            SiteDefinition.from_row(row, adapter_registry=self.adapter_registry)
            for row in grouped.values()
        ]

    def load_sites(
        self,
        *,
        fallback_seed_file: Optional[Path] = None,
        active_only: bool = True,
    ) -> List[SiteDefinition]:
        if self.settings:
            try:
                rows = self._fetch_rows(active_only=active_only)
                sites = [SiteDefinition.from_row(row, adapter_registry=self.adapter_registry) for row in rows]
                if sites:
                    return sites
            except Exception:
                if fallback_seed_file:
                    return self._load_local_sites(fallback_seed_file)
                raise
        if fallback_seed_file:
            return self._load_local_sites(fallback_seed_file)
        return []

    def load_seed_urls(
        self,
        *,
        fallback_seed_file: Optional[Path] = None,
        active_only: bool = True,
    ) -> List[str]:
        urls: List[str] = []
        for site in self.load_sites(fallback_seed_file=fallback_seed_file, active_only=active_only):
            urls.extend(site.seed_urls)
        return unique_preserve_order(urls)
