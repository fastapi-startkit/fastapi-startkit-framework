"""fastapi_startkit.jsonapi — JSON:API specification helpers."""

from .response import (
    JsonResource,
    ResourceCollection,
    parse_fields,
    parse_include,
)

__all__ = [
    "JsonResource",
    "ResourceCollection",
    "parse_include",
    "parse_fields",
]
