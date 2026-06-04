"""Abstract base class for MCP tools."""

from abc import ABC, abstractmethod
from typing import Optional, Type

from pydantic import BaseModel

from .response import Response


class Tool(ABC):
    """Base class for MCP tools.

    Subclasses must set ``name`` and ``description``, and implement ``handle()``.
    Optionally override ``schema()`` to declare the input schema and
    ``output_schema()`` to declare the output schema.
    """

    name: str
    description: str

    def schema(self) -> Optional[Type[BaseModel]]:
        """Return a Pydantic BaseModel subclass describing the input, or None."""
        return None

    def output_schema(self) -> Optional[Type[BaseModel]]:
        """Return a Pydantic BaseModel subclass describing the output, or None."""
        return None

    @abstractmethod
    async def handle(self, arguments: dict) -> Response:
        """Execute the tool with the given arguments and return a Response."""
        raise NotImplementedError

    def to_json(self) -> dict:
        """Serialise to the MCP tools/list format."""
        input_schema: dict
        schema_cls = self.schema()
        if schema_cls is not None:
            input_schema = schema_cls.model_json_schema()
        else:
            input_schema = {"type": "object", "properties": {}}

        data: dict = {
            "name": self.name,
            "description": self.description,
            "inputSchema": input_schema,
        }

        output_schema_cls = self.output_schema()
        if output_schema_cls is not None:
            data["outputSchema"] = output_schema_cls.model_json_schema()

        return data
