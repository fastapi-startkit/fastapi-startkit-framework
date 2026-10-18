"""Abstract base class for MCP prompts."""

from abc import ABC, abstractmethod
from typing import Any

from .argument import Argument
from .response import Response


class Prompt(ABC):
    name: str
    description: str | None = None
    title: str | None = None

    def arguments(self) -> list[Argument]:
        """Return the list of arguments this prompt accepts."""
        return []

    def should_register(self) -> bool:
        """Return False to prevent this prompt from being registered."""
        return True

    @abstractmethod
    async def handle(self, arguments: dict[str, Any]) -> Response:
        """Render the prompt with the given arguments and return a Response."""
        raise NotImplementedError

    def to_json(self) -> dict[str, Any]:
        """Serialise to the MCP prompts/list format."""
        data: dict[str, Any] = {"name": self.name}
        if self.description is not None:
            data["description"] = self.description
        if self.title is not None:
            data["title"] = self.title
        args = self.arguments()
        if args:
            data["arguments"] = [arg.to_json() for arg in args]
        return data
