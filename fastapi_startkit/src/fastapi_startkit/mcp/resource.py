from __future__ import annotations

from abc import ABC, abstractmethod


class Resource(ABC):
    """Base class for MCP resources.

    Subclasses must set ``uri`` and ``name`` and implement ``read``.
    """

    uri: str | None = None
    name: str | None = None
    description: str | None = None
    mime_type: str = "text/plain"

    @abstractmethod
    async def read(self, **kwargs) -> str:
        """Read and return the resource content."""
        ...

    def to_json(self) -> dict:
        """Build the MCP resource definition for ``resources/list``."""
        entry = {
            "uri": self.uri,
            "name": self.name,
            "mimeType": self.mime_type,
        }
        if self.description:
            entry["description"] = self.description
        return entry
