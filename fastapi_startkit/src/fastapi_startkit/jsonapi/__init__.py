"""fastapi_startkit.jsonapi — JSON:API specification helpers."""

from .response import (
    JsonAPIListResponse,
    JsonAPIResponse,
    JsonResource,
    _ResourceCollection,
    parse_fields,
    parse_include,
)

__all__ = [
    # New API
    "JsonResource",
    "_ResourceCollection",
    # Backward-compatible aliases
    "JsonAPIResponse",
    "JsonAPIListResponse",
    # Query-param helpers
    "parse_include",
    "parse_fields",
]
