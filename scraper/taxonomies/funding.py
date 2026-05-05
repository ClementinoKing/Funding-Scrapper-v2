"""Funding-specific taxonomy provider."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from scraper.taxonomies.base import TaxonomyMatch, TaxonomyProvider
from scraper.utils.text import clean_text


class FundingTaxonomy(TaxonomyProvider):
    """Taxonomy for funding-specific classifications (use of funds, ownership targets, etc.)."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.use_of_funds_keywords: Dict[str, List[str]] = {}
        self.ownership_target_keywords: Dict[str, List[str]] = {}
        self.entity_type_keywords: Dict[str, List[str]] = {}
        self.certification_keywords: Dict[str, List[str]] = {}
        super().__init__(config)

    def _initialize(self) -> None:
        """Load funding taxonomy from config."""
        self.use_of_funds_keywords = self.config.get("use_of_funds_keywords", {})
        self.ownership_target_keywords = self.config.get("ownership_target_keywords", {})
        self.entity_type_keywords = self.config.get("entity_type_keywords", {})
        self.certification_keywords = self.config.get("certification_keywords", {})

    def classify(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[TaxonomyMatch]:
        """Classify funding-related attributes from text."""
        context = context or {}
        classification_type = context.get("classification_type", "all")
        cleaned = clean_text(text).lower()
        matches: List[TaxonomyMatch] = []

        # Classify use of funds
        if classification_type in {"all", "use_of_funds"}:
            matches.extend(self._classify_use_of_funds(cleaned, text))

        # Classify ownership targets
        if classification_type in {"all", "ownership_targets"}:
            matches.extend(self._classify_ownership_targets(cleaned, text))

        # Classify entity types
        if classification_type in {"all", "entity_types"}:
            matches.extend(self._classify_entity_types(cleaned, text))

        # Classify certifications
        if classification_type in {"all", "certifications"}:
            matches.extend(self._classify_certifications(cleaned, text))

        return matches

    def _classify_use_of_funds(self, cleaned: str, original_text: str) -> List[TaxonomyMatch]:
        """Classify use of funds categories."""
        matches: List[TaxonomyMatch] = []
        for category, keywords in self.use_of_funds_keywords.items():
            matched_keywords = [kw for kw in keywords if kw.lower() in cleaned]
            if matched_keywords:
                confidence = min(0.9, 0.6 + (len(matched_keywords) * 0.08))
                matches.append(
                    TaxonomyMatch(
                        category="UseOfFunds",
                        subcategory=category,
                        confidence=confidence,
                        matched_terms=matched_keywords[:5],
                        source_text=original_text[:200],
                    )
                )
        return matches

    def _classify_ownership_targets(self, cleaned: str, original_text: str) -> List[TaxonomyMatch]:
        """Classify ownership target categories."""
        matches: List[TaxonomyMatch] = []
        for category, keywords in self.ownership_target_keywords.items():
            matched_keywords = [kw for kw in keywords if kw.lower() in cleaned]
            if matched_keywords:
                confidence = min(0.95, 0.7 + (len(matched_keywords) * 0.08))
                matches.append(
                    TaxonomyMatch(
                        category="OwnershipTarget",
                        subcategory=category,
                        confidence=confidence,
                        matched_terms=matched_keywords[:5],
                        source_text=original_text[:200],
                    )
                )
        return matches

    def _classify_entity_types(self, cleaned: str, original_text: str) -> List[TaxonomyMatch]:
        """Classify entity type categories."""
        matches: List[TaxonomyMatch] = []
        for category, keywords in self.entity_type_keywords.items():
            matched_keywords = [kw for kw in keywords if kw.lower() in cleaned]
            if matched_keywords:
                confidence = min(0.9, 0.65 + (len(matched_keywords) * 0.08))
                matches.append(
                    TaxonomyMatch(
                        category="EntityType",
                        subcategory=category,
                        confidence=confidence,
                        matched_terms=matched_keywords[:5],
                        source_text=original_text[:200],
                    )
                )
        return matches

    def _classify_certifications(self, cleaned: str, original_text: str) -> List[TaxonomyMatch]:
        """Classify certification categories."""
        matches: List[TaxonomyMatch] = []
        for category, keywords in self.certification_keywords.items():
            matched_keywords = [kw for kw in keywords if kw.lower() in cleaned]
            if matched_keywords:
                confidence = min(0.95, 0.75 + (len(matched_keywords) * 0.05))
                matches.append(
                    TaxonomyMatch(
                        category="Certification",
                        subcategory=category,
                        confidence=confidence,
                        matched_terms=matched_keywords[:5],
                        source_text=original_text[:200],
                    )
                )
        return matches

    def get_categories(self) -> List[str]:
        """Return all funding taxonomy categories."""
        return ["UseOfFunds", "OwnershipTarget", "EntityType", "Certification"]

    def get_subcategories(self, category: str) -> List[str]:
        """Return subcategories for a funding category."""
        if category == "UseOfFunds":
            return list(self.use_of_funds_keywords.keys())
        if category == "OwnershipTarget":
            return list(self.ownership_target_keywords.keys())
        if category == "EntityType":
            return list(self.entity_type_keywords.keys())
        if category == "Certification":
            return list(self.certification_keywords.keys())
        return []

    def validate(self, category: str, subcategory: Optional[str] = None) -> bool:
        """Validate a funding classification."""
        if category not in self.get_categories():
            return False
        if subcategory:
            return subcategory in self.get_subcategories(category)
        return True

    @property
    def taxonomy_type(self) -> str:
        """Return taxonomy type identifier."""
        return "funding"
