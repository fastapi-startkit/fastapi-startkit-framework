"""Abstract base class for MCP prompts."""

from abc import ABC, abstractmethod
from typing import Optional

from .argument import Argument
from .response import Response


class Prompt(ABC):
    """Base class for MCP prompts.

    Subclasses must set ``name`` and implement ``handle()``.
    Override ``arguments()`` to declare accepted arguments.
    Override ``should_register()`` to conditionally skip registration.
    """

    name: str
    description: Optional[str] = None
    title: Optional[str] = None

    def arguments(self) -> list[Argument]:
        """Return the list of arguments this prompt accepts."""
        return []

    def should_register(self) -> bool:
        """Return False to prevent this prompt from being registered."""
        return True

    @abstractmethod
    async def handle(self, arguments: dict) -> Response:
        """Render the prompt with the given arguments and return a Response."""
        raise NotImplementedError

    def to_json(self) -> dict:
        """Serialise to the MCP prompts/list format."""
        data: dict = {"name": self.name}
        if self.description is not None:
            data["description"] = self.description
        if self.title is not None:
            data["title"] = self.title
        args = self.arguments()
        if args:
            data["arguments"] = [arg.to_json() for arg in args]
        return data
