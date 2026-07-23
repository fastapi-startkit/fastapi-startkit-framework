"""JSON-RPC 2.0 request model."""

from typing import Any, Optional, Union

from pydantic import BaseModel


class JsonRpcRequest(BaseModel):
    """Represents a JSON-RPC 2.0 request or notification."""

    jsonrpc: str = "2.0"
    method: str
    params: Optional[dict[str, Any]] = None
    id: Optional[Union[str, int]] = None

    @property
    def is_notification(self) -> bool:
        """Return True when the request has no id (i.e. it is a notification)."""
        return self.id is None
