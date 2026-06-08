"""fastapi_startkit.jsonapi — JSON:API specification helpers."""

from .response import (
    JsonResource,
    _ResourceCollection,
    parse_fields,
    parse_include,
)

__all__ = [
    "JsonResource",
    "_ResourceCollection",
    "parse_include",
    "parse_fields",
]
