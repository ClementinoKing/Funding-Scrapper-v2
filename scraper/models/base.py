"""Base generic record model for domain-agnostic scraping."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class FieldType(str, Enum):
    """Supported field types for generic records."""

    STRING = "string"
    TEXT = "text"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    URL = "url"
    EMAIL = "email"
    PHONE = "phone"
    LIST_STRING = "list_string"
    LIST_URL = "list_url"
    DICT = "dict"
    JSON = "json"


class FieldDefinition(BaseModel):
    """Definition of a field in a generic record schema."""

    name: str
    field_type: FieldType
    required: bool = False
    default: Optional[Any] = None
    description: Optional[str] = None
    validation_rules: Dict[str, Any] = Field(default_factory=dict)
    extraction_hints: List[str] = Field(default_factory=list)
    ai_prompt: Optional[str] = None


class RecordSchema(BaseModel):
    """Schema definition for a generic record type."""

    schema_name: str
    schema_version: str = "1.0.0"
    description: Optional[str] = None
    fields: List[FieldDefinition] = Field(default_factory=list)
    required_fields: List[str] = Field(default_factory=list)
    unique_fields: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def get_field(self, field_name: str) -> Optional[FieldDefinition]:
        """Get a field definition by name."""
        for field in self.fields:
            if field.name == field_name:
                return field
        return None

    def validate_record(self, record: Dict[str, Any]) -> tuple[bool, List[str]]:
        """Validate a record against this schema."""
        errors: List[str] = []

        # Check required fields
        for field_name in self.required_fields:
            if field_name not in record or record[field_name] is None:
                errors.append(f"Required field '{field_name}' is missing")

        # Check field types
        for field_def in self.fields:
            if field_def.name in record:
                value = record[field_def.name]
                if value is not None:
                    # Basic type checking
                    if field_def.field_type == FieldType.INTEGER and not isinstance(value, int):
                        errors.append(f"Field '{field_def.name}' should be integer, got {type(value).__name__}")
                    elif field_def.field_type == FieldType.FLOAT and not isinstance(value, (int, float)):
                        errors.append(f"Field '{field_def.name}' should be float, got {type(value).__name__}")
                    elif field_def.field_type == FieldType.BOOLEAN and not isinstance(value, bool):
                        errors.append(f"Field '{field_def.name}' should be boolean, got {type(value).__name__}")
                    elif field_def.field_type in {FieldType.LIST_STRING, FieldType.LIST_URL} and not isinstance(value, list):
                        errors.append(f"Field '{field_def.name}' should be list, got {type(value).__name__}")

        return len(errors) == 0, errors


class GenericRecord(BaseModel):
    """Generic record model that can adapt to any domain."""

    # Core identification fields
    id: str = Field(default_factory=lambda: str(uuid4()))
    record_type: str = "generic"
    schema_name: Optional[str] = None
    schema_version: str = "1.0.0"

    # Source tracking
    source_url: str
    source_urls: List[str] = Field(default_factory=list)
    source_domain: str
    source_page_title: Optional[str] = None

    # Timestamps
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Generic data storage
    data: Dict[str, Any] = Field(default_factory=dict)
    raw_data: Dict[str, Any] = Field(default_factory=dict)

    # Extraction metadata
    extraction_confidence: Dict[str, float] = Field(default_factory=dict)
    evidence_by_field: Dict[str, List[str]] = Field(default_factory=dict)
    field_sources: Dict[str, str] = Field(default_factory=dict)

    # Quality and review
    quality_score: float = 0.0
    needs_review: bool = False
    validation_errors: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)

    # Adapter and processing info
    site_adapter: Optional[str] = None
    page_type: Optional[str] = None
    ai_enriched: bool = False

    @field_validator("source_urls", mode="before")
    @classmethod
    def _normalize_source_urls(cls, value: Any) -> List[str]:
        """Normalize source URLs."""
        if value is None:
            return []
        if isinstance(value, str):
            return [value] if value else []
        return [str(v) for v in value if v]

    @field_validator("notes", "validation_errors", mode="before")
    @classmethod
    def _normalize_list_fields(cls, value: Any) -> List[str]:
        """Normalize list fields."""
        if value is None:
            return []
        if isinstance(value, str):
            return [value] if value else []
        return [str(v) for v in value if v]

    def get_field(self, field_name: str, default: Any = None) -> Any:
        """Get a field value from the data dict."""
        return self.data.get(field_name, default)

    def set_field(self, field_name: str, value: Any, confidence: Optional[float] = None) -> None:
        """Set a field value in the data dict."""
        self.data[field_name] = value
        if confidence is not None:
            self.extraction_confidence[field_name] = confidence

    def get_all_fields(self) -> Dict[str, Any]:
        """Get all field values."""
        return dict(self.data)

    def to_specialized(self, target_model: type[BaseModel]) -> BaseModel:
        """Convert this generic record to a specialized model."""
        # Map generic fields to specialized model
        data = {
            "source_url": self.source_url,
            "source_urls": self.source_urls,
            "source_domain": self.source_domain,
            "source_page_title": self.source_page_title,
            "scraped_at": self.scraped_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "site_adapter": self.site_adapter,
            "page_type": self.page_type,
            "notes": self.notes,
            **self.data,
        }
        return target_model.model_validate(data)

    @classmethod
    def from_specialized(cls, specialized_record: BaseModel, record_type: str = "generic") -> "GenericRecord":
        """Create a generic record from a specialized model."""
        record_dict = specialized_record.model_dump()

        # Extract core fields
        core_fields = {
            "source_url",
            "source_urls",
            "source_domain",
            "source_page_title",
            "scraped_at",
            "created_at",
            "updated_at",
            "site_adapter",
            "page_type",
            "notes",
            "validation_errors",
        }

        generic_data = {}
        core_data = {}

        for key, value in record_dict.items():
            if key in core_fields:
                core_data[key] = value
            else:
                generic_data[key] = value

        return cls(
            record_type=record_type,
            data=generic_data,
            raw_data=record_dict,
            **core_data,
        )
