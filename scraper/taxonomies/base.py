"""Base taxonomy provider interface for pluggable classification systems."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class TaxonomyMatch:
    """Result of a taxonomy classification."""

    category: str
    subcategory: Optional[str] = None
    confidence: float = 0.0
    matched_terms: List[str] = field(default_factory=list)
    source_text: Optional[str] = None


class TaxonomyProvider(ABC):
    """Abstract base for pluggable taxonomy providers."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        self._initialize()

    @abstractmethod
    def _initialize(self) -> None:
        """Load taxonomy data and prepare for classification."""
        pass

    @abstractmethod
    def classify(self, text: str, context: Optional[Dict[str, Any]] = None) -> List[TaxonomyMatch]:
        """Classify text against this taxonomy."""
        pass

    @abstractmethod
    def get_categories(self) -> List[str]:
        """Return all available categories in this taxonomy."""
        pass

    @abstractmethod
    def get_subcategories(self, category: str) -> List[str]:
        """Return subcategories for a given category."""
        pass

    @abstractmethod
    def validate(self, category: str, subcategory: Optional[str] = None) -> bool:
        """Check if a category/subcategory combination is valid."""
        pass

    @property
    @abstractmethod
    def taxonomy_type(self) -> str:
        """Return the type identifier for this taxonomy."""
        pass


class TaxonomyRegistry:
    """Central registry for managing multiple taxonomy providers."""

    def __init__(self) -> None:
        self._providers: Dict[str, TaxonomyProvider] = {}
        self._default_providers: Dict[str, str] = {}

    def register(
        self,
        taxonomy_type: str,
        provider: TaxonomyProvider,
        set_as_default: bool = True,
    ) -> None:
        """Register a taxonomy provider."""
        key = f"{taxonomy_type}:{provider.__class__.__name__}"
        self._providers[key] = provider
        if set_as_default or taxonomy_type not in self._default_providers:
            self._default_providers[taxonomy_type] = key

    def get(
        self,
        taxonomy_type: str,
        provider_name: Optional[str] = None,
    ) -> Optional[TaxonomyProvider]:
        """Get a taxonomy provider by type and optional name."""
        if provider_name:
            key = f"{taxonomy_type}:{provider_name}"
            return self._providers.get(key)
        default_key = self._default_providers.get(taxonomy_type)
        return self._providers.get(default_key) if default_key else None

    def list_providers(self, taxonomy_type: Optional[str] = None) -> List[str]:
        """List all registered providers, optionally filtered by type."""
        if taxonomy_type:
            prefix = f"{taxonomy_type}:"
            return [key for key in self._providers.keys() if key.startswith(prefix)]
        return list(self._providers.keys())

    def classify_all(
        self,
        text: str,
        taxonomy_types: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, List[TaxonomyMatch]]:
        """Classify text against multiple taxonomies."""
        results: Dict[str, List[TaxonomyMatch]] = {}
        types_to_check = taxonomy_types or list(self._default_providers.keys())
        for taxonomy_type in types_to_check:
            provider = self.get(taxonomy_type)
            if provider:
                results[taxonomy_type] = provider.classify(text, context)
        return results


# Global registry instance
_global_registry: Optional[TaxonomyRegistry] = None


def get_global_registry() -> TaxonomyRegistry:
    """Get or create the global taxonomy registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = TaxonomyRegistry()
    return _global_registry


def register_taxonomy(
    provider: TaxonomyProvider,
    set_as_default: bool = True,
) -> None:
    """Register a taxonomy provider in the global registry."""
    registry = get_global_registry()
    registry.register(provider.taxonomy_type, provider, set_as_default)
