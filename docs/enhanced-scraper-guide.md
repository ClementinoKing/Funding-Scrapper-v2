# Enhanced Scraper Guide

## Overview

The enhanced scraper system provides a flexible, domain-agnostic architecture for scraping different types of websites. Key improvements include:

1. **Pluggable Taxonomies** - Easily add new classification systems
2. **Generic Domain Models** - Adapt to any data structure
3. **Multi-Language Support** - Automatic translation and language detection
4. **Enhanced Document Processing** - PDF, Word, Excel with OCR support
5. **Error Recovery** - Checkpoints and adaptive retry strategies
6. **Better Performance** - Parallel processing and intelligent caching

## Quick Start

### Basic Usage (Backward Compatible)

The enhanced scraper maintains full backward compatibility:

```python
from scraper.pipeline import ScraperPipeline
from scraper.config import ScraperSettings

settings = ScraperSettings.from_env()
pipeline = ScraperPipeline(settings)

# Works exactly as before
summary = pipeline.run(["https://example.com/funding"])
```

### Enhanced Usage

```python
from scraper.config_v2 import EnhancedScraperSettings
from scraper.pipeline import ScraperPipeline

# Load enhanced settings
settings = EnhancedScraperSettings.from_env()
settings.initialize_components()

# Create pipeline with enhanced features
pipeline = ScraperPipeline(settings.legacy_settings)

# Run with automatic checkpointing and retry
summary = pipeline.run(["https://example.com"])
```

## Feature Guides

### 1. Multi-Country Support

Add support for new countries dynamically:

```python
from scraper.config_v2 import EnhancedScraperSettings

settings = EnhancedScraperSettings.from_env()
settings.initialize_components()

# Add a new country
settings.add_custom_country(
    country_code="FR",
    name="France",
    provinces=["Île-de-France", "Provence", "Brittany", ...],
    postal_pattern=r"\b\d{5}\b"
)
```

Or load from configuration file:

```python
settings.load_taxonomy_from_file(
    "geography",
    Path("scraper/examples/multi_country_config.json")
)
```

### 2. Multi-Language Support

Enable automatic translation:

```bash
# Set environment variables
export SCRAPER_ENABLE_TRANSLATION=true
export SCRAPER_TRANSLATION_PROVIDER=openai
export OPENAI_API_KEY=your_api_key
export SCRAPER_TARGET_LANGUAGE=en
```

Or configure programmatically:

```python
settings = EnhancedScraperSettings.from_env()
settings.enable_translation = True
settings.translation_provider = "openai"
settings.translation_api_key = "your_api_key"
settings.target_language = "en"
settings.initialize_components()
```

Detect language in content:

```python
from scraper.i18n import LanguageDetector

detector = LanguageDetector()
language = detector.detect_primary("Bonjour le monde")
# Returns: "fr"

# Check for multilingual content
is_multi = detector.is_multilingual(text)
```

### 3. Enhanced Document Processing

Enable OCR for scanned PDFs:

```bash
export SCRAPER_ENABLE_OCR=true
export SCRAPER_OCR_LANGUAGE=eng
```

Extract from Word and Excel:

```python
from scraper.documents import get_extractor_for_file

extractor = get_extractor_for_file("document.docx")
text = extractor.extract_text("document.docx")
metadata = extractor.extract_metadata("document.docx")
```

### 4. Checkpoint and Resume

Enable automatic checkpointing:

```bash
export SCRAPER_ENABLE_CHECKPOINTS=true
export SCRAPER_CHECKPOINT_INTERVAL=10  # Save every 10 pages
export SCRAPER_AUTO_RESUME=true
```

Manual checkpoint management:

```python
from scraper.recovery import CheckpointManager, CrawlCheckpoint

manager = CheckpointManager(Path("./checkpoints"))

# Save checkpoint
checkpoint = CrawlCheckpoint(
    checkpoint_id="crawl_001",
    run_id="run_20260505",
    visited_urls={"https://example.com/page1"},
    pages_crawled=10
)
manager.save_checkpoint(checkpoint)

# Resume from checkpoint
checkpoint = manager.get_latest_checkpoint(run_id="run_20260505")
if checkpoint:
    visited_urls = checkpoint.visited_urls
```

### 5. Adaptive Retry Strategies

Configure retry behavior:

```bash
export SCRAPER_RETRY_STRATEGY=adaptive  # or exponential, rate_limit
export SCRAPER_MAX_RETRIES=5
export SCRAPER_RETRY_BASE_DELAY=1.0
export SCRAPER_RETRY_MAX_DELAY=120.0
```

Use retry strategies directly:

```python
from scraper.recovery import AdaptiveRetry, ExponentialBackoffRetry

# Exponential backoff
retry = ExponentialBackoffRetry(
    max_retries=3,
    base_delay=1.0,
    max_delay=60.0
)

result = retry.execute(lambda: fetch_url("https://example.com"))

# Adaptive retry (learns from failures)
adaptive = AdaptiveRetry(max_retries=5)
result = adaptive.execute(
    lambda: fetch_url("https://example.com"),
    on_retry=lambda attempt, error: print(f"Retry {attempt}: {error}")
)
```

### 6. Custom Taxonomies

Create custom classification systems:

```python
from scraper.taxonomies import TaxonomyProvider, TaxonomyMatch, register_taxonomy

class ProductCategoryTaxonomy(TaxonomyProvider):
    def _initialize(self):
        self.categories = {
            "Electronics": ["laptop", "phone", "tablet", "computer"],
            "Clothing": ["shirt", "pants", "dress", "shoes"],
            "Food": ["snacks", "beverages", "groceries"]
        }
    
    def classify(self, text, context=None):
        matches = []
        for category, keywords in self.categories.items():
            matched = [kw for kw in keywords if kw in text.lower()]
            if matched:
                matches.append(TaxonomyMatch(
                    category=category,
                    confidence=0.9,
                    matched_terms=matched
                ))
        return matches
    
    def get_categories(self):
        return list(self.categories.keys())
    
    def get_subcategories(self, category):
        return []
    
    def validate(self, category, subcategory=None):
        return category in self.categories
    
    @property
    def taxonomy_type(self):
        return "product_category"

# Register the taxonomy
register_taxonomy(ProductCategoryTaxonomy())
```

### 7. Generic Record Models

Adapt to different domains:

```python
from scraper.models import GenericRecord, RecordSchema, FieldDefinition, FieldType
import json

# Load schema from file
with open("scraper/examples/job_listings_schema.json") as f:
    schema_data = json.load(f)
    schema = RecordSchema.model_validate(schema_data)

# Create a generic record
record = GenericRecord(
    record_type="job_listing",
    schema_name="job_listing",
    source_url="https://example.com/job/123",
    source_domain="example.com"
)

# Set fields
record.set_field("job_title", "Senior Python Developer", confidence=0.95)
record.set_field("company_name", "Tech Corp", confidence=0.9)
record.set_field("salary_min", 80000, confidence=0.7)
record.set_field("remote_allowed", True, confidence=0.85)

# Validate against schema
is_valid, errors = schema.validate_record(record.data)
```

### 8. Domain-Specific Adapters

Create adapters for different domains:

```python
from scraper.adapters.base import SiteAdapter

# Job board adapter
job_adapter = SiteAdapter(
    key="job_board",
    domain="jobs.example.com",
    allowed_path_prefixes=["/jobs/", "/careers/"],
    include_url_terms=["job", "career", "position", "vacancy"],
    exclude_url_terms=["login", "register", "profile"],
    content_selectors=[".job-listing", ".position-details"],
    candidate_selectors=[".job-card", ".position-item"],
)

# Real estate adapter
realestate_adapter = SiteAdapter(
    key="real_estate",
    domain="properties.example.com",
    allowed_path_prefixes=["/properties/", "/listings/"],
    include_url_terms=["property", "house", "apartment", "for-sale", "for-rent"],
    content_selectors=[".property-details", ".listing-content"],
    candidate_selectors=[".property-card", ".listing-item"],
)
```

## Environment Variables Reference

### Translation
- `SCRAPER_ENABLE_TRANSLATION` - Enable translation (true/false)
- `SCRAPER_TRANSLATION_PROVIDER` - Provider (openai, noop)
- `SCRAPER_TRANSLATION_API_KEY` - API key for translation
- `SCRAPER_TARGET_LANGUAGE` - Target language code (en, es, fr, etc.)
- `SCRAPER_AUTO_DETECT_LANGUAGE` - Auto-detect source language (true/false)

### Document Processing
- `SCRAPER_ENABLE_OCR` - Enable OCR for scanned documents (true/false)
- `SCRAPER_OCR_LANGUAGE` - OCR language (eng, fra, spa, etc.)
- `SCRAPER_ENABLE_WORD` - Enable Word document extraction (true/false)
- `SCRAPER_ENABLE_EXCEL` - Enable Excel extraction (true/false)

### Checkpoints
- `SCRAPER_ENABLE_CHECKPOINTS` - Enable checkpointing (true/false)
- `SCRAPER_CHECKPOINT_INTERVAL` - Pages between checkpoints (default: 10)
- `SCRAPER_CHECKPOINT_DIR` - Checkpoint directory path
- `SCRAPER_AUTO_RESUME` - Auto-resume from checkpoint (true/false)

### Retry
- `SCRAPER_RETRY_STRATEGY` - Strategy (exponential, adaptive, rate_limit)
- `SCRAPER_MAX_RETRIES` - Maximum retry attempts (default: 3)
- `SCRAPER_RETRY_BASE_DELAY` - Base delay in seconds (default: 1.0)
- `SCRAPER_RETRY_MAX_DELAY` - Maximum delay in seconds (default: 60.0)

### Performance
- `SCRAPER_ENABLE_CACHING` - Enable response caching (true/false)
- `SCRAPER_CACHE_TTL` - Cache TTL in seconds (default: 3600)
- `SCRAPER_PARALLEL_DOCS` - Parallel document processing (true/false)
- `SCRAPER_MAX_DOC_WORKERS` - Max document workers (default: 4)

### Domain
- `SCRAPER_RECORD_SCHEMA` - Record schema name (default: funding_programme)

## Migration Guide

### From Legacy to Enhanced

1. **Update imports:**
```python
# Old
from scraper.config import ScraperSettings

# New (backward compatible)
from scraper.config_v2 import EnhancedScraperSettings
```

2. **Initialize components:**
```python
settings = EnhancedScraperSettings.from_env()
settings.initialize_components()  # Initialize new features
```

3. **Use legacy settings for pipeline:**
```python
pipeline = ScraperPipeline(settings.legacy_settings)
```

4. **Enable new features gradually:**
```python
# Start with checkpoints
settings.enable_checkpoints = True

# Add translation when needed
settings.enable_translation = True

# Enable OCR for document-heavy sites
settings.enable_ocr = True
```

## Performance Tips

1. **Enable caching** for repeated crawls of the same site
2. **Use checkpoints** for long-running crawls
3. **Enable parallel document processing** for document-heavy sites
4. **Use adaptive retry** for unreliable sites
5. **Configure domain concurrency** for multi-site crawls
6. **Tune checkpoint interval** based on crawl speed

## Troubleshooting

### Translation not working
- Verify `OPENAI_API_KEY` is set
- Check `SCRAPER_ENABLE_TRANSLATION=true`
- Ensure translation provider is initialized

### OCR not extracting text
- Install Tesseract: `brew install tesseract` (macOS) or `apt-get install tesseract-ocr` (Linux)
- Install Python package: `pip install pytesseract pdf2image`
- Verify `SCRAPER_ENABLE_OCR=true`

### Checkpoints not saving
- Check `SCRAPER_CHECKPOINT_DIR` is writable
- Verify `SCRAPER_ENABLE_CHECKPOINTS=true`
- Check disk space

### High memory usage
- Reduce `SCRAPER_MAX_DOC_WORKERS`
- Decrease `SCRAPER_CHECKPOINT_INTERVAL`
- Disable caching if not needed
- Reduce `max_pages` per domain

## Examples

See the `scraper/examples/` directory for:
- `multi_country_config.json` - Multi-country geography setup
- `job_listings_schema.json` - Job board scraping schema
- `real_estate_schema.json` - Real estate scraping schema

## Next Steps

1. Review the example schemas for your domain
2. Configure taxonomies for your target countries/industries
3. Set up translation if scraping multi-language sites
4. Enable checkpoints for production crawls
5. Monitor performance and tune settings
