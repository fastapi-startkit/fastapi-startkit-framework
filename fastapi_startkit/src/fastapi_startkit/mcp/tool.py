from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from .response import Response


class Tool(ABC):
    """Base class for MCP tools.

    Subclasses must set ``name`` and ``description`` and implement ``handle``.
    """

    name: str | None = None
    description: str | None = None

    def schema(self) -> type[BaseModel]:
        """Return the Pydantic model describing the tool's input parameters."""
        return BaseModel

    def output_schema(self) -> type[BaseModel] | None:
        """Optional output schema as a Pydantic model. Return ``None`` to omit."""
        return None

    @abstractmethod
    async def handle(self, arguments: dict) -> Response:
        """Execute the tool and return a ``Response``."""
        ...

    def to_json(self) -> dict:
        """Build the full MCP tool definition for ``tools/list``."""
        entry = {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.schema().model_json_schema(),
        }
        output = self.output_schema()
        if output is not None:
            entry["outputSchema"] = output.model_json_schema()
        return entry
