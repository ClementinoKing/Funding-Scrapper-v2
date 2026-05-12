"""Typed contracts for OpenAI Web Search extraction."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from scraper.storage.site_repository import SiteDefinition
from scraper.utils.text import clean_text, unique_preserve_order
from scraper.utils.urls import canonicalize_url, extract_host


COUNTRY_CODES = {
    "south africa": "ZA",
    "malawi": "MW",
}


@dataclass(frozen=True)
class WebSearchFunder:
    """One funder processed by the web-search pipeline."""

    funder_name: str
    website_url: str
    country: str = "South Africa"
    currency: str = "ZAR"
    site_key: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def domain(self) -> str:
        return extract_host(self.website_url)

    @property
    def country_code(self) -> str:
        return COUNTRY_CODES.get(self.country.strip().casefold(), "ZA")

    @classmethod
    def from_site(cls, site: SiteDefinition) -> "WebSearchFunder":
        website_url = site.seed_urls[0] if site.seed_urls else site.primary_domain
        if website_url and not website_url.startswith(("http://", "https://")):
            website_url = "https://%s" % website_url.strip("/")
        adapter_config = site.adapter_config or {}
        return cls(
            funder_name=site.display_name or site.site_key or site.primary_domain,
            website_url=canonicalize_url(website_url) or website_url,
            country=clean_text(str(adapter_config.get("country") or "South Africa")) or "South Africa",
            currency=clean_text(str(adapter_config.get("currency") or "ZAR")).upper() or "ZAR",
            site_key=site.site_key,
            raw=site.raw,
        )


class WebSearchSource(BaseModel):
    """One source consulted or cited during web-search extraction."""

    url: str
    title: Optional[str] = None
    source_type: str = "web_page"
    official_rank: int = 4

    @model_validator(mode="after")
    def _normalize(self) -> "WebSearchSource":
        self.url = canonicalize_url(self.url) or self.url
        self.title = clean_text(self.title or "") or None
        self.source_type = clean_text(self.source_type or "") or "web_page"
        self.official_rank = max(1, min(int(self.official_rank or 4), 4))
        return self


class WebSearchProgrammeDraft(BaseModel):
    """Programme shape requested from OpenAI before mapping to DB columns."""

    program_name: Optional[str] = None
    parent_program_name: Optional[str] = None
    is_sub_programme: bool = False
    funding_type: Optional[str] = None
    funding_lines: List[str] = Field(default_factory=list)
    ticket_min: Optional[Any] = None
    ticket_max: Optional[Any] = None
    ideal_range: Optional[str] = None
    currency: Optional[str] = None
    raw_eligibility_criteria: List[str] = Field(default_factory=list)
    raw_repayment_terms: List[str] = Field(default_factory=list)
    sector_focus: List[str] = Field(default_factory=list)
    required_documents: List[str] = Field(default_factory=list)
    application_process: Optional[str] = None
    target_applicants: List[str] = Field(default_factory=list)
    geographic_focus: Optional[str] = None
    source_url: Optional[str] = None
    source_title: Optional[str] = None
    source_type: Optional[str] = None
    confidence_score: int = 0
    extraction_notes: Optional[str] = None
    secondary_sources: List[WebSearchSource] = Field(default_factory=list)
    query: Optional[str] = None

    @field_validator(
        "funding_lines",
        "raw_eligibility_criteria",
        "raw_repayment_terms",
        "sector_focus",
        "required_documents",
        "target_applicants",
        mode="before",
    )
    @classmethod
    def _normalize_lists(cls, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        return unique_preserve_order([clean_text(str(item)) for item in value if clean_text(str(item))])

    @field_validator("confidence_score", mode="before")
    @classmethod
    def _normalize_confidence_score(cls, value: Any) -> int:
        if value is None or value == "":
            return 0
        try:
            score = float(value)
        except (TypeError, ValueError):
            return 0
        if 0 <= score <= 1:
            score *= 100
        return max(0, min(round(score), 100))

    @model_validator(mode="after")
    def _normalize(self) -> "WebSearchProgrammeDraft":
        self.program_name = clean_text(self.program_name or "") or None
        self.parent_program_name = clean_text(self.parent_program_name or "") or None
        self.currency = clean_text(self.currency or "").upper() or None
        self.source_url = canonicalize_url(self.source_url or "") or None
        self.source_title = clean_text(self.source_title or "") or None
        self.source_type = clean_text(self.source_type or "") or None
        self.ideal_range = clean_text(self.ideal_range or "") or None
        self.application_process = clean_text(self.application_process or "") or None
        self.geographic_focus = clean_text(self.geographic_focus or "") or None
        self.extraction_notes = clean_text(self.extraction_notes or "") or None
        self.query = clean_text(self.query or "") or None
        self.confidence_score = max(0, min(int(self.confidence_score or 0), 100))
        if self.parent_program_name:
            self.is_sub_programme = True
        return self


class WebSearchExtractionResponse(BaseModel):
    """Structured response for one funder/query extraction."""

    funder_name: Optional[str] = None
    website_url: Optional[str] = None
    country: Optional[str] = None
    currency: Optional[str] = None
    programmes: List[WebSearchProgrammeDraft] = Field(default_factory=list)
    status: str = "ok"
    notes: Optional[str] = None


@dataclass
class FunderWebSearchResult:
    """Completed processing result for one funder."""

    funder: WebSearchFunder
    records: list
    review_records: list
    skipped_low_confidence: int = 0
    candidate_sources_found: int = 0
    queries_run: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    completed: bool = True
