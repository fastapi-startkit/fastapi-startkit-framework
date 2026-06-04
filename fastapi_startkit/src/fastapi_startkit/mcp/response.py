from __future__ import annotations


class Response:
    """Wraps tool/prompt output into MCP content format."""

    def __init__(self):
        self._parts: list[dict] = []

    @staticmethod
    def text(value: str) -> Response:
        r = Response()
        r._parts.append({"type": "text", "text": value})
        return r

    @staticmethod
    def structure(data: dict) -> Response:
        r = Response()
        r._parts.append({"type": "resource", "resource": data})
        return r

    def to_content(self) -> list[dict]:
        """Serialize to MCP content array."""
        return self._parts or [{"type": "text", "text": ""}]
