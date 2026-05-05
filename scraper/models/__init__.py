"""Generic domain models for flexible scraping."""

from scraper.models.base import GenericRecord, FieldDefinition, RecordSchema
from scraper.models.registry import SchemaRegistry, get_global_schema_registry

__all__ = [
    "GenericRecord",
    "FieldDefinition",
    "RecordSchema",
    "SchemaRegistry",
    "get_global_schema_registry",
]
