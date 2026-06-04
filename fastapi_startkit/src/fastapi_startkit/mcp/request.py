from __future__ import annotations

from pydantic import BaseModel, Field


class JsonRpcRequest(BaseModel):
    """A JSON-RPC 2.0 request envelope for the MCP transport."""

    jsonrpc: str = "2.0"
    method: str = ""
    id: str | int | None = None
    params: dict = Field(default_factory=dict)

    @property
    def is_notification(self) -> bool:
        """Requests without an ``id`` are notifications (no response expected)."""
        return self.id is None
