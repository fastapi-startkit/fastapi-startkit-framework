"""Abstract base class for MCP resources."""

from abc import ABC, abstractmethod
from typing import Any


class Resource(ABC):
    """Base class for MCP resources.

    Subclasses must set ``uri`` and ``name``, and implement ``read()``.
    """

    uri: str
    name: str
    description: str | None = None
    mime_type: str = "text/plain"

    @abstractmethod
    async def read(self, **kwargs) -> str:
        """Return the resource content as a string."""
        raise NotImplementedError

    def to_json(self) -> dict[str, Any]:
        """Serialise to the MCP resources/list format."""
        data: dict[str, Any] = {
            "uri": self.uri,
            "name": self.name,
            "mimeType": self.mime_type,
        }
        if self.description is not None:
            data["description"] = self.description
        return data
