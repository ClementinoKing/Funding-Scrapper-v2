"""Pydantic schemas for crawler, extraction, and storage artifacts."""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from uuid import NAMESPACE_URL, uuid5
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator

from scraper.config import load_json_resource
from scraper import __version__ as SCRAPER_VERSION
from scraper.utils.text import (
    clean_text,
    generate_program_id,
    sentence_chunks,
    slugify,
    split_lines,
    strip_leading_numbered_prefix,
    unique_preserve_order,
)
from scraper.utils.document_reader import document_type_label
from scraper.utils.urls import is_probably_document_url


APPROVED_PROVINCES = set(load_json_resource("provinces.json"))
APPROVED_MUNICIPALITIES = set(load_json_resource("municipalities.json"))


class FundingType(str, Enum):
    GRANT = "Grant"
    LOAN = "Loan"
    EQUITY = "Equity"
    GUARANTEE = "Guarantee"
    HYBRID = "Hybrid"
    OTHER = "Other"
    UNKNOWN = "Unknown"


class DeadlineType(str, Enum):
    FIXED_DATE = "FixedDate"
    ROLLING = "Rolling"
    OPEN = "Open"
    UNKNOWN = "Unknown"


class GeographyScope(str, Enum):
    NATIONAL = "National"
    PROVINCE = "Province"
    MUNICIPALITY = "Municipality"
    LOCAL = "Local"
    INTERNATIONAL = "International"
    UNKNOWN = "Unknown"


class TriState(str, Enum):
    YES = "Yes"
    NO = "No"
    MAYBE = "Maybe"
    UNKNOWN = "Unknown"


class InterestType(str, Enum):
    FIXED = "Fixed"
    PRIME_LINKED = "Prime-linked"
    FACTOR_RATE = "Factor-rate"
    UNKNOWN = "Unknown"


class RepaymentFrequency(str, Enum):
    WEEKLY = "Weekly"
    MONTHLY = "Monthly"
    QUARTERLY = "Quarterly"
    ANNUALLY = "Annually"
    ONCE_OFF = "Once-off"
    FLEXIBLE = "Flexible"
    VARIABLE = "Variable"
    UNKNOWN = "Unknown"


class ApplicationChannel(str, Enum):
    ONLINE_FORM = "Online form"
    EMAIL = "Email"
    BRANCH = "Branch"
    PARTNER_REFERRAL = "Partner referral"
    MANUAL_CONTACT_FIRST = "Manual / Contact first"
    UNKNOWN = "Unknown"


class ProgrammeStatus(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed"
    OPENING_SOON = "opening_soon"
    SUSPENDED = "suspended"
    UNKNOWN = "unknown"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ProgrammeNature(str, Enum):
    DIRECT_FUNDING = "direct_funding"
    VOUCHER_SUPPORT = "voucher_support"
    NON_FINANCIAL_SUPPORT = "non_financial_support"
    UNKNOWN = "unknown"


class DisplayCategory(str, Enum):
    FUNDING = "funding"
    SUPPORT = "support"
    BOTH = "both"
    UNKNOWN = "unknown"


class SupportType(str, Enum):
    VOUCHER = "voucher"
    MENTORSHIP = "mentorship"
    MARKET_LINKAGE = "market_linkage"
    BUSINESS_MANAGEMENT_TRAINING = "business_management_training"
    APPLICATION_SUPPORT = "application_support"
    SPONSORSHIP = "sponsorship"
    BUSINESS_SUPPORT = "business_support"
    UNKNOWN = "unknown"


class FieldEvidence(BaseModel):
    """Field-level traceability for extracted evidence."""

    field_name: str
    normalized_value: Optional[Any] = None
    raw_value: Optional[Any] = None
    evidence_text: str
    source_url: str
    source_section: Optional[str] = None
    source_scope: Optional[str] = None
    confidence: float = 0.0
    method: str = "direct_page_evidence"


class SectionNode(BaseModel):
    """One node in the reviewer/debug section tree."""

    title: str
    level: int = 1
    text: str = ""
    source_url: Optional[str] = None
    children: List["SectionNode"] = Field(default_factory=list)


class PageDebugRecord(BaseModel):
    """Compact per-record trace bundle for a crawled page."""

    program_name: Optional[str] = None
    parent_programme_name: Optional[str] = None
    source_scope: Optional[str] = None
    evidence_map: Dict[str, List[FieldEvidence]] = Field(default_factory=dict)
    confidence_map: Dict[str, float] = Field(default_factory=dict)
    notes: List[str] = Field(default_factory=list)


class PageContentSection(BaseModel):
    """A semantic section extracted from the cleaned page body."""

    heading: str
    content: str


class PageInteractiveSection(BaseModel):
    """A semantic section extracted from an interactive page container."""

    type: str
    label: str
    content: str

    @model_validator(mode="after")
    def _normalize(self) -> "PageInteractiveSection":
        self.type = clean_text(self.type) or "interactive"
        self.label = clean_text(self.label)
        self.content = clean_text(self.content)
        return self


class DocumentEvidenceSnapshot(BaseModel):
    """Compact evidence extracted from a linked or source document."""

    document_url: str
    document_kind: str
    content_type: Optional[str] = None
    source_method: str = "http"
    summary: Optional[str] = None
    key_points: List[str] = Field(default_factory=list)
    extracted_text: Optional[str] = None
    notes: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _normalize(self) -> "DocumentEvidenceSnapshot":
        self.document_url = clean_text(self.document_url)
        self.document_kind = clean_text(self.document_kind) or document_type_label(self.document_url, self.content_type)
        self.content_type = clean_text(self.content_type or "") or None
        self.source_method = clean_text(self.source_method or "") or "http"
        self.summary = clean_text(self.summary or "") or None
        self.key_points = unique_preserve_order([clean_text(item) for item in self.key_points if clean_text(item)])
        self.extracted_text = clean_text(self.extracted_text or "") or None
        self.notes = unique_preserve_order([clean_text(item) for item in self.notes if clean_text(item)])
        return self


class PageContentDocument(BaseModel):
    """Raw, generic page content sent to the AI classifier."""

    page_url: str
    title: Optional[str] = None
    source_content_type: Optional[str] = None
    headings: List[str] = Field(default_factory=list)
    full_body_text: str = ""
    structured_sections: List[PageContentSection] = Field(default_factory=list)
    interactive_sections: List[PageInteractiveSection] = Field(default_factory=list)
    discovered_links: List[str] = Field(default_factory=list)
    internal_links: List[str] = Field(default_factory=list)
    application_links: List[str] = Field(default_factory=list)
    document_links: List[str] = Field(default_factory=list)
    document_evidence: List[DocumentEvidenceSnapshot] = Field(default_factory=list)
    main_content_hint: Optional[str] = None
    source_domain: Optional[str] = None
    page_title: Optional[str] = None
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def _normalize(self) -> "PageContentDocument":
        self.headings = unique_preserve_order([cleaned for cleaned in (clean_text(item) for item in self.headings) if cleaned])
        self.full_body_text = clean_text(self.full_body_text)
        self.title = clean_text(self.title) or None
        self.source_content_type = clean_text(self.source_content_type or "") or None
        self.page_title = clean_text(self.page_title) or self.title
        self.structured_sections = [
            PageContentSection(
                heading=clean_text(section.heading),
                content=clean_text(section.content),
            )
            for section in self.structured_sections
            if clean_text(section.heading) or clean_text(section.content)
        ]
        self.interactive_sections = [
            PageInteractiveSection(
                type=clean_text(section.type),
                label=clean_text(section.label),
                content=clean_text(section.content),
            )
            for section in self.interactive_sections
            if clean_text(section.label) or clean_text(section.content)
        ]
        self.discovered_links = unique_preserve_order([clean_text(item) for item in self.discovered_links if clean_text(item)])
        self.internal_links = unique_preserve_order([clean_text(item) for item in self.internal_links if clean_text(item)])
        self.application_links = unique_preserve_order([clean_text(item) for item in self.application_links if clean_text(item)])
        self.document_links = unique_preserve_order([clean_text(item) for item in self.document_links if clean_text(item)])
        self.document_evidence = [DocumentEvidenceSnapshot.model_validate(item) for item in self.document_evidence if item]
        self.main_content_hint = clean_text(self.main_content_hint or "") or None
        self.source_domain = clean_text(self.source_domain or "") or None
        return self

    @property
    def records(self) -> List["FundingProgrammeRecord"]:
        from scraper.ai.ai_enhancement import AIClassifier

        classifier = AIClassifier({"aiProvider": "openai", "disableRemoteAi": True}, storage=None)
        return classifier.classify_document(self)

    @property
    def page_ai_context(self) -> "PageAIContext":
        record_snapshots = [
            PageAIRecordSnapshot(
                record_index=index,
                normalized_record=record.model_dump(mode="json", exclude={"page_debug_package"}),
            )
            for index, record in enumerate(self.records)
        ]
        candidate_blocks: List[CandidateBlockSnapshot] = []
        if self.structured_sections:
            for section in self.structured_sections:
                candidate_blocks.append(
                    CandidateBlockSnapshot(
                        heading=section.heading,
                        text=section.content,
                        source_url=self.page_url,
                        section_map={section.heading: [section.content]},
                        section_tree=[],
                        section_bundle={},
                        section_aliases={},
                        detail_links=list(self.internal_links),
                        application_links=list(self.application_links),
                        document_links=list(self.document_links),
                    )
                )
        for interactive_section in self.interactive_sections:
            candidate_blocks.append(
                CandidateBlockSnapshot(
                    heading=interactive_section.label or interactive_section.type,
                    text=interactive_section.content,
                    source_url=self.page_url,
                    section_map={interactive_section.label or interactive_section.type: [interactive_section.content]},
                    section_tree=[],
                    section_bundle={},
                    section_aliases={},
                    detail_links=list(self.internal_links),
                    application_links=list(self.application_links),
                    document_links=list(self.document_links),
                )
            )
        if not candidate_blocks:
            candidate_blocks.append(
                CandidateBlockSnapshot(
                    heading=self.title or self.page_title or "",
                    text=self.full_body_text,
                    source_url=self.page_url,
                    section_map={},
                    section_tree=[],
                    section_bundle={},
                    section_aliases={},
                    detail_links=list(self.internal_links),
                    application_links=list(self.application_links),
                    document_links=list(self.document_links),
                )
            )
        return PageAIContext(
            page_url=self.page_url,
            final_url=self.page_url,
            page_title=self.title or self.page_title,
            cleaned_text=self.full_body_text,
            section_tree=[],
            discovered_links=list(self.discovered_links),
            internal_links=list(self.internal_links),
            application_links=list(self.application_links),
            document_links=list(self.document_links),
            candidate_blocks=candidate_blocks,
            current_records=record_snapshots,
            debug_package=PageDebugPackageSnapshot(
                page_url=self.page_url,
                final_url=self.page_url,
                page_title=self.title or self.page_title,
                cleaned_text=self.full_body_text,
                section_tree=[],
                extracted_evidence_map={},
                confidence_map={},
                records=[],
            ),
        )

    @property
    def page_debug_package(self) -> "PageDebugPackage":
        return PageDebugPackage(
            page_url=self.page_url,
            final_url=self.page_url,
            page_title=self.title or self.page_title,
            cleaned_text=self.full_body_text,
            section_tree=[],
            extracted_evidence_map={},
            confidence_map={},
            records=[],
            ai_context=self.page_ai_context,
        )


class AIProgrammeDraft(BaseModel):
    """One AI-produced draft record before local technical fields are added."""

    program_name: Optional[str] = None
    funder_name: Optional[str] = None
    parent_programme_name: Optional[str] = None
    source_url: Optional[str] = None
    source_urls: List[str] = Field(default_factory=list)
    source_page_title: Optional[str] = None
    raw_eligibility_data: Optional[List[str]] = None
    raw_eligibility_criteria: List[str] = Field(default_factory=list)
    raw_funding_offer_data: List[str] = Field(default_factory=list)
    raw_terms_data: List[str] = Field(default_factory=list)
    raw_documents_data: List[str] = Field(default_factory=list)
    raw_application_data: List[str] = Field(default_factory=list)
    funding_type: Optional[str] = None
    funding_lines: List[str] = Field(default_factory=list)
    ticket_min: Optional[float] = None
    ticket_max: Optional[float] = None
    currency: Optional[str] = None
    program_budget_total: Optional[float] = None
    deadline_type: Optional[str] = None
    deadline_date: Optional[date] = None
    funding_speed_days_min: Optional[int] = None
    funding_speed_days_max: Optional[int] = None
    geography_scope: Optional[str] = None
    provinces: List[str] = Field(default_factory=list)
    municipalities: List[str] = Field(default_factory=list)
    postal_code_ranges: List[str] = Field(default_factory=list)
    industries: List[str] = Field(default_factory=list)
    use_of_funds: List[str] = Field(default_factory=list)
    business_stage_eligibility: List[str] = Field(default_factory=list)
    turnover_min: Optional[float] = None
    turnover_max: Optional[float] = None
    years_in_business_min: Optional[float] = None
    years_in_business_max: Optional[float] = None
    employee_min: Optional[int] = None
    employee_max: Optional[int] = None
    ownership_targets: List[str] = Field(default_factory=list)
    entity_types_allowed: List[str] = Field(default_factory=list)
    certifications_required: List[str] = Field(default_factory=list)
    security_required: Optional[str] = None
    equity_required: Optional[str] = None
    payback_months_min: Optional[int] = None
    payback_months_max: Optional[int] = None
    payback_raw_text: Optional[str] = None
    payback_term_min_months: Optional[int] = None
    payback_term_max_months: Optional[int] = None
    payback_structure: Optional[str] = None
    grace_period_months: Optional[int] = None
    interest_type: Optional[str] = None
    repayment_frequency: Optional[str] = None
    payback_confidence: Optional[float] = None
    exclusions: List[str] = Field(default_factory=list)
    required_documents: List[str] = Field(default_factory=list)
    application_channel: Optional[str] = None
    application_url: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    raw_text_snippets: Dict[str, List[str]] = Field(default_factory=dict)
    extraction_confidence: Dict[str, float] = Field(default_factory=dict)
    related_documents: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    approval_status: Optional[str] = None
    country_code: Optional[str] = None
    status: Optional[str] = None
    page_type: Optional[str] = None
    page_role: Optional[str] = None
    source_scope: Optional[str] = None
    ai_enriched: Optional[bool] = None

    @field_validator(
        "source_urls",
        "raw_funding_offer_data",
        "raw_eligibility_criteria",
        "raw_terms_data",
        "raw_documents_data",
        "raw_application_data",
        "provinces",
        "municipalities",
        "postal_code_ranges",
        "industries",
        "use_of_funds",
        "business_stage_eligibility",
        "ownership_targets",
        "entity_types_allowed",
        "certifications_required",
        "exclusions",
        "required_documents",
        "related_documents",
        "notes",
        mode="before",
    )
    @classmethod
    def _normalize_list_fields(cls, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        cleaned: List[str] = []
        for item in value:
            if item is None:
                continue
            text = clean_text(str(item))
            if text:
                cleaned.append(text)
        return unique_preserve_order(cleaned)

    @field_validator(
        "payback_raw_text",
        "payback_structure",
        mode="before",
    )
    @classmethod
    def _normalize_optional_text_fields(cls, value: Any) -> Optional[str]:
        text = clean_text(str(value)) if value is not None else ""
        return text or None

    @field_validator(
        "payback_months_min",
        "payback_months_max",
        "payback_term_min_months",
        "payback_term_max_months",
        "grace_period_months",
        mode="before",
    )
    @classmethod
    def _normalize_optional_int_fields(cls, value: Any) -> Optional[int]:
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        try:
            return int(float(str(value).strip()))
        except (TypeError, ValueError):
            return None

    @field_validator("payback_confidence", mode="before")
    @classmethod
    def _normalize_payback_confidence(cls, value: Any) -> Optional[float]:
        if value is None or value == "":
            return None
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return None
        return max(0.0, min(confidence, 1.0))

    @field_validator("funding_lines", mode="before")
    @classmethod
    def _normalize_funding_lines(cls, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        cleaned: List[str] = []
        for item in value:
            if item is None:
                continue
            for fragment in sentence_chunks(str(item)) or split_lines(str(item)):
                text = clean_text(fragment)
                if text:
                    cleaned.append(text)
        return unique_preserve_order(cleaned)

    @field_validator("raw_eligibility_data", mode="before")
    @classmethod
    def _normalize_optional_list_fields(cls, value: Any) -> Optional[List[str]]:
        if value is None:
            return None
        if isinstance(value, str):
            value = [value]
        cleaned: List[str] = []
        for item in value:
            if item is None:
                continue
            fragments = sentence_chunks(str(item)) or split_lines(str(item))
            for fragment in fragments:
                text = clean_text(str(fragment))
                if text:
                    cleaned.append(text)
        return unique_preserve_order(cleaned) or None

    @field_validator("raw_eligibility_criteria", mode="before")
    @classmethod
    def _normalize_raw_eligibility_criteria(cls, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        cleaned: List[str] = []
        for item in value:
            if item is None:
                continue
            fragments = sentence_chunks(str(item)) or split_lines(str(item))
            for fragment in fragments:
                text = clean_text(str(fragment))
                if text:
                    cleaned.append(text)
        return unique_preserve_order(cleaned)

    @field_validator("raw_text_snippets", "extraction_confidence", mode="before")
    @classmethod
    def _normalize_mapping_fields(cls, value: Any) -> Dict[str, Any]:
        return value or {}


class AIClassificationResponse(BaseModel):
    """Strict JSON response returned by the AI model."""

    page_decision: Optional[str] = None
    page_type: Optional[str] = None
    page_decision_confidence: Optional[float] = None
    records: List[AIProgrammeDraft] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class AIMergeDecisionResponse(BaseModel):
    """Strict JSON response returned by the AI merge judge."""

    merge_decision: Optional[str] = None
    confidence: Optional[float] = None
    reason: Optional[str] = None


class PageDebugPackageBase(BaseModel):
    """Reviewer/debug artifact saved alongside parsed pages."""

    page_url: str
    final_url: Optional[str] = None
    page_title: Optional[str] = None
    cleaned_text: str = ""
    section_tree: List[SectionNode] = Field(default_factory=list)
    extracted_evidence_map: Dict[str, List[FieldEvidence]] = Field(default_factory=dict)
    confidence_map: Dict[str, float] = Field(default_factory=dict)
    records: List[PageDebugRecord] = Field(default_factory=list)


class PageDebugPackageSnapshot(PageDebugPackageBase):
    """AI-safe snapshot of the page debug bundle."""


class PageAIRecordSnapshot(BaseModel):
    """One normalized record snapshot supplied to AI for column-aware repair."""

    record_index: int
    normalized_record: Dict[str, Any] = Field(default_factory=dict)


class CandidateBlockSnapshot(BaseModel):
    """AI-safe snapshot of a candidate programme block."""

    heading: str
    text: str
    source_url: str
    section_map: Dict[str, List[str]] = Field(default_factory=dict)
    section_tree: List[SectionNode] = Field(default_factory=list)
    section_bundle: Dict[str, Any] = Field(default_factory=dict)
    section_aliases: Dict[str, List[str]] = Field(default_factory=dict)
    detail_links: List[str] = Field(default_factory=list)
    application_links: List[str] = Field(default_factory=list)
    document_links: List[str] = Field(default_factory=list)


class PageAIContext(BaseModel):
    """Structured page payload passed to the AI enrichment step."""

    page_url: str
    final_url: Optional[str] = None
    page_title: Optional[str] = None
    cleaned_text: str = ""
    section_tree: List[SectionNode] = Field(default_factory=list)
    discovered_links: List[str] = Field(default_factory=list)
    internal_links: List[str] = Field(default_factory=list)
    application_links: List[str] = Field(default_factory=list)
    document_links: List[str] = Field(default_factory=list)
    candidate_blocks: List[CandidateBlockSnapshot] = Field(default_factory=list)
    current_records: List[PageAIRecordSnapshot] = Field(default_factory=list)
    debug_package: Optional[PageDebugPackageSnapshot] = None


class PageDebugPackage(PageDebugPackageBase):
    ai_context: Optional[PageAIContext] = None


class CrawlTraceEntry(BaseModel):
    """One crawl/discovery event for debugging and provenance."""

    event: str
    url: str
    adapter_name: Optional[str] = None
    source_url: Optional[str] = None
    canonical_url: Optional[str] = None
    depth: Optional[int] = None
    score: Optional[float] = None
    reason: Optional[str] = None
    page_type: Optional[str] = None
    page_role: Optional[str] = None
    status_code: Optional[int] = None
    records_found: int = 0
    discovered_links: int = 0
    document_links: int = 0
    notes: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PageFetchResult(BaseModel):
    """Output of a fetcher call."""

    url: str
    requested_url: str
    canonical_url: str
    final_url: Optional[str] = None
    status_code: Optional[int] = None
    content_type: Optional[str] = None
    html: str = ""
    title: Optional[str] = None
    fetch_method: str = "http"
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    headers: Dict[str, str] = Field(default_factory=dict)
    js_rendered: bool = False
    response_bytes: int = 0
    retry_count: int = 0
    elapsed_seconds: float = 0.0
    browser_fallback_reason: Optional[str] = None
    notes: List[str] = Field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        if not self.status_code or not 200 <= self.status_code < 400:
            return False
        if self.html:
            return True
        lowered_content_type = (self.content_type or "").lower()
        if lowered_content_type.startswith(
            (
                "image/",
                "application/pdf",
                "application/msword",
                "application/vnd.ms-excel",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        ):
            return True
        return is_probably_document_url(self.url)


class FundingProgrammeRecord(BaseModel):
    """Canonical normalized funding programme record."""

    id: str = ""
    program_id: str = ""
    program_name: Optional[str] = None
    program_slug: Optional[str] = None
    funder_name: Optional[str] = None
    funder_slug: Optional[str] = None
    country_code: str = "ZA"
    status: ProgrammeStatus = ProgrammeStatus.UNKNOWN
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    site_adapter: Optional[str] = None
    page_type: Optional[str] = None
    page_role: Optional[str] = None
    parent_programme_name: Optional[str] = None
    programme_nature: ProgrammeNature = ProgrammeNature.UNKNOWN
    display_category: DisplayCategory = DisplayCategory.UNKNOWN
    support_type: SupportType = SupportType.UNKNOWN
    source_url: str
    source_urls: List[str] = Field(default_factory=list)
    source_domain: str
    source_page_title: Optional[str] = None
    source_scope: Optional[str] = None
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_verified_at: Optional[date] = None
    raw_eligibility_data: Optional[List[str]] = None
    raw_eligibility_criteria: List[str] = Field(default_factory=list)
    raw_funding_offer_data: List[str] = Field(default_factory=list)
    raw_terms_data: List[str] = Field(default_factory=list)
    raw_documents_data: List[str] = Field(default_factory=list)
    raw_application_data: List[str] = Field(default_factory=list)
    evidence_by_field: Dict[str, List[str]] = Field(default_factory=dict)
    field_confidence: Dict[str, float] = Field(default_factory=dict)
    extraction_confidence_by_field: Dict[str, float] = Field(default_factory=dict)

    funding_type: FundingType = FundingType.UNKNOWN
    funding_lines: List[str] = Field(default_factory=list)
    ticket_min: Optional[float] = None
    ticket_max: Optional[float] = None
    currency: Optional[str] = None
    program_budget_total: Optional[float] = None

    deadline_type: DeadlineType = DeadlineType.UNKNOWN
    deadline_date: Optional[date] = None
    funding_speed_days_min: Optional[int] = None
    funding_speed_days_max: Optional[int] = None

    geography_scope: GeographyScope = GeographyScope.UNKNOWN
    provinces: List[str] = Field(default_factory=list)
    municipalities: List[str] = Field(default_factory=list)
    postal_code_ranges: List[str] = Field(default_factory=list)

    industries: List[str] = Field(default_factory=list)
    use_of_funds: List[str] = Field(default_factory=list)
    business_stage_eligibility: List[str] = Field(default_factory=list)
    turnover_min: Optional[float] = None
    turnover_max: Optional[float] = None
    years_in_business_min: Optional[float] = None
    years_in_business_max: Optional[float] = None
    employee_min: Optional[int] = None
    employee_max: Optional[int] = None
    ownership_targets: List[str] = Field(default_factory=list)
    entity_types_allowed: List[str] = Field(default_factory=list)
    certifications_required: List[str] = Field(default_factory=list)

    security_required: TriState = TriState.UNKNOWN
    equity_required: TriState = TriState.UNKNOWN
    payback_months_min: Optional[int] = None
    payback_months_max: Optional[int] = None
    payback_raw_text: Optional[str] = None
    payback_term_min_months: Optional[int] = None
    payback_term_max_months: Optional[int] = None
    payback_structure: Optional[str] = None
    grace_period_months: Optional[int] = None
    interest_type: InterestType = InterestType.UNKNOWN
    repayment_frequency: RepaymentFrequency = RepaymentFrequency.UNKNOWN
    payback_confidence: float = 0.0

    exclusions: List[str] = Field(default_factory=list)
    required_documents: List[str] = Field(default_factory=list)

    application_channel: ApplicationChannel = ApplicationChannel.UNKNOWN
    application_url: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None

    raw_text_snippets: Dict[str, List[str]] = Field(default_factory=dict)
    extraction_confidence: Dict[str, float] = Field(default_factory=dict)
    field_evidence: Dict[str, List[FieldEvidence]] = Field(default_factory=dict)
    related_documents: List[str] = Field(default_factory=list)
    parser_version: str = SCRAPER_VERSION
    ai_enriched: bool = False
    needs_review: bool = False
    needs_review_reasons: List[str] = Field(default_factory=list)
    validation_errors: List[str] = Field(default_factory=list)
    field_conflicts: Dict[str, List[str]] = Field(default_factory=dict)
    deleted_at: Optional[datetime] = None
    notes: List[str] = Field(default_factory=list)
    page_debug_package: Optional[PageDebugPackage] = None

    @field_validator(
        "provinces",
        "municipalities",
        "postal_code_ranges",
        "industries",
        "use_of_funds",
        "business_stage_eligibility",
        "raw_eligibility_criteria",
        "ownership_targets",
        "entity_types_allowed",
        "certifications_required",
        "exclusions",
        "required_documents",
        "related_documents",
        "raw_funding_offer_data",
        "raw_terms_data",
        "raw_documents_data",
        "raw_application_data",
        "needs_review_reasons",
        "validation_errors",
        "notes",
        mode="before",
    )
    @classmethod
    def _normalize_list_fields(cls, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        cleaned: List[str] = []
        for item in value:
            if item is None:
                continue
            text = " ".join(str(item).split()).strip()
            if text:
                cleaned.append(text)
        return unique_preserve_order(cleaned)

    @field_validator(
        "payback_raw_text",
        "payback_structure",
        "page_role",
        mode="before",
    )
    @classmethod
    def _normalize_optional_text_fields(cls, value: Any) -> Optional[str]:
        text = clean_text(str(value)) if value is not None else ""
        return text or None

    @field_validator(
        "payback_months_min",
        "payback_months_max",
        "payback_term_min_months",
        "payback_term_max_months",
        "grace_period_months",
        mode="before",
    )
    @classmethod
    def _normalize_optional_int_fields(cls, value: Any) -> Optional[int]:
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        try:
            return int(float(str(value).strip()))
        except (TypeError, ValueError):
            return None

    @field_validator("payback_confidence", mode="before")
    @classmethod
    def _normalize_payback_confidence(cls, value: Any) -> float:
        if value is None or value == "":
            return 0.0
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(confidence, 1.0))

    @field_validator("funding_lines", mode="before")
    @classmethod
    def _normalize_funding_lines(cls, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        cleaned: List[str] = []
        for item in value:
            if item is None:
                continue
            fragments = sentence_chunks(str(item)) or split_lines(str(item))
            for fragment in fragments:
                text = clean_text(str(fragment))
                if text:
                    cleaned.append(text)
        return unique_preserve_order(cleaned)

    @field_validator("source_urls", mode="before")
    @classmethod
    def _normalize_source_urls(cls, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return unique_preserve_order([str(item).strip() for item in value if str(item).strip()])

    @field_validator("raw_eligibility_data", mode="before")
    @classmethod
    def _normalize_raw_eligibility(cls, value: Any) -> Optional[List[str]]:
        if value is None:
            return None
        if isinstance(value, str):
            value = [value]
        cleaned: List[str] = []
        for item in value:
            if item is None:
                continue
            fragments = sentence_chunks(str(item)) or split_lines(str(item))
            for fragment in fragments:
                text = clean_text(str(fragment))
                if text:
                    cleaned.append(text)
        cleaned = unique_preserve_order(cleaned)
        return cleaned or None

    @field_validator("raw_eligibility_criteria", mode="before")
    @classmethod
    def _normalize_raw_eligibility_criteria(cls, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        cleaned: List[str] = []
        for item in value:
            if item is None:
                continue
            fragments = sentence_chunks(str(item)) or split_lines(str(item))
            for fragment in fragments:
                text = clean_text(str(fragment))
                if text:
                    cleaned.append(text)
        return unique_preserve_order(cleaned)

    @field_validator("field_evidence", mode="before")
    @classmethod
    def _normalize_field_evidence(cls, value: Any) -> Dict[str, List[FieldEvidence]]:
        if not value:
            return {}
        if isinstance(value, list):
            value = {"evidence": value}
        if not isinstance(value, dict):
            return {}
        normalized: Dict[str, List[FieldEvidence]] = {}
        for field_name, evidence_items in value.items():
            if evidence_items is None:
                continue
            if isinstance(evidence_items, (FieldEvidence, dict, str)):
                iterable = [evidence_items]
            else:
                iterable = list(evidence_items)
            cleaned: List[FieldEvidence] = []
            for item in iterable:
                try:
                    if isinstance(item, FieldEvidence):
                        cleaned.append(item)
                    elif isinstance(item, dict):
                        payload = dict(item)
                        payload.setdefault("field_name", str(field_name))
                        cleaned.append(FieldEvidence.model_validate(payload))
                    else:
                        text = " ".join(str(item).split()).strip()
                        if text:
                            cleaned.append(
                                FieldEvidence(
                                    field_name=str(field_name),
                                    evidence_text=text,
                                    source_url="",
                                )
                            )
                except Exception:
                    continue
            if cleaned:
                normalized[str(field_name)] = cleaned
        return normalized

    @field_validator("raw_text_snippets", mode="before")
    @classmethod
    def _normalize_raw_snippets(cls, value: Any) -> Dict[str, List[str]]:
        if not value:
            return {}
        normalized: Dict[str, List[str]] = {}
        for field_name, snippets in value.items():
            if snippets is None:
                continue
            if isinstance(snippets, str):
                snippet_values = [snippets]
            else:
                snippet_values = list(snippets)
            cleaned = unique_preserve_order(
                [" ".join(str(item).split()).strip() for item in snippet_values if str(item).strip()]
            )
            if cleaned:
                normalized[str(field_name)] = cleaned
        return normalized

    @field_validator("evidence_by_field", mode="before")
    @classmethod
    def _normalize_evidence_by_field(cls, value: Any) -> Dict[str, List[str]]:
        return cls._normalize_raw_snippets(value)

    @field_validator("extraction_confidence_by_field", mode="before")
    @classmethod
    def _normalize_extraction_confidence_by_field(cls, value: Any) -> Dict[str, float]:
        if not value:
            return {}
        normalized: Dict[str, float] = {}
        for field_name, confidence in value.items():
            try:
                normalized[str(field_name)] = max(0.0, min(float(confidence), 1.0))
            except (TypeError, ValueError):
                continue
        return normalized

    @field_validator("extraction_confidence", mode="before")
    @classmethod
    def _normalize_confidence(cls, value: Any) -> Dict[str, float]:
        if not value:
            return {}
        normalized: Dict[str, float] = {}
        for field_name, confidence in value.items():
            try:
                normalized[str(field_name)] = max(0.0, min(float(confidence), 1.0))
            except (TypeError, ValueError):
                continue
        return normalized

    @field_validator("field_confidence", mode="before")
    @classmethod
    def _normalize_field_confidence(cls, value: Any) -> Dict[str, float]:
        return cls._normalize_confidence(value)

    @field_validator("field_conflicts", mode="before")
    @classmethod
    def _normalize_field_conflicts(cls, value: Any) -> Dict[str, List[str]]:
        if not value or not isinstance(value, dict):
            return {}
        normalized: Dict[str, List[str]] = {}
        for field_name, conflicts in value.items():
            if conflicts is None:
                continue
            if isinstance(conflicts, str):
                items = [conflicts]
            else:
                items = list(conflicts)
            cleaned = unique_preserve_order([clean_text(str(item)) for item in items if clean_text(str(item))])
            if cleaned:
                normalized[str(field_name)] = cleaned
        return normalized

    @field_validator("source_url", "application_url")
    @classmethod
    def _validate_urls(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("URL must be http(s) with a host")
        return value

    @field_validator("contact_email")
    @classmethod
    def _validate_email(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return value.strip().lower()

    @field_validator("provinces")
    @classmethod
    def _validate_provinces(cls, value: List[str]) -> List[str]:
        invalid = [province for province in value if province not in APPROVED_PROVINCES]
        if invalid:
            raise ValueError("Unknown provinces: %s" % ", ".join(sorted(invalid)))
        return value

    @field_validator("municipalities")
    @classmethod
    def _validate_municipalities(cls, value: List[str]) -> List[str]:
        invalid = [municipality for municipality in value if municipality not in APPROVED_MUNICIPALITIES]
        if invalid:
            raise ValueError("Unknown municipalities: %s" % ", ".join(sorted(invalid)))
        return value

    @model_validator(mode="after")
    def _validate_ranges(self) -> "FundingProgrammeRecord":
        self.program_name = strip_leading_numbered_prefix(self.program_name or "") or self.program_name
        self.parent_programme_name = strip_leading_numbered_prefix(self.parent_programme_name or "") or self.parent_programme_name
        if self.payback_term_min_months is None and self.payback_months_min is not None:
            self.payback_term_min_months = self.payback_months_min
        if self.payback_term_max_months is None and self.payback_months_max is not None:
            self.payback_term_max_months = self.payback_months_max
        if self.payback_months_min is None and self.payback_term_min_months is not None:
            self.payback_months_min = self.payback_term_min_months
        if self.payback_months_max is None and self.payback_term_max_months is not None:
            self.payback_months_max = self.payback_term_max_months
        self.ticket_min, self.ticket_max = self._normalize_order(self.ticket_min, self.ticket_max)
        self.payback_months_min, self.payback_months_max = self._normalize_order(
            self.payback_months_min,
            self.payback_months_max,
        )
        self.payback_term_min_months, self.payback_term_max_months = self._normalize_order(
            self.payback_term_min_months,
            self.payback_term_max_months,
        )
        if self.payback_raw_text and not self.raw_text_snippets.get("payback_raw_text"):
            self.raw_text_snippets["payback_raw_text"] = [self.payback_raw_text]
        if self.payback_structure and not self.raw_text_snippets.get("payback_structure"):
            self.raw_text_snippets["payback_structure"] = [self.payback_structure]
        if self.raw_eligibility_criteria and not self.raw_text_snippets.get("raw_eligibility_criteria"):
            self.raw_text_snippets["raw_eligibility_criteria"] = list(self.raw_eligibility_criteria)
        self.years_in_business_min, self.years_in_business_max = self._normalize_order(
            self.years_in_business_min,
            self.years_in_business_max,
        )
        self.turnover_min, self.turnover_max = self._normalize_order(self.turnover_min, self.turnover_max)
        self.employee_min, self.employee_max = self._normalize_order(self.employee_min, self.employee_max)
        self.funding_speed_days_min, self.funding_speed_days_max = self._normalize_order(
            self.funding_speed_days_min,
            self.funding_speed_days_max,
        )
        if not self.source_urls:
            self.source_urls = [self.source_url]
        elif self.source_url not in self.source_urls:
            self.source_urls.insert(0, self.source_url)
        if not self.evidence_by_field and self.raw_text_snippets:
            self.evidence_by_field = dict(self.raw_text_snippets)
        if not self.raw_text_snippets and self.evidence_by_field:
            self.raw_text_snippets = dict(self.evidence_by_field)
        if not self.extraction_confidence_by_field and self.extraction_confidence:
            self.extraction_confidence_by_field = dict(self.extraction_confidence)
        if not self.extraction_confidence and self.extraction_confidence_by_field:
            self.extraction_confidence = dict(self.extraction_confidence_by_field)
        if not self.field_evidence and self.evidence_by_field:
            self.field_evidence = {
                field_name: [
                    FieldEvidence(
                        field_name=field_name,
                        evidence_text=snippet,
                        source_url=self.source_url,
                        source_section=field_name,
                        source_scope=self.source_scope,
                        confidence=self.extraction_confidence.get(field_name, 0.0),
                        normalized_value=None,
                        raw_value=snippet,
                    )
                    for snippet in snippets
                ]
                for field_name, snippets in self.evidence_by_field.items()
            }
        if not self.program_id:
            self.program_id = generate_program_id(self.source_domain, self.funder_name, self.program_name)
        if not self.id:
            self.id = str(uuid5(NAMESPACE_URL, f"{self.source_domain}:{self.program_id}"))
        if not self.program_slug:
            self.program_slug = slugify(self.program_name or self.program_id, max_length=80)
        if not self.funder_slug:
            self.funder_slug = slugify(self.funder_name or self.source_domain, max_length=80)
        if not self.last_scraped_at:
            self.last_scraped_at = self.scraped_at
        if not self.evidence_by_field and self.raw_text_snippets:
            self.evidence_by_field = dict(self.raw_text_snippets)
        if not self.raw_text_snippets and self.evidence_by_field:
            self.raw_text_snippets = dict(self.evidence_by_field)
        if not self.extraction_confidence_by_field and self.extraction_confidence:
            self.extraction_confidence_by_field = dict(self.extraction_confidence)
        if not self.extraction_confidence and self.extraction_confidence_by_field:
            self.extraction_confidence = dict(self.extraction_confidence_by_field)
        if not self.field_confidence and self.extraction_confidence:
            self.field_confidence = dict(self.extraction_confidence)
        if not self.extraction_confidence and self.field_confidence:
            self.extraction_confidence = dict(self.field_confidence)
        if self.payback_confidence is not None and "payback_confidence" not in self.extraction_confidence:
            self.extraction_confidence["payback_confidence"] = self.payback_confidence
        if self.raw_eligibility_criteria and "raw_eligibility_criteria" not in self.extraction_confidence:
            self.extraction_confidence["raw_eligibility_criteria"] = max(
                self.extraction_confidence.get("raw_eligibility_criteria", 0.0),
                0.88,
            )
        if not self.evidence_by_field and self.field_evidence:
            flattened: Dict[str, List[str]] = {}
            for field_name, items in self.field_evidence.items():
                flattened[field_name] = [item.evidence_text for item in items if item.evidence_text]
            self.evidence_by_field = {
                field_name: unique_preserve_order(values) for field_name, values in flattened.items() if values
            }
        if not self.raw_text_snippets and self.field_evidence:
            self.raw_text_snippets = dict(self.evidence_by_field)
        if not self.extraction_confidence_by_field and self.field_evidence:
            self.extraction_confidence_by_field = {
                field_name: max((item.confidence for item in items), default=0.0)
                for field_name, items in self.field_evidence.items()
            }
        self.validation_errors = unique_preserve_order(
            [cleaned for cleaned in (" ".join(item.split()).strip() for item in self.validation_errors) if cleaned]
        )
        if self.deadline_type == DeadlineType.FIXED_DATE and self.deadline_date is None:
            self.validation_errors = unique_preserve_order(
                [*self.validation_errors, "missing deadline date for fixed-date programme"]
            )
        if not self.program_name:
            self.validation_errors = unique_preserve_order([*self.validation_errors, "missing program_name"])
        if not self.funder_name:
            self.validation_errors = unique_preserve_order([*self.validation_errors, "missing funder_name"])
        if self.application_channel == ApplicationChannel.ONLINE_FORM and not self.application_url:
            self.validation_errors = unique_preserve_order([*self.validation_errors, "missing application_url"])
        self.field_conflicts = self._detect_field_conflicts()
        if self.field_conflicts:
            self.needs_review_reasons = unique_preserve_order([*self.needs_review_reasons, "conflicting_field_values"])
        self.status = self._derive_status()
        self.needs_review = self.needs_review or bool(self.validation_errors) or bool(self.needs_review_reasons) or bool(self.field_conflicts)
        return self

    @staticmethod
    def _normalize_order(
        minimum: Optional[float],
        maximum: Optional[float],
    ) -> tuple[Optional[float], Optional[float]]:
        if minimum is not None and maximum is not None and minimum > maximum:
            return maximum, minimum
        return minimum, maximum

    def overall_confidence(self) -> float:
        if not self.extraction_confidence:
            return 0.0
        return round(sum(self.extraction_confidence.values()) / len(self.extraction_confidence), 4)

    def _detect_field_conflicts(self) -> Dict[str, List[str]]:
        conflict_candidates = (
            "program_name",
            "funder_name",
            "page_type",
            "page_role",
            "funding_type",
            "ticket_min",
            "ticket_max",
            "program_budget_total",
            "deadline_date",
            "application_url",
            "contact_email",
            "contact_phone",
        )
        conflicts: Dict[str, List[str]] = {}
        for field_name in conflict_candidates:
            evidence_items = self.field_evidence.get(field_name) or []
            if len(evidence_items) < 2:
                continue
            values = unique_preserve_order(
                [
                    clean_text(str(item.normalized_value if item.normalized_value not in (None, "", [], {}) else item.raw_value if item.raw_value not in (None, "", [], {}) else item.evidence_text))
                    for item in evidence_items
                    if clean_text(
                        str(
                            item.normalized_value
                            if item.normalized_value not in (None, "", [], {})
                            else item.raw_value
                            if item.raw_value not in (None, "", [], {})
                            else item.evidence_text
                        )
                    )
                ]
            )
            if len(values) > 1:
                conflicts[field_name] = values
        return conflicts

    def _derive_status(self) -> ProgrammeStatus:
        notes_lower = " ".join(self.notes).lower()
        if any(term in notes_lower for term in ["archived", "expired", "closed funding programme"]):
            return ProgrammeStatus.CLOSED
        if self.deadline_type in {DeadlineType.OPEN, DeadlineType.ROLLING}:
            return ProgrammeStatus.ACTIVE
        if self.deadline_type == DeadlineType.FIXED_DATE and self.deadline_date:
            return ProgrammeStatus.CLOSED if self.deadline_date < date.today() else ProgrammeStatus.ACTIVE
        return self.status if self.status != ProgrammeStatus.UNKNOWN else ProgrammeStatus.UNKNOWN


class ExtractionResult(BaseModel):
    """Parser output for a fetched page."""

    page_url: str
    page_title: Optional[str] = None
    cleaned_text: str = ""
    section_tree: List[SectionNode] = Field(default_factory=list)
    discovered_links: List[str] = Field(default_factory=list)
    internal_links: List[str] = Field(default_factory=list)
    application_links: List[str] = Field(default_factory=list)
    document_links: List[str] = Field(default_factory=list)
    records: List[FundingProgrammeRecord] = Field(default_factory=list)
    evidence: List[FieldEvidence] = Field(default_factory=list)
    page_debug_package: Optional[PageDebugPackage] = None
    page_ai_context: Optional[PageAIContext] = None
    page_type: str = "unknown"
    notes: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class RunSummary(BaseModel):
    """Top-level crawl report written to disk for QA and telemetry."""

    run_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str = "running"
    seed_urls: List[str] = Field(default_factory=list)
    total_urls_crawled: int = 0
    pages_fetched_successfully: int = 0
    pages_failed: int = 0
    programmes_extracted: int = 0
    programmes_after_dedupe: int = 0
    records_with_missing_program_name: int = 0
    records_with_missing_funder_name: int = 0
    records_with_unknown_funding_type: int = 0
    records_with_no_application_route: int = 0
    records_with_low_confidence_extraction: int = 0
    records_with_borderline_review: int = 0
    records_rejected_for_quality: int = 0
    browser_fallback_count: int = 0
    retry_count: int = 0
    skipped_url_counts: Dict[str, int] = Field(default_factory=dict)
    queue_saturation_count: int = 0
    average_fetch_time_seconds: float = 0.0
    domain_telemetry: List[Dict[str, Any]] = Field(default_factory=list)
    low_confidence_threshold: float = 0.0
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class CrawlState(BaseModel):
    """Persistent crawl progress so runs can resume between domains."""

    run_id: Optional[str] = None
    completed_domains: List[str] = Field(default_factory=list)
    failed_domains: List[str] = Field(default_factory=list)
    last_processed_domain: Optional[str] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
