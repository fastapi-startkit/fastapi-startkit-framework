from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Self


class MessageBag:
    def __init__(self, messages: Mapping[str, str | Iterable[str]] | None = None) -> None:
        self.messages: dict[str, list[str]] = {}
        for field, field_messages in (messages or {}).items():
            for message in [field_messages] if isinstance(field_messages, str) else field_messages:
                self.add(field, message)

    @classmethod
    def from_errors(cls, errors: Iterable[Mapping[str, Any]], skip: int = 0) -> Self:
        bag = cls()
        for error in errors:
            bag.add(".".join(str(part) for part in tuple(error["loc"])[skip:]), error["msg"])
        return bag

    def add(self, field: str, message: str) -> Self:
        self.messages.setdefault(field, []).append(message)
        return self

    def merge(self, other: MessageBag, prefix: str | None = None) -> Self:
        for field, messages in other.messages.items():
            for message in messages:
                self.add(f"{prefix}.{field}" if prefix else field, message)
        return self

    def has(self, field: str) -> bool:
        return field in self.messages

    def get(self, field: str) -> Sequence[str]:
        return self.messages.get(field, [])

    def first(self, field: str | None = None) -> str | None:
        messages = self.get(field) if field is not None else self.all()
        return messages[0] if messages else None

    def all(self) -> list[str]:
        return [message for messages in self.messages.values() for message in messages]

    def count(self) -> int:
        return len(self.all())

    def any(self) -> bool:
        return bool(self.messages)

    def summary(self) -> str:
        first = self.first() or "The given data was invalid."
        remaining = self.count() - 1
        if remaining <= 0:
            return first
        return f"{first} (and {remaining} more error{'s' if remaining > 1 else ''})"

    def to_dict(self) -> dict[str, Any]:
        return {
            "message": self.summary(),
            "errors": {field: list(messages) for field, messages in self.messages.items()},
        }
