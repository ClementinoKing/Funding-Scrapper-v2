"""Site adapter registry and built-in funding site rules."""

from scraper.adapters.base import SiteAdapter
from scraper.adapters.registry import SiteAdapterRegistry, build_default_registry

__all__ = ["SiteAdapter", "SiteAdapterRegistry", "build_default_registry"]
