"""Response wrapper for MCP tool and prompt outputs."""

import json
from typing import Any


class Response:
    """Wraps tool/prompt output into MCP content format."""

    def __init__(self, content: list[dict]) -> None:
        self._content = content

    @classmethod
    def text(cls, value: str) -> "Response":
        """Create a plain-text response."""
        return cls([{"type": "text", "text": value}])

    @classmethod
    def structure(cls, data: dict[str, Any]) -> "Response":
        """Create a structured (resource-type) response."""
        return cls([{"type": "resource", "resource": {"text": json.dumps(data), "mimeType": "application/json"}}])

    @classmethod
    def empty(cls) -> "Response":
        """Create an empty response with no content."""
        return cls([])

    def to_content(self) -> list[dict]:
        """Return the raw content list."""
        return self._content
