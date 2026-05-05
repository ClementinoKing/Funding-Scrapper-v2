"""Enhanced configuration system with pluggable components."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from scraper.config import ScraperSettings as LegacyScraperSettings
from scraper.taxonomies import (
    GeographyTaxonomy,
    IndustryTaxonomy,
    FundingTaxonomy,
    get_global_registry as get_taxonomy_registry,
)
from scraper.i18n import LanguageDetector, get_global_translation_registry
from scraper.i18n.translator import OpenAITranslationProvider
from scraper.documents.ocr import TesseractOCRProvider, NoOpOCRProvider
from scraper.recovery import CheckpointManager, ExponentialBackoffRetry, AdaptiveRetry


@dataclass
class EnhancedScraperSettings:
    """Enhanced scraper settings with pluggable components."""

    # Legacy settings (for backward compatibility)
    legacy_settings: LegacyScraperSettings = field(default_factory=LegacyScraperSettings.from_env)

    # Multi-language support
    enable_translation: bool = False
    translation_provider: str = "noop"
    translation_api_key: Optional[str] = None
    target_language: str = "en"
    auto_detect_language: bool = True

    # Enhanced document processing
    enable_ocr: bool = False
    ocr_language: str = "eng"
    enable_word_extraction: bool = True
    enable_excel_extraction: bool = True

    # Checkpoint and recovery
    enable_checkpoints: bool = True
    checkpoint_interval: int = 10  # Save checkpoint every N pages
    checkpoint_dir: Optional[Path] = None
    auto_resume: bool = True

    # Retry strategies
    retry_strategy: str = "exponential"  # exponential, adaptive, rate_limit
    max_retries: int = 3
    retry_base_delay: float = 1.0
    retry_max_delay: float = 60.0

    # Taxonomy configuration
    taxonomy_config: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    custom_taxonomies: Dict[str, str] = field(default_factory=dict)

    # Performance optimizations
    enable_caching: bool = True
    cache_ttl_seconds: int = 3600
    parallel_document_processing: bool = True
    max_document_workers: int = 4

    # Domain-specific settings
    record_schema: str = "funding_programme"  # Can be overridden for different domains
    custom_field_extractors: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls, legacy_settings: Optional[LegacyScraperSettings] = None) -> "EnhancedScraperSettings":
        """Create settings from environment variables."""
        import os

        legacy = legacy_settings or LegacyScraperSettings.from_env()

        # Translation settings
        enable_translation = os.getenv("SCRAPER_ENABLE_TRANSLATION", "false").lower() == "true"
        translation_provider = os.getenv("SCRAPER_TRANSLATION_PROVIDER", "noop")
        translation_api_key = os.getenv("OPENAI_API_KEY") or os.getenv("SCRAPER_TRANSLATION_API_KEY")
        target_language = os.getenv("SCRAPER_TARGET_LANGUAGE", "en")
        auto_detect_language = os.getenv("SCRAPER_AUTO_DETECT_LANGUAGE", "true").lower() == "true"

        # OCR settings
        enable_ocr = os.getenv("SCRAPER_ENABLE_OCR", "false").lower() == "true"
        ocr_language = os.getenv("SCRAPER_OCR_LANGUAGE", "eng")

        # Document extraction
        enable_word_extraction = os.getenv("SCRAPER_ENABLE_WORD", "true").lower() == "true"
        enable_excel_extraction = os.getenv("SCRAPER_ENABLE_EXCEL", "true").lower() == "true"

        # Checkpoint settings
        enable_checkpoints = os.getenv("SCRAPER_ENABLE_CHECKPOINTS", "true").lower() == "true"
        checkpoint_interval = int(os.getenv("SCRAPER_CHECKPOINT_INTERVAL", "10"))
        checkpoint_dir_str = os.getenv("SCRAPER_CHECKPOINT_DIR")
        checkpoint_dir = Path(checkpoint_dir_str) if checkpoint_dir_str else legacy.output_path / "checkpoints"
        auto_resume = os.getenv("SCRAPER_AUTO_RESUME", "true").lower() == "true"

        # Retry settings
        retry_strategy = os.getenv("SCRAPER_RETRY_STRATEGY", "exponential")
        max_retries = int(os.getenv("SCRAPER_MAX_RETRIES", "3"))
        retry_base_delay = float(os.getenv("SCRAPER_RETRY_BASE_DELAY", "1.0"))
        retry_max_delay = float(os.getenv("SCRAPER_RETRY_MAX_DELAY", "60.0"))

        # Performance settings
        enable_caching = os.getenv("SCRAPER_ENABLE_CACHING", "true").lower() == "true"
        cache_ttl_seconds = int(os.getenv("SCRAPER_CACHE_TTL", "3600"))
        parallel_document_processing = os.getenv("SCRAPER_PARALLEL_DOCS", "true").lower() == "true"
        max_document_workers = int(os.getenv("SCRAPER_MAX_DOC_WORKERS", "4"))

        # Domain settings
        record_schema = os.getenv("SCRAPER_RECORD_SCHEMA", "funding_programme")

        return cls(
            legacy_settings=legacy,
            enable_translation=enable_translation,
            translation_provider=translation_provider,
            translation_api_key=translation_api_key,
            target_language=target_language,
            auto_detect_language=auto_detect_language,
            enable_ocr=enable_ocr,
            ocr_language=ocr_language,
            enable_word_extraction=enable_word_extraction,
            enable_excel_extraction=enable_excel_extraction,
            enable_checkpoints=enable_checkpoints,
            checkpoint_interval=checkpoint_interval,
            checkpoint_dir=checkpoint_dir,
            auto_resume=auto_resume,
            retry_strategy=retry_strategy,
            max_retries=max_retries,
            retry_base_delay=retry_base_delay,
            retry_max_delay=retry_max_delay,
            enable_caching=enable_caching,
            cache_ttl_seconds=cache_ttl_seconds,
            parallel_document_processing=parallel_document_processing,
            max_document_workers=max_document_workers,
            record_schema=record_schema,
        )

    def initialize_components(self) -> None:
        """Initialize all pluggable components."""
        # Initialize taxonomies
        self._initialize_taxonomies()

        # Initialize translation
        if self.enable_translation:
            self._initialize_translation()

        # Initialize checkpoint manager
        if self.enable_checkpoints and self.checkpoint_dir:
            self.checkpoint_manager = CheckpointManager(self.checkpoint_dir)

        # Initialize retry strategy
        self.retry_handler = self._create_retry_strategy()

        # Initialize OCR provider
        if self.enable_ocr:
            self.ocr_provider = TesseractOCRProvider(language=self.ocr_language)
        else:
            self.ocr_provider = NoOpOCRProvider()

        # Initialize language detector
        if self.auto_detect_language:
            self.language_detector = LanguageDetector()

    def _initialize_taxonomies(self) -> None:
        """Initialize taxonomy providers."""
        registry = get_taxonomy_registry()

        # Geography taxonomy
        geography_config = self.taxonomy_config.get("geography", {})
        if not geography_config:
            # Use legacy settings
            geography_config = {
                "countries": {
                    "ZA": {
                        "name": "South Africa",
                        "provinces": self.legacy_settings.province_list,
                        "municipalities": self.legacy_settings.municipality_list,
                        "postal_pattern": r"\b\d{4}\b",
                    }
                }
            }

        geography_taxonomy = GeographyTaxonomy(config=geography_config)
        registry.register("geography", geography_taxonomy)

        # Industry taxonomy
        industry_config = self.taxonomy_config.get("industry", {})
        if not industry_config:
            industry_config = {
                "industry_keywords": self.legacy_settings.industry_taxonomy,
                "industry_hierarchy": {},
            }

        industry_taxonomy = IndustryTaxonomy(config=industry_config)
        registry.register("industry", industry_taxonomy)

        # Funding taxonomy
        funding_config = self.taxonomy_config.get("funding", {})
        if not funding_config:
            funding_config = {
                "use_of_funds_keywords": self.legacy_settings.use_of_funds_taxonomy,
                "ownership_target_keywords": self.legacy_settings.ownership_target_keywords,
                "entity_type_keywords": self.legacy_settings.entity_type_keywords,
                "certification_keywords": self.legacy_settings.certification_keywords,
            }

        funding_taxonomy = FundingTaxonomy(config=funding_config)
        registry.register("funding", funding_taxonomy)

    def _initialize_translation(self) -> None:
        """Initialize translation provider."""
        registry = get_global_translation_registry()

        if self.translation_provider == "openai" and self.translation_api_key:
            provider = OpenAITranslationProvider(
                config={
                    "api_key": self.translation_api_key,
                    "model": "gpt-4o-mini",
                }
            )
            registry.register("openai", provider, set_as_default=True)

    def _create_retry_strategy(self):
        """Create retry strategy based on configuration."""
        if self.retry_strategy == "adaptive":
            return AdaptiveRetry(
                max_retries=self.max_retries,
                base_delay=self.retry_base_delay,
                max_delay=self.retry_max_delay,
            )
        else:  # exponential (default)
            return ExponentialBackoffRetry(
                max_retries=self.max_retries,
                base_delay=self.retry_base_delay,
                max_delay=self.retry_max_delay,
            )

    def load_taxonomy_from_file(self, taxonomy_type: str, file_path: Path) -> None:
        """Load taxonomy configuration from a JSON file."""
        with open(file_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        self.taxonomy_config[taxonomy_type] = config

    def add_custom_country(
        self,
        country_code: str,
        name: str,
        provinces: Optional[List[str]] = None,
        municipalities: Optional[List[str]] = None,
        postal_pattern: Optional[str] = None,
    ) -> None:
        """Add a custom country to geography taxonomy."""
        registry = get_taxonomy_registry()
        geography = registry.get("geography")
        if isinstance(geography, GeographyTaxonomy):
            geography.add_country(
                country_code=country_code,
                name=name,
                provinces=provinces,
                municipalities=municipalities,
                postal_pattern=postal_pattern,
            )
