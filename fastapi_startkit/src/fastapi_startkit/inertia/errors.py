from collections.abc import Iterable, Mapping
from typing import Any, Optional, Self, Union

from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

Messages = Union[str, Iterable[str]]
ErrorsInput = Union["ValidationErrors", Mapping[str, Messages], ValidationError, RequestValidationError]


class ValidationErrors:
    def __init__(self, messages: Optional[Mapping[str, Messages]] = None):
        self.messages: dict[str, list[str]] = {}
        if messages:
            self.merge(messages)

    def add(self, field: str, message: str) -> Self:
        self.messages.setdefault(field, []).append(message)
        return self

    def has(self, field: str) -> bool:
        return bool(self.messages.get(field))

    def first(self, field: str) -> Optional[str]:
        messages = self.messages.get(field)
        return messages[0] if messages else None

    def get(self, field: str) -> list[str]:
        return list(self.messages.get(field, []))

    def merge(self, errors: Union["ValidationErrors", Mapping[str, Messages]]) -> Self:
        source = errors.messages if isinstance(errors, ValidationErrors) else errors
        for field, messages in source.items():
            for message in [messages] if isinstance(messages, str) else messages:
                self.add(field, message)
        return self

    def all(self) -> dict[str, list[str]]:
        return {field: list(messages) for field, messages in self.messages.items()}

    def firsts(self) -> dict[str, str]:
        return {field: messages[0] for field, messages in self.messages.items() if messages}

    def __bool__(self) -> bool:
        return any(self.messages.values())

    @classmethod
    def make(cls, errors: ErrorsInput) -> "ValidationErrors":
        if isinstance(errors, RequestValidationError):
            return cls.from_error_list(errors.errors(), skip=1)
        if isinstance(errors, ValidationError):
            return cls.from_error_list(errors.errors(), skip=0)
        return cls(errors.messages if isinstance(errors, ValidationErrors) else errors)

    @classmethod
    def from_error_list(cls, errors: Iterable[Mapping[str, Any]], skip: int) -> "ValidationErrors":
        result = cls()
        for error in errors:
            result.add(".".join(str(part) for part in error["loc"][skip:]), error["msg"])
        return result
