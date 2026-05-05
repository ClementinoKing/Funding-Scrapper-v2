"""Industry taxonomy provider with configurable classification."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from scraper.taxonomies.base import TaxonomyMatch, TaxonomyProvider
from scraper.utils.text import clean_text


class IndustryTaxonomy(TaxonomyProvider):
    """Pluggable industry taxonomy with keyword-based classification."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.industry_keywords: Dict[str, List[str]] = {}
        self.industry_hierarchy: Dict[str, List[str]] = {}
        super().__init__(config)

    def _initialize(self) -> None:
        """Load industry taxonomy from config."""
        # Load from config
        self.industry_keywords = self.config.get("industry_keywords", {})
        self.industry_hierarchy = self.config.get("industry_hierarchy", {})

        # If no config provided, use empty taxonomy
        if not self.industry_keywords:
            self.industry_keywords = {}

    def classify(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[TaxonomyMatch]:
        """Classify industries from text based on keywords."""
        cleaned = clean_text(text).lower()
        matches: List[TaxonomyMatch] = []
        seen_industries = set()

        for industry, keywords in self.industry_keywords.items():
            matched_keywords = []
            for keyword in keywords:
                if keyword.lower() in cleaned:
                    matched_keywords.append(keyword)

            if matched_keywords and industry not in seen_industries:
                # Calculate confidence based on number of matches
                confidence = min(0.95, 0.6 + (len(matched_keywords) * 0.1))
                seen_industries.add(industry)

                # Check if this is a subcategory
                parent_category = None
                for parent, children in self.industry_hierarchy.items():
                    if industry in children:
                        parent_category = parent
                        break

                matches.append(
                    TaxonomyMatch(
                        category=parent_category or industry,
                        subcategory=industry if parent_category else None,
                        confidence=confidence,
                        matched_terms=matched_keywords[:5],
                        source_text=text[:200],
                    )
                )

        return matches

    def get_categories(self) -> List[str]:
        """Return all industry categories."""
        # Return top-level categories (those with children) plus standalone industries
        categories = list(self.industry_hierarchy.keys())
        standalone = [
            industry
            for industry in self.industry_keywords.keys()
            if not any(industry in children for children in self.industry_hierarchy.values())
        ]
        return categories + standalone

    def get_subcategories(self, category: str) -> List[str]:
        """Return subcategories for an industry category."""
        return self.industry_hierarchy.get(category, [])

    def validate(self, category: str, subcategory: Optional[str] = None) -> bool:
        """Validate an industry classification."""
        if category not in self.get_categories():
            return False
        if subcategory:
            valid_subcategories = self.get_subcategories(category)
            return subcategory in valid_subcategories if valid_subcategories else False
        return True

    @property
    def taxonomy_type(self) -> str:
        """Return taxonomy type identifier."""
        return "industry"

    def add_industry(
        self,
        industry: str,
        keywords: List[str],
        parent_category: Optional[str] = None,
    ) -> None:
        """Dynamically add a new industry to the taxonomy."""
        self.industry_keywords[industry] = keywords
        if parent_category:
            if parent_category not in self.industry_hierarchy:
                self.industry_hierarchy[parent_category] = []
            if industry not in self.industry_hierarchy[parent_category]:
                self.industry_hierarchy[parent_category].append(industry)
