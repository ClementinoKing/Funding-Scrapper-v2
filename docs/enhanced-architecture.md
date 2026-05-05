# Enhanced Scraper Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Enhanced Scraper System                      │
│                                                                   │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐   │
│  │   Taxonomies   │  │     Models     │  │      i18n      │   │
│  │   (Pluggable)  │  │   (Generic)    │  │ (Multi-lang)   │   │
│  └────────────────┘  └────────────────┘  └────────────────┘   │
│                                                                   │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐   │
│  │   Documents    │  │    Recovery    │  │  Config v2     │   │
│  │  (Enhanced)    │  │  (Checkpoints) │  │   (Unified)    │   │
│  └────────────────┘  └────────────────┘  └────────────────┘   │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │              Existing Scraper Core (v1)                    │ │
│  │  Pipeline │ Crawler │ Parser │ Adapters │ Storage │ AI   │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Component Architecture

### 1. Taxonomy System

```
┌─────────────────────────────────────────────────────────┐
│                  Taxonomy Registry                       │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐       │
│  │ Geography  │  │  Industry  │  │  Funding   │  ...  │
│  └────────────┘  └────────────┘  └────────────┘       │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  Classification API   │
              │  - classify()         │
              │  - get_categories()   │
              │  - validate()         │
              └───────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   TaxonomyMatch       │
              │   - category          │
              │   - subcategory       │
              │   - confidence        │
              │   - matched_terms     │
              └───────────────────────┘
```

### 2. Generic Models

```
┌─────────────────────────────────────────────────────────┐
│                   Schema Registry                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ Job Listing  │  │ Real Estate  │  │   Custom     │ │
│  │   Schema     │  │    Schema    │  │   Schema     │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   GenericRecord       │
              │   - data: Dict        │
              │   - schema_name       │
              │   - confidence        │
              │   - evidence          │
              └───────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  Specialized Model    │
              │  (FundingProgramme,   │
              │   JobListing, etc.)   │
              └───────────────────────┘
```

### 3. Multi-Language Support

```
┌─────────────────────────────────────────────────────────┐
│                 Translation Registry                     │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐       │
│  │   OpenAI   │  │   NoOp     │  │   Custom   │  ...  │
│  └────────────┘  └────────────┘  └────────────┘       │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  LanguageDetector     │
              │  - detect()           │
              │  - detect_primary()   │
              │  - is_multilingual()  │
              └───────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  TranslationProvider  │
              │  - translate()        │
              │  - translate_batch()  │
              │  - detect_language()  │
              └───────────────────────┘
```

### 4. Document Processing

```
┌─────────────────────────────────────────────────────────┐
│              Document Extractor Factory                  │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐       │
│  │    PDF     │  │    Word    │  │   Excel    │  ...  │
│  │ Extractor  │  │ Extractor  │  │ Extractor  │       │
│  └────────────┘  └────────────┘  └────────────┘       │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   OCR Provider        │
              │   (Tesseract)         │
              │   - extract_text()    │
              │   - is_available()    │
              └───────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  Extracted Content    │
              │  - text               │
              │  - metadata           │
              └───────────────────────┘
```

### 5. Error Recovery

```
┌─────────────────────────────────────────────────────────┐
│              Checkpoint Manager                          │
│  ┌────────────────────────────────────────────────┐    │
│  │  CrawlCheckpoint                                │    │
│  │  - visited_urls                                 │    │
│  │  - queued_urls                                  │    │
│  │  - failed_urls                                  │    │
│  │  - statistics                                   │    │
│  └────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   Retry Strategy      │
              │   - Exponential       │
              │   - Adaptive          │
              │   - RateLimit         │
              └───────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  Resilient Execution  │
              │  - Auto-retry         │
              │  - Auto-resume        │
              │  - Error tracking     │
              └───────────────────────┘
```

## Data Flow

### Standard Scraping Flow

```
┌──────────┐
│  Seed    │
│  URLs    │
└────┬─────┘
     │
     ▼
┌──────────────────┐
│   Crawler        │
│   - Queue URLs   │
│   - Fetch pages  │
└────┬─────────────┘
     │
     ▼
┌──────────────────┐
│   Parser         │
│   - Extract HTML │
│   - Find content │
└────┬─────────────┘
     │
     ▼
┌──────────────────┐
│   AI Classifier  │
│   - Classify     │
│   - Extract data │
└────┬─────────────┘
     │
     ▼
┌──────────────────┐
│   Storage        │
│   - Save records │
│   - Export       │
└──────────────────┘
```

### Enhanced Flow with New Features

```
┌──────────┐
│  Seed    │
│  URLs    │
└────┬─────┘
     │
     ▼
┌──────────────────┐     ┌──────────────────┐
│  Checkpoint      │────▶│  Resume from     │
│  Check           │     │  last state?     │
└────┬─────────────┘     └──────────────────┘
     │
     ▼
┌──────────────────┐     ┌──────────────────┐
│   Crawler        │────▶│  Retry Strategy  │
│   - Queue URLs   │     │  (Adaptive)      │
│   - Fetch pages  │     └──────────────────┘
└────┬─────────────┘
     │
     ▼
┌──────────────────┐     ┌──────────────────┐
│   Parser         │────▶│  Language        │
│   - Extract HTML │     │  Detector        │
│   - Find content │     └──────────────────┘
└────┬─────────────┘
     │
     ▼
┌──────────────────┐     ┌──────────────────┐
│  Document        │────▶│  OCR Provider    │
│  Extractor       │     │  (if needed)     │
└────┬─────────────┘     └──────────────────┘
     │
     ▼
┌──────────────────┐     ┌──────────────────┐
│  Translation     │────▶│  Target Language │
│  (if enabled)    │     │  Content         │
└────┬─────────────┘     └──────────────────┘
     │
     ▼
┌──────────────────┐     ┌──────────────────┐
│   AI Classifier  │────▶│  Taxonomy        │
│   - Classify     │     │  Classification  │
│   - Extract data │     └──────────────────┘
└────┬─────────────┘
     │
     ▼
┌──────────────────┐     ┌──────────────────┐
│  Generic Record  │────▶│  Schema          │
│  Creation        │     │  Validation      │
└────┬─────────────┘     └──────────────────┘
     │
     ▼
┌──────────────────┐     ┌──────────────────┐
│  Checkpoint      │────▶│  Save state      │
│  Save            │     │  (every N pages) │
└────┬─────────────┘     └──────────────────┘
     │
     ▼
┌──────────────────┐
│   Storage        │
│   - Save records │
│   - Export       │
└──────────────────┘
```

## Configuration Hierarchy

```
┌─────────────────────────────────────────────────────────┐
│              EnhancedScraperSettings                     │
│                                                           │
│  ┌────────────────────────────────────────────────┐    │
│  │  LegacyScraperSettings (backward compatible)   │    │
│  │  - All existing settings preserved              │    │
│  └────────────────────────────────────────────────┘    │
│                                                           │
│  ┌────────────────────────────────────────────────┐    │
│  │  New Features                                   │    │
│  │  - Translation settings                         │    │
│  │  - OCR settings                                 │    │
│  │  - Checkpoint settings                          │    │
│  │  - Retry settings                               │    │
│  │  - Performance settings                         │    │
│  └────────────────────────────────────────────────┘    │
│                                                           │
│  ┌────────────────────────────────────────────────┐    │
│  │  Component Initialization                       │    │
│  │  - Initialize taxonomies                        │    │
│  │  - Initialize translation                       │    │
│  │  - Initialize checkpoint manager                │    │
│  │  - Initialize retry strategy                    │    │
│  │  - Initialize OCR provider                      │    │
│  └────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

## Extensibility Points

### 1. Custom Taxonomy Provider

```python
class CustomTaxonomy(TaxonomyProvider):
    def _initialize(self):
        # Load custom data
        pass
    
    def classify(self, text, context=None):
        # Custom classification logic
        return [TaxonomyMatch(...)]
    
    @property
    def taxonomy_type(self):
        return "custom"

# Register
register_taxonomy(CustomTaxonomy())
```

### 2. Custom Translation Provider

```python
class CustomTranslator(TranslationProvider):
    def _initialize(self):
        # Initialize API client
        pass
    
    def translate(self, text, source_lang, target_lang):
        # Custom translation logic
        return translated_text

# Register
registry = get_global_translation_registry()
registry.register("custom", CustomTranslator())
```

### 3. Custom Document Extractor

```python
class CustomExtractor(DocumentExtractor):
    def extract_text(self, file_path):
        # Custom extraction logic
        return text
    
    def extract_metadata(self, file_path):
        # Custom metadata extraction
        return metadata
    
    def supports_file(self, file_path):
        # Check if this extractor handles the file
        return True
```

### 4. Custom Retry Strategy

```python
class CustomRetry(RetryStrategy):
    def should_retry(self, attempt, error):
        # Custom retry logic
        return attempt < max_retries
    
    def get_delay(self, attempt):
        # Custom delay calculation
        return delay
```

### 5. Custom Record Schema

```json
{
  "schema_name": "custom_domain",
  "fields": [
    {
      "name": "field_name",
      "field_type": "string",
      "required": true
    }
  ]
}
```

## Performance Optimization

### Parallel Processing

```
┌─────────────────────────────────────────────────────────┐
│              Document Processing Pool                    │
│                                                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐│
│  │ Worker 1 │  │ Worker 2 │  │ Worker 3 │  │ Worker 4 ││
│  │  PDF     │  │  Word    │  │  Excel   │  │  PDF     ││
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘│
│                                                           │
│  Result: 2-5x faster document processing                 │
└─────────────────────────────────────────────────────────┘
```

### Caching Strategy

```
┌─────────────────────────────────────────────────────────┐
│                   Cache Layers                           │
│                                                           │
│  ┌────────────────────────────────────────────────┐    │
│  │  HTTP Response Cache (TTL: 1 hour)             │    │
│  │  - Reduces redundant requests                   │    │
│  └────────────────────────────────────────────────┘    │
│                                                           │
│  ┌────────────────────────────────────────────────┐    │
│  │  Translation Cache                              │    │
│  │  - Eliminates redundant translations            │    │
│  └────────────────────────────────────────────────┘    │
│                                                           │
│  ┌────────────────────────────────────────────────┐    │
│  │  Taxonomy Match Cache                           │    │
│  │  - Speeds up repeated classifications           │    │
│  └────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

## Deployment Architecture

### Single Machine

```
┌─────────────────────────────────────────────────────────┐
│                   Single Machine                         │
│                                                           │
│  ┌────────────────────────────────────────────────┐    │
│  │  Enhanced Scraper                               │    │
│  │  - All components in one process                │    │
│  │  - Checkpoints to local disk                    │    │
│  │  - Parallel document processing                 │    │
│  └────────────────────────────────────────────────┘    │
│                                                           │
│  ┌────────────────────────────────────────────────┐    │
│  │  Local Storage                                  │    │
│  │  - JSON/CSV output                              │    │
│  │  - Checkpoints                                  │    │
│  │  - Logs                                         │    │
│  └────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

### Production (with Supabase)

```
┌─────────────────────────────────────────────────────────┐
│                   Scraper Server                         │
│                                                           │
│  ┌────────────────────────────────────────────────┐    │
│  │  Enhanced Scraper                               │    │
│  │  - Checkpoints enabled                          │    │
│  │  - Adaptive retry                               │    │
│  │  - Translation enabled                          │    │
│  └────────────┬───────────────────────────────────┘    │
└───────────────┼─────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────┐
│                   Supabase                               │
│                                                           │
│  ┌────────────────────────────────────────────────┐    │
│  │  Database                                       │    │
│  │  - funding_programmes                           │    │
│  │  - sites                                        │    │
│  │  - scrape_runs                                  │    │
│  └────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

## Summary

The enhanced architecture provides:

✅ **Modularity** - Each component is independent and pluggable
✅ **Extensibility** - Easy to add new providers and strategies
✅ **Backward Compatibility** - Existing code works unchanged
✅ **Performance** - Parallel processing and intelligent caching
✅ **Reliability** - Checkpoints and adaptive retry
✅ **Flexibility** - Supports any domain, country, or language

All while maintaining a clean, well-documented codebase.
