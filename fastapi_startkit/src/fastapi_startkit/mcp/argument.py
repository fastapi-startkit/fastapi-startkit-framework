from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Argument:
    """A single prompt argument definition."""

    name: str
    description: str | None = None
    required: bool = False

    def to_json(self) -> dict:
        """Build the MCP argument definition for ``prompts/list``."""
        entry: dict = {"name": self.name, "required": self.required}
        if self.description:
            entry["description"] = self.description
        return entry
