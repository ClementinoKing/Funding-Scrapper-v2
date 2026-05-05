"""Geography taxonomy provider with multi-country support."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from scraper.taxonomies.base import TaxonomyMatch, TaxonomyProvider
from scraper.utils.text import clean_text


class GeographyTaxonomy(TaxonomyProvider):
    """Pluggable geography taxonomy supporting multiple countries."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.countries: Dict[str, Dict[str, Any]] = {}
        self.provinces: Dict[str, List[str]] = {}
        self.municipalities: Dict[str, List[str]] = {}
        self.postal_patterns: Dict[str, str] = {}
        super().__init__(config)

    def _initialize(self) -> None:
        """Load geography data from config."""
        # Default South Africa data
        default_sa_provinces = [
            "Eastern Cape",
            "Free State",
            "Gauteng",
            "KwaZulu-Natal",
            "Limpopo",
            "Mpumalanga",
            "Northern Cape",
            "North West",
            "Western Cape",
        ]

        # Load from config or use defaults
        countries_config = self.config.get("countries", {})
        if not countries_config:
            # Default to South Africa
            countries_config = {
                "ZA": {
                    "name": "South Africa",
                    "provinces": default_sa_provinces,
                    "municipalities": self.config.get("municipalities", []),
                    "postal_pattern": r"\b\d{4}\b",
                }
            }

        for country_code, country_data in countries_config.items():
            self.countries[country_code] = country_data
            self.provinces[country_code] = country_data.get("provinces", [])
            self.municipalities[country_code] = country_data.get("municipalities", [])
            postal_pattern = country_data.get("postal_pattern")
            if postal_pattern:
                self.postal_patterns[country_code] = postal_pattern

    def classify(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[TaxonomyMatch]:
        """Classify geographic scope from text."""
        context = context or {}
        country_code = context.get("country_code", "ZA")
        cleaned = clean_text(text).lower()
        matches: List[TaxonomyMatch] = []

        # Check for national scope
        national_terms = ["national", "nationwide", "country-wide", "all provinces"]
        if any(term in cleaned for term in national_terms):
            matches.append(
                TaxonomyMatch(
                    category="National",
                    confidence=0.9,
                    matched_terms=[term for term in national_terms if term in cleaned],
                    source_text=text[:200],
                )
            )

        # Check for international scope
        international_terms = ["international", "global", "worldwide", "cross-border"]
        if any(term in cleaned for term in international_terms):
            matches.append(
                TaxonomyMatch(
                    category="International",
                    confidence=0.85,
                    matched_terms=[term for term in international_terms if term in cleaned],
                    source_text=text[:200],
                )
            )

        # Check provinces
        provinces = self.provinces.get(country_code, [])
        matched_provinces = []
        for province in provinces:
            if province.lower() in cleaned:
                matched_provinces.append(province)
                matches.append(
                    TaxonomyMatch(
                        category="Province",
                        subcategory=province,
                        confidence=0.95,
                        matched_terms=[province],
                        source_text=text[:200],
                    )
                )

        # Check municipalities
        municipalities = self.municipalities.get(country_code, [])
        for municipality in municipalities:
            if municipality.lower() in cleaned:
                matches.append(
                    TaxonomyMatch(
                        category="Municipality",
                        subcategory=municipality,
                        confidence=0.9,
                        matched_terms=[municipality],
                        source_text=text[:200],
                    )
                )

        # Check postal codes
        postal_pattern = self.postal_patterns.get(country_code)
        if postal_pattern:
            postal_matches = re.findall(postal_pattern, text)
            if postal_matches:
                matches.append(
                    TaxonomyMatch(
                        category="PostalCode",
                        confidence=0.8,
                        matched_terms=postal_matches[:5],
                        source_text=text[:200],
                    )
                )

        return matches

    def get_categories(self) -> List[str]:
        """Return all geographic scope categories."""
        return ["National", "International", "Province", "Municipality", "PostalCode", "Local"]

    def get_subcategories(self, category: str) -> List[str]:
        """Return subcategories for a geographic category."""
        if category == "Province":
            # Return all provinces from all countries
            all_provinces = []
            for provinces in self.provinces.values():
                all_provinces.extend(provinces)
            return all_provinces
        if category == "Municipality":
            all_municipalities = []
            for municipalities in self.municipalities.values():
                all_municipalities.extend(municipalities)
            return all_municipalities
        return []

    def validate(self, category: str, subcategory: Optional[str] = None) -> bool:
        """Validate a geographic classification."""
        if category not in self.get_categories():
            return False
        if subcategory and category in {"Province", "Municipality"}:
            return subcategory in self.get_subcategories(category)
        return True

    @property
    def taxonomy_type(self) -> str:
        """Return taxonomy type identifier."""
        return "geography"

    def add_country(
        self,
        country_code: str,
        name: str,
        provinces: Optional[List[str]] = None,
        municipalities: Optional[List[str]] = None,
        postal_pattern: Optional[str] = None,
    ) -> None:
        """Dynamically add a new country to the taxonomy."""
        self.countries[country_code] = {"name": name}
        if provinces:
            self.provinces[country_code] = provinces
        if municipalities:
            self.municipalities[country_code] = municipalities
        if postal_pattern:
            self.postal_patterns[country_code] = postal_pattern
