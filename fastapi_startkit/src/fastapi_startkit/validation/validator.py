from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Self

from fastapi_startkit.validation.message_bag import MessageBag

if TYPE_CHECKING:
    from starlette.requests import Request


@dataclass
class Validator:
    data: dict[str, Any]
    context: Mapping[str, Any] = field(default_factory=dict)
    request: Request | None = None
    errors: MessageBag = field(default_factory=MessageBag)

    def merge(self, values: Mapping[str, Any]) -> Self:
        self.data.update(values)
        return self

    def fails(self) -> bool:
        return self.errors.any()
