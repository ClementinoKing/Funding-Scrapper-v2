from __future__ import annotations

import json
from pathlib import Path

from scraper.adapters.registry import build_default_registry
from scraper.config import SupabaseSettings
from scraper.storage.site_repository import SiteRepository


class FakeResponse:
    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.requests = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, url, headers=None):
        self.requests.append((url, headers or {}))
        return FakeResponse(self.payload)


def test_site_repository_loads_active_sites_from_supabase_rows() -> None:
    settings = SupabaseSettings(url="https://example.supabase.co", anon_key="anon")
    payload = [
        {
            "site_key": "nefcorp",
            "display_name": "NEF",
            "primary_domain": "nefcorp.co.za",
            "adapter_key": "nefcorp",
            "seed_urls": ["https://www.nefcorp.co.za/products-services/"],
            "adapter_config": {
                "allowed_path_prefixes": ["/products-services/"],
                "strict_path_prefixes": True,
                "site_profile": {
                    "content_scope_selectors": [".entry-content"],
                    "content_exclude_selectors": [".sidebar"],
                    "section_aliases": {"eligibility": ["who qualifies"]},
                },
            },
            "active": True,
            "notes": ["Primary funding site"],
        }
    ]
    client = FakeClient(payload)
    repo = SiteRepository(
        settings=settings,
        adapter_registry=build_default_registry(),
        client_factory=lambda **kwargs: client,
    )

    sites = repo.load_sites()

    assert len(sites) == 1
    site = sites[0]
    assert site.site_key == "nefcorp"
    assert site.display_name == "NEF"
    assert site.primary_domain == "www.nefcorp.co.za"
    assert site.adapter_key == "nefcorp"
    assert site.seed_urls == ("https://www.nefcorp.co.za/products-services",)
    assert site.adapter_config == {
        "allowed_path_prefixes": ["/products-services/"],
        "strict_path_prefixes": True,
        "site_profile": {
            "content_scope_selectors": [".entry-content"],
            "content_exclude_selectors": [".sidebar"],
            "section_aliases": {"eligibility": ["who qualifies"]},
        },
    }


def test_site_repository_reads_ai_enrichment_requirement_from_adapter_config() -> None:
    settings = SupabaseSettings(url="https://example.supabase.co", anon_key="anon")
    payload = [
        {
            "site_key": "nefcorp",
            "display_name": "NEF",
            "primary_domain": "www.nefcorp.co.za",
            "adapter_key": "nefcorp",
            "seed_urls": ["https://www.nefcorp.co.za/products-services/"],
            "adapter_config": {
                "ai_enrichment_required": True,
            },
            "active": True,
            "notes": [],
        }
    ]
    client = FakeClient(payload)
    repo = SiteRepository(
        settings=settings,
        adapter_registry=build_default_registry(),
        client_factory=lambda **kwargs: client,
    )

    site = repo.load_sites()[0]

    assert site.ai_enrichment_required is True


def test_site_repository_falls_back_to_local_seed_file(tmp_path: Path) -> None:
    seed_file = tmp_path / "seed_urls.json"
    seed_file.write_text(
        json.dumps(
            [
                {"name": "NEF", "url": "https://www.nefcorp.co.za/products-services/"},
                {"name": "NYDA", "url": "https://www.nyda.gov.za/"},
            ]
        ),
        encoding="utf-8",
    )

    repo = SiteRepository(settings=None, adapter_registry=build_default_registry())

    sites = repo.load_sites(fallback_seed_file=seed_file)
    urls = repo.load_seed_urls(fallback_seed_file=seed_file)

    assert {site.primary_domain for site in sites} == {"www.nefcorp.co.za", "www.nyda.gov.za"}
    assert urls == [
        "https://www.nefcorp.co.za/products-services",
        "https://www.nyda.gov.za/",
    ]
