"""NYDA site adapter for the shared funding scraper framework."""

from __future__ import annotations

import os
from typing import Optional
from urllib.parse import urlparse

from scraper.adapters.base import SiteAdapter
from scraper.schemas import DisplayCategory, FundingProgrammeRecord, FundingType, ProgrammeNature, SupportType
from scraper.utils.text import clean_text, looks_like_support_title, unique_preserve_order
from scraper.utils.urls import extract_domain, is_probably_document_url


FUNDING_ONLY = "funding_only"
FUNDING_PLUS_SUPPORT = "funding_plus_support"
SUPPORTED_MODES = {FUNDING_ONLY, FUNDING_PLUS_SUPPORT}

MAIN_DOMAIN = "nyda.gov.za"
ERP_DOMAIN = "erp.nyda.gov.za"

MAIN_PATH_PREFIX = "/products-services/"
MAIN_PORTAL_PREFIX = "/portals/0/"

NYDA_PRIORITY_TERMS = (
    "grant",
    "voucher",
    "fund",
    "funding",
    "sponsorship",
    "thusano",
    "mentorship",
    "market linkage",
    "market linkages",
    "business management training",
    "entrepreneurship",
    "support",
    "apply",
    "application",
    "products & services",
)

NYDA_EXCLUDED_TERMS = (
    "/news/",
    "/media/",
    "/press/",
    "/careers/",
    "/jobs/",
    "/vacancies/",
    "/internship/",
    "/internships/",
    "/bursary/",
    "/bursaries/",
    "/about/",
)

ERP_ALLOWED_TERMS = (
    "/faq",
    "/apply",
    "/application",
    "/register",
    "/registration",
    "/portal",
)

PROGRAMME_TERMS = (
    "grant",
    "voucher",
    "fund",
    "funding",
    "sponsorship",
    "thusano",
    "mentorship",
    "market linkage",
    "market linkages",
    "business management training",
    "support",
)

SUPPORT_TERMS = (
    "faq",
    "application form",
    "application",
    "apply",
    "register",
    "registration",
    "portal",
    "how to apply",
    "checklist",
)


def _contains_any(haystack: str, terms: tuple[str, ...]) -> bool:
    lowered = (haystack or "").lower()
    return any(term.lower() in lowered for term in terms)


def _mode_from_env(value: Optional[str] = None) -> str:
    resolved = (value or os.getenv("SCRAPER_NYDA_MODE") or FUNDING_ONLY).strip().lower().replace("-", "_")
    return resolved if resolved in SUPPORTED_MODES else FUNDING_ONLY


class NydaSiteAdapter(SiteAdapter):
    """NYDA-specific crawl and normalization rules."""

    def __init__(self, *args, crawl_mode: str = FUNDING_ONLY, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        object.__setattr__(self, "_crawl_mode", _mode_from_env(crawl_mode))

    @property
    def crawl_mode(self) -> str:
        return getattr(self, "_crawl_mode", FUNDING_ONLY)

    @classmethod
    def build(
        cls,
        crawl_mode: Optional[str] = None,
        default_seed_urls: Optional[tuple[str, ...]] = None,
    ) -> SiteAdapter:
        mode = _mode_from_env(crawl_mode)
        return cls(
            key="nyda",
            domain=MAIN_DOMAIN,
            crawl_mode=mode,
            default_seed_urls=default_seed_urls
            or (
                "https://www.nyda.gov.za/",
                "https://www.nyda.gov.za/Products-Services/NYDA-Voucher-Programme.html",
                "https://www.nyda.gov.za/Products-Services/Sponsorships-Thusano-Fund.html",
                "https://www.nyda.gov.za/Portals/0/WebSitesCreative_MyContentManager/1092/NYDA_Grant_Programme.pdf",
                "https://www.nyda.gov.za/Portals/0/Downloads/Forms/Grant%20and%20Voucher%20Application%20Form.pdf",
                "https://erp.nyda.gov.za/faq",
            ),
            include_url_terms=(
                "grant",
                "voucher",
                "fund",
                "funding",
                "sponsorship",
                "thusano",
                "mentorship",
                "market linkage",
                "market linkages",
                "business management training",
                "entrepreneurship",
                "products-services",
                "apply",
                "application",
            ),
            exclude_url_terms=NYDA_EXCLUDED_TERMS,
            strict_path_prefixes=False,
            allow_root_url=True,
            discovery_terms=NYDA_PRIORITY_TERMS,
            content_selectors=(
                "main",
                "article",
                ".content",
                ".single-page-content",
                ".entry-content",
                ".products-services",
            ),
            candidate_selectors=(
                "article",
                "section",
                "div.card",
                ".card",
                ".programme-card",
                ".single-page-content",
                ".entry-content",
            ),
            parent_page_terms=(
                "products & services",
                "products and services",
                "nyda grant programme",
                "voucher programme",
                "sponsorships",
                "thusano fund",
            ),
            child_page_terms=(
                "mentorship",
                "market linkage",
                "market linkages",
                "business management training",
                "how to apply",
                "application form",
                "faq",
            ),
            support_page_terms=(
                "how to apply",
                "application form",
                "faq",
                "checklist",
                "portal",
                "register",
                "application",
                "guidelines",
            ),
            merge_aliases={
                "nyda voucher programme": "voucher programme",
                "sponsorships & thusano fund": "thusano fund",
                "products & services": "",
            },
            playwright_required_by_default=False,
            notes=(
                "Treat nyda.gov.za as the primary programme source.",
                "Use erp.nyda.gov.za only for FAQ and application-route metadata.",
                f"NYDA mode: {mode}.",
            ),
        )

    def should_allow_url(self, url: str, anchor_text: str = "") -> bool:
        parsed = urlparse(url)
        domain = extract_domain(url)
        path = (parsed.path or "").lower()
        haystack = " ".join([url, anchor_text]).lower()

        if not self.matches_domain(domain):
            return False
        if _contains_any(haystack, NYDA_EXCLUDED_TERMS):
            return False

        if domain == extract_domain(ERP_DOMAIN):
            if _contains_any(haystack, ERP_ALLOWED_TERMS) or any(term in path for term in ERP_ALLOWED_TERMS):
                return True
            return False

        if path in {"", "/"}:
            return True
        if path.startswith(MAIN_PATH_PREFIX) or path.startswith(MAIN_PORTAL_PREFIX):
            return True
        if is_probably_document_url(url) and _contains_any(haystack, PROGRAMME_TERMS + SUPPORT_TERMS):
            return True
        if _contains_any(haystack, NYDA_PRIORITY_TERMS) and not _contains_any(haystack, ("third-party", "external")):
            return True
        return False

    def should_promote_records(self, page_type: str) -> bool:
        if page_type == "support-document":
            return False
        if page_type == "supporting_or_complementary_programme_page":
            return self.crawl_mode == FUNDING_PLUS_SUPPORT
        return True

    def should_promote_record(self, record: FundingProgrammeRecord, page_type: str) -> bool:
        if not self.should_promote_records(page_type):
            return False
        if page_type == "application_support_page" and self.crawl_mode == FUNDING_ONLY:
            combined = clean_text(" ".join([record.program_name or "", record.source_page_title or "", " ".join(record.notes or [])])).lower()
            if _contains_any(
                combined,
                (
                    "mentorship",
                    "market linkage",
                    "market linkages",
                    "business management training",
                    "business support",
                ),
            ):
                return False
        return True

    def page_role(
        self,
        page_url: str,
        page_title: Optional[str],
        text: str,
        record_count: int,
        candidate_block_count: int,
        internal_link_count: int,
        detail_link_count: int,
        application_link_count: int,
        document_link_count: int,
    ) -> str:
        lowered = " ".join([(page_url or "").lower(), (page_title or "").lower(), (text or "").lower()])
        path = urlparse(page_url).path.lower()
        domain = extract_domain(page_url)

        if domain == extract_domain(ERP_DOMAIN):
            if _contains_any(lowered, SUPPORT_TERMS) or application_link_count or document_link_count:
                return "application_support_page"
            return "application_support_page"

        if is_probably_document_url(page_url):
            if _contains_any(lowered, ("application form", "checklist", "faq", "how to apply", "register", "portal")):
                return "application_support_page"
            if _contains_any(lowered, PROGRAMME_TERMS):
                return "pdf_programme_page"
            if looks_like_support_title(page_title or ""):
                return "application_support_page"
            return "support-document"

        if path in {"", "/"} or _contains_any(lowered, ("products & services", "products and services")):
            if record_count > 1 or candidate_block_count > 1 or internal_link_count > 5:
                return "programme_index_page"
            if _contains_any(lowered, PROGRAMME_TERMS):
                return "programme_index_page"

        if _contains_any(lowered, ("mentorship", "market linkage", "market linkages", "business management training")):
            return "supporting_or_complementary_programme_page"

        if path.startswith(MAIN_PATH_PREFIX):
            if _contains_any(lowered, ("voucher", "grant", "thusano", "fund", "sponsorship", "programme")):
                return "programme_page"
            if application_link_count or document_link_count:
                return "application_support_page" if _contains_any(lowered, ("application", "faq", "form", "checklist")) else "programme_page"

        if _contains_any(lowered, ("faq", "how to apply", "application form", "portal", "register", "application")):
            return "application_support_page"

        if candidate_block_count > 1:
            return "programme_index_page"
        if record_count > 1:
            return "programme_index_page"
        if detail_link_count > 0:
            return "programme_page"
        if application_link_count or document_link_count:
            return "application_support_page"
        return super().page_role(
            page_url=page_url,
            page_title=page_title,
            text=text,
            record_count=record_count,
            candidate_block_count=candidate_block_count,
            internal_link_count=internal_link_count,
            detail_link_count=detail_link_count,
            application_link_count=application_link_count,
            document_link_count=document_link_count,
        )

    def normalize_record(
        self,
        record: FundingProgrammeRecord,
        *,
        page_type: str,
        page_url: str,
        page_title: Optional[str] = None,
    ) -> FundingProgrammeRecord:
        combined = clean_text(" ".join([record.program_name or "", record.source_page_title or "", page_title or "", page_url]))
        lowered = combined.lower()

        support_type = record.support_type
        programme_nature = record.programme_nature
        display_category = record.display_category
        funding_type = record.funding_type

        if any(term in lowered for term in ("mentorship",)):
            support_type = SupportType.MENTORSHIP
            programme_nature = ProgrammeNature.NON_FINANCIAL_SUPPORT
            display_category = DisplayCategory.SUPPORT
            funding_type = FundingType.OTHER
        elif any(term in lowered for term in ("market linkage", "market linkages")):
            support_type = SupportType.MARKET_LINKAGE
            programme_nature = ProgrammeNature.NON_FINANCIAL_SUPPORT
            display_category = DisplayCategory.SUPPORT
            funding_type = FundingType.OTHER
        elif any(term in lowered for term in ("business management training",)):
            support_type = SupportType.BUSINESS_MANAGEMENT_TRAINING
            programme_nature = ProgrammeNature.NON_FINANCIAL_SUPPORT
            display_category = DisplayCategory.SUPPORT
            funding_type = FundingType.OTHER
        elif any(term in lowered for term in ("voucher",)):
            support_type = SupportType.VOUCHER
            programme_nature = ProgrammeNature.VOUCHER_SUPPORT
            display_category = DisplayCategory.FUNDING
            if funding_type == FundingType.UNKNOWN:
                funding_type = FundingType.OTHER
        elif page_type == "application_support_page":
            support_type = support_type if support_type != SupportType.UNKNOWN else SupportType.APPLICATION_SUPPORT
            programme_nature = ProgrammeNature.NON_FINANCIAL_SUPPORT
            display_category = DisplayCategory.SUPPORT
            if funding_type == FundingType.UNKNOWN:
                funding_type = FundingType.OTHER
        elif page_type == "supporting_or_complementary_programme_page":
            support_type = support_type if support_type != SupportType.UNKNOWN else SupportType.BUSINESS_SUPPORT
            programme_nature = ProgrammeNature.NON_FINANCIAL_SUPPORT
            display_category = DisplayCategory.SUPPORT
            if funding_type == FundingType.UNKNOWN:
                funding_type = FundingType.OTHER
        elif any(term in lowered for term in ("grant", "fund", "sponsorship", "thusano")):
            if programme_nature == ProgrammeNature.UNKNOWN:
                programme_nature = ProgrammeNature.DIRECT_FUNDING
            if display_category == DisplayCategory.UNKNOWN:
                display_category = DisplayCategory.FUNDING
            if funding_type == FundingType.UNKNOWN and any(term in lowered for term in ("sponsorship", "thusano")):
                funding_type = FundingType.OTHER
        elif page_type in {"programme_page", "pdf_programme_page", "programme_index_page"}:
            if funding_type == FundingType.UNKNOWN and any(term in lowered for term in ("grant", "fund", "sponsorship", "thusano")):
                funding_type = FundingType.OTHER

        if programme_nature == ProgrammeNature.UNKNOWN and funding_type != FundingType.UNKNOWN:
            programme_nature = ProgrammeNature.DIRECT_FUNDING
        if display_category == DisplayCategory.UNKNOWN:
            display_category = DisplayCategory.FUNDING if programme_nature != ProgrammeNature.NON_FINANCIAL_SUPPORT else DisplayCategory.SUPPORT

        if support_type == SupportType.UNKNOWN and page_type == "application_support_page":
            support_type = SupportType.APPLICATION_SUPPORT

        if page_type == "programme_index_page" and funding_type == FundingType.UNKNOWN:
            funding_type = FundingType.OTHER if "voucher" in lowered or "support" in lowered else funding_type

        return record.model_copy(
            update={
                "programme_nature": programme_nature,
                "display_category": display_category,
                "support_type": support_type,
                "funding_type": funding_type,
            }
        )
