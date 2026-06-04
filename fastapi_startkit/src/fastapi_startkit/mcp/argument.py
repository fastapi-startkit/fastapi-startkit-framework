"""Argument dataclass for MCP prompt arguments."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Argument:
    """Represents a single argument accepted by a Prompt."""

    name: str
    description: Optional[str] = field(default=None)
    required: bool = field(default=False)

    def to_json(self) -> dict:
        """Serialise to MCP-compatible JSON."""
        data: dict = {"name": self.name, "required": self.required}
        if self.description is not None:
            data["description"] = self.description
        return data
