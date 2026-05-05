"""Pluggable taxonomy system for domain-agnostic classification."""

from scraper.taxonomies.base import TaxonomyProvider, TaxonomyRegistry
from scraper.taxonomies.geography import GeographyTaxonomy
from scraper.taxonomies.industry import IndustryTaxonomy
from scraper.taxonomies.funding import FundingTaxonomy

__all__ = [
    "TaxonomyProvider",
    "TaxonomyRegistry",
    "GeographyTaxonomy",
    "IndustryTaxonomy",
    "FundingTaxonomy",
]
