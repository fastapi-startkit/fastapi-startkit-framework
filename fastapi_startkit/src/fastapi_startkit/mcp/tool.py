"""Abstract base class for MCP tools."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from .response import Response


class Tool(ABC):
    name: str
    description: str

    def schema(self) -> type[BaseModel] | None:
        """Return a Pydantic BaseModel subclass describing the input, or None."""
        return None

    def output_schema(self) -> type[BaseModel] | None:
        """Return a Pydantic BaseModel subclass describing the output, or None."""
        return None

    @abstractmethod
    async def handle(self, arguments: dict[str, Any]) -> Response:
        """Execute the tool with the given arguments and return a Response."""
        raise NotImplementedError

    def to_json(self) -> dict[str, Any]:
        """Serialise to the MCP tools/list format."""
        input_schema: dict[str, Any]
        schema_cls = self.schema()
        if schema_cls is not None:
            input_schema = schema_cls.model_json_schema()
        else:
            input_schema = {"type": "object", "properties": {}}

        data: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "inputSchema": input_schema,
        }

        output_schema_cls = self.output_schema()
        if output_schema_cls is not None:
            data["outputSchema"] = output_schema_cls.model_json_schema()

        return data
