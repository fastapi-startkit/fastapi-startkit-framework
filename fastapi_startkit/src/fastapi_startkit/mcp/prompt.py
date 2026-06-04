from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from .argument import Argument

if TYPE_CHECKING:
    from .response import Response


class Prompt(ABC):
    """Base class for MCP prompts.

    Subclasses must set ``name`` and implement ``handle``.
    """

    title: str | None = None
    name: str | None = None
    description: str | None = None

    def should_register(self) -> bool:
        """Return ``False`` to conditionally skip registration."""
        return True

    def arguments(self) -> list[Argument]:
        """Return the prompt's argument definitions."""
        return []

    @abstractmethod
    async def handle(self, arguments: dict) -> Response:
        """Generate the prompt content. Returns a ``Response``."""
        ...

    def to_json(self) -> dict:
        """Build the MCP prompt definition for ``prompts/list``."""
        return {
            "name": self.name,
            "description": self.description,
            "arguments": [a.to_json() for a in self.arguments()],
        }
