"""
Enhanced Scraper Demo

This script demonstrates the new features of the enhanced scraper system.
"""

import json
from pathlib import Path

from scraper.config_v2 import EnhancedScraperSettings
from scraper.taxonomies import get_global_registry as get_taxonomy_registry
from scraper.i18n import LanguageDetector
from scraper.models import GenericRecord, RecordSchema
from scraper.recovery import CheckpointManager, CrawlCheckpoint, ExponentialBackoffRetry
from scraper.documents import get_extractor_for_file


def demo_multi_country_support():
    """Demonstrate multi-country geography support."""
    print("\n=== Multi-Country Support Demo ===\n")

    settings = EnhancedScraperSettings.from_env()
    settings.initialize_components()

    # Add a new country
    settings.add_custom_country(
        country_code="FR",
        name="France",
        provinces=["Île-de-France", "Provence-Alpes-Côte d'Azur", "Nouvelle-Aquitaine"],
        postal_pattern=r"\b\d{5}\b",
    )

    # Test geography classification
    registry = get_taxonomy_registry()
    geography = registry.get("geography")

    test_text = "This program is available in Gauteng and Western Cape provinces."
    matches = geography.classify(test_text, context={"country_code": "ZA"})

    print(f"Text: {test_text}")
    print(f"Detected locations:")
    for match in matches:
        print(f"  - {match.category}: {match.subcategory} (confidence: {match.confidence:.2f})")


def demo_language_detection():
    """Demonstrate language detection."""
    print("\n=== Language Detection Demo ===\n")

    detector = LanguageDetector()

    test_texts = [
        "This is an English text about funding opportunities.",
        "Ceci est un texte français sur les opportunités de financement.",
        "Este es un texto en español sobre oportunidades de financiación.",
        "Dies ist ein deutscher Text über Finanzierungsmöglichkeiten.",
    ]

    for text in test_texts:
        language = detector.detect_primary(text)
        all_languages = detector.detect(text, top_n=2)
        print(f"Text: {text[:50]}...")
        print(f"Primary language: {language}")
        print(f"All detected: {all_languages}")
        print()


def demo_generic_records():
    """Demonstrate generic record models."""
    print("\n=== Generic Record Models Demo ===\n")

    # Load job listing schema
    schema_path = Path(__file__).parent / "job_listings_schema.json"
    with open(schema_path) as f:
        schema_data = json.load(f)
        schema = RecordSchema.model_validate(schema_data)

    print(f"Loaded schema: {schema.schema_name} v{schema.schema_version}")
    print(f"Fields: {len(schema.fields)}")
    print(f"Required fields: {schema.required_fields}")

    # Create a generic record
    record = GenericRecord(
        record_type="job_listing",
        schema_name="job_listing",
        source_url="https://example.com/jobs/senior-python-dev",
        source_domain="example.com",
    )

    # Set fields
    record.set_field("job_title", "Senior Python Developer", confidence=0.95)
    record.set_field("company_name", "Tech Innovations Inc.", confidence=0.9)
    record.set_field("location", "San Francisco, CA", confidence=0.85)
    record.set_field("salary_min", 120000, confidence=0.7)
    record.set_field("salary_max", 180000, confidence=0.7)
    record.set_field("currency", "USD", confidence=0.95)
    record.set_field("employment_type", "Full-time", confidence=0.9)
    record.set_field("remote_allowed", True, confidence=0.85)

    print(f"\nCreated record:")
    print(f"  Job: {record.get_field('job_title')}")
    print(f"  Company: {record.get_field('company_name')}")
    print(f"  Location: {record.get_field('location')}")
    print(f"  Salary: ${record.get_field('salary_min'):,} - ${record.get_field('salary_max'):,}")
    print(f"  Remote: {record.get_field('remote_allowed')}")

    # Validate
    is_valid, errors = schema.validate_record(record.data)
    print(f"\nValidation: {'✓ Valid' if is_valid else '✗ Invalid'}")
    if errors:
        for error in errors:
            print(f"  - {error}")


def demo_checkpoint_system():
    """Demonstrate checkpoint and resume functionality."""
    print("\n=== Checkpoint System Demo ===\n")

    checkpoint_dir = Path("./demo_checkpoints")
    checkpoint_dir.mkdir(exist_ok=True)

    manager = CheckpointManager(checkpoint_dir)

    # Create a checkpoint
    checkpoint = CrawlCheckpoint(
        checkpoint_id="demo_crawl_001",
        run_id="demo_run_20260505",
        visited_urls={"https://example.com/page1", "https://example.com/page2"},
        queued_urls=[(0.9, "https://example.com/page3", 1, "seed")],
        pages_crawled=2,
        records_extracted=5,
    )

    # Save checkpoint
    path = manager.save_checkpoint(checkpoint)
    print(f"Saved checkpoint to: {path}")

    # List checkpoints
    checkpoints = manager.list_checkpoints()
    print(f"Available checkpoints: {checkpoints}")

    # Load checkpoint
    loaded = manager.load_checkpoint("demo_crawl_001")
    if loaded:
        print(f"\nLoaded checkpoint:")
        print(f"  Run ID: {loaded.run_id}")
        print(f"  Pages crawled: {loaded.pages_crawled}")
        print(f"  Records extracted: {loaded.records_extracted}")
        print(f"  Visited URLs: {len(loaded.visited_urls)}")

    # Cleanup
    manager.delete_checkpoint("demo_crawl_001")
    checkpoint_dir.rmdir()
    print("\nCheckpoint cleaned up")


def demo_retry_strategies():
    """Demonstrate retry strategies."""
    print("\n=== Retry Strategies Demo ===\n")

    # Exponential backoff
    retry = ExponentialBackoffRetry(
        max_retries=3,
        base_delay=0.1,  # Short delay for demo
        max_delay=1.0,
    )

    attempt_count = [0]

    def flaky_function():
        attempt_count[0] += 1
        if attempt_count[0] < 3:
            raise ConnectionError(f"Attempt {attempt_count[0]} failed")
        return "Success!"

    try:
        result = retry.execute(
            flaky_function,
            on_retry=lambda attempt, error: print(f"  Retry {attempt}: {error}"),
        )
        print(f"Result: {result}")
    except Exception as e:
        print(f"Failed after retries: {e}")


def demo_taxonomy_classification():
    """Demonstrate taxonomy classification."""
    print("\n=== Taxonomy Classification Demo ===\n")

    settings = EnhancedScraperSettings.from_env()
    settings.initialize_components()

    registry = get_taxonomy_registry()

    test_text = """
    This funding program supports technology startups in the agriculture sector.
    Available for businesses in Gauteng and Western Cape provinces.
    Funding can be used for equipment purchase, working capital, and expansion.
    """

    # Classify with all taxonomies
    results = registry.classify_all(test_text)

    print(f"Text: {test_text.strip()}\n")
    print("Classification results:")

    for taxonomy_type, matches in results.items():
        if matches:
            print(f"\n{taxonomy_type.upper()}:")
            for match in matches:
                if match.subcategory:
                    print(f"  - {match.category} > {match.subcategory} ({match.confidence:.2f})")
                else:
                    print(f"  - {match.category} ({match.confidence:.2f})")


def demo_document_extraction():
    """Demonstrate document extraction (if files available)."""
    print("\n=== Document Extraction Demo ===\n")

    # This is a placeholder - actual files would be needed
    print("Document extraction capabilities:")
    print("  ✓ PDF text extraction")
    print("  ✓ Word document (.docx) extraction")
    print("  ✓ Excel spreadsheet (.xlsx) extraction")
    print("  ✓ OCR for scanned documents (if Tesseract installed)")
    print("\nExample usage:")
    print("  extractor = get_extractor_for_file('document.pdf')")
    print("  text = extractor.extract_text('document.pdf')")
    print("  metadata = extractor.extract_metadata('document.pdf')")


def main():
    """Run all demos."""
    print("=" * 60)
    print("Enhanced Scraper Feature Demonstrations")
    print("=" * 60)

    try:
        demo_multi_country_support()
        demo_language_detection()
        demo_generic_records()
        demo_checkpoint_system()
        demo_retry_strategies()
        demo_taxonomy_classification()
        demo_document_extraction()

        print("\n" + "=" * 60)
        print("All demos completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\nError running demos: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
