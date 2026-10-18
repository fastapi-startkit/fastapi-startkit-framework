"""JSON-RPC 2.0 request model."""

from typing import Any

from pydantic import BaseModel


class JsonRpcRequest(BaseModel):
    """Represents a JSON-RPC 2.0 request or notification."""

    jsonrpc: str = "2.0"
    method: str
    params: dict[str, Any] | None = None
    id: str | int | None = None

    @property
    def is_notification(self) -> bool:
        """Return True when the request has no id (i.e. it is a notification)."""
        return self.id is None
