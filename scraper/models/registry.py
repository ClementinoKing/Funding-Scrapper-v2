"""Schema registry for managing multiple record types."""

from __future__ import annotations

from typing import Dict, List, Optional

from scraper.models.base import RecordSchema


class SchemaRegistry:
    """Central registry for managing record schemas."""

    def __init__(self) -> None:
        self._schemas: Dict[str, RecordSchema] = {}
        self._default_schema: Optional[str] = None

    def register(self, schema: RecordSchema, set_as_default: bool = False) -> None:
        """Register a record schema."""
        self._schemas[schema.schema_name] = schema
        if set_as_default or self._default_schema is None:
            self._default_schema = schema.schema_name

    def get(self, schema_name: str) -> Optional[RecordSchema]:
        """Get a schema by name."""
        return self._schemas.get(schema_name)

    def get_default(self) -> Optional[RecordSchema]:
        """Get the default schema."""
        if self._default_schema:
            return self._schemas.get(self._default_schema)
        return None

    def list_schemas(self) -> List[str]:
        """List all registered schema names."""
        return list(self._schemas.keys())

    def remove(self, schema_name: str) -> bool:
        """Remove a schema from the registry."""
        if schema_name in self._schemas:
            del self._schemas[schema_name]
            if self._default_schema == schema_name:
                self._default_schema = None
            return True
        return False


# Global registry instance
_global_schema_registry: Optional[SchemaRegistry] = None


def get_global_schema_registry() -> SchemaRegistry:
    """Get or create the global schema registry."""
    global _global_schema_registry
    if _global_schema_registry is None:
        _global_schema_registry = SchemaRegistry()
    return _global_schema_registry
