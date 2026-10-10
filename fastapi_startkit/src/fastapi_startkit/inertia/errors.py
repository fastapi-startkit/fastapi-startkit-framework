from typing import Any, Dict, Iterable, List, Mapping, Optional, Union

from pydantic import ValidationError as PydanticValidationError
from starlette.requests import Request

from fastapi_startkit.inertia.constant import Header

DEFAULT_ERROR_BAG = "default"

Messages = Dict[str, List[str]]
Bags = Dict[str, Messages]


class ValidationErrors:
    def __init__(self, messages: Optional[Mapping[str, Union[str, Iterable[str]]]] = None):
        self._messages: Messages = {}
        for field, value in (messages or {}).items():
            self._messages[field] = [value] if isinstance(value, str) else list(value)

    @classmethod
    def of(cls, errors: Union["ValidationErrors", Mapping[str, Union[str, Iterable[str]]]]) -> "ValidationErrors":
        return errors if isinstance(errors, ValidationErrors) else cls(errors)

    @classmethod
    def from_validation_error(cls, exc: Any) -> "ValidationErrors":
        errors = cls()
        for error in exc.errors():
            location = error["loc"]
            path = location if isinstance(exc, PydanticValidationError) else location[1:]
            errors.add(".".join(str(part) for part in path), error["msg"])
        return errors

    def add(self, field: str, message: str) -> "ValidationErrors":
        self._messages.setdefault(field, []).append(message)
        return self

    def has(self, field: str) -> bool:
        return bool(self._messages.get(field))

    def get(self, field: str) -> List[str]:
        return list(self._messages.get(field, []))

    def first(self, field: str) -> Optional[str]:
        messages = self._messages.get(field)
        return messages[0] if messages else None

    def merge(self, other: "ValidationErrors") -> "ValidationErrors":
        merged = ValidationErrors(self._messages)
        for field, messages in other._messages.items():
            for message in messages:
                merged.add(field, message)
        return merged

    def to_dict(self) -> Messages:
        return {field: list(messages) for field, messages in self._messages.items()}


def resolve_error_bag(request: Request, bag: Optional[str] = None) -> str:
    return bag or request.headers.get(Header.ERROR_BAG) or DEFAULT_ERROR_BAG


def merge_error_bag(bags: Bags, bag: str, errors: ValidationErrors) -> Bags:
    return {**bags, bag: ValidationErrors(bags.get(bag)).merge(errors).to_dict()}


def flash_errors(session: Any, bag: str, errors: ValidationErrors) -> None:
    session["errors"] = merge_error_bag(session.get("errors", {}), bag, errors)


def shape_error_bags(bags: Bags, with_all_errors: bool) -> Dict[str, Any]:
    shaped: Dict[str, Any] = {}
    for bag, messages in bags.items():
        fields = {field: list(values) if with_all_errors else values[0] for field, values in messages.items() if values}
        if bag == DEFAULT_ERROR_BAG:
            shaped.update(fields)
        else:
            shaped[bag] = fields
    return shaped
