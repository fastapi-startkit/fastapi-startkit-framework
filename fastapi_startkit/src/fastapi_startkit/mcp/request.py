"""JSON-RPC 2.0 request model."""

from typing import Annotated, Any, override

from fastapi_startkit.validation import Field, FormRequest, Validator

NOTIFICATION_PREFIX = "notifications/"


class JsonRpcRequest(FormRequest):
    """Represents a JSON-RPC 2.0 request or notification."""

    jsonrpc: str = "2.0"
    method: Annotated[str, Field().required().string()]
    params: dict[str, Any] | None = None
    id: str | int | None = None

    @classmethod
    @override
    def after(cls, validator: Validator) -> None:
        method = validator.data.get("method")
        if validator.data.get("id") is None and isinstance(method, str) and not method.startswith(NOTIFICATION_PREFIX):
            validator.errors.add("id", f"The id field is required for {method}.")

    @property
    def is_notification(self) -> bool:
        """Return True when the request has no id (i.e. it is a notification)."""
        return self.id is None
