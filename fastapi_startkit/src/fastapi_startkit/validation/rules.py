from __future__ import annotations

import re
from collections.abc import Callable, Collection, Mapping
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any, ClassVar
from urllib.parse import urlparse

if TYPE_CHECKING:
    from fastapi_startkit.masoniteorm.models.builder import QueryBuilder
    from fastapi_startkit.masoniteorm.models.model import Model

type Message = str | Callable[[str, Any, Mapping[str, Any]], str]
type Ignore = Any | Callable[[Mapping[str, Any]], Any]

PLACEHOLDER = re.compile(r":(\w+)")


def is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def humanize(attribute: str) -> str:
    return attribute.replace("_", " ").replace(".", " ").strip()


class BaseRule:
    message: ClassVar[str] = "The :attribute field is invalid."
    implicit: ClassVar[bool] = False

    def __init__(self, message: Message | None = None) -> None:
        self.custom_message: Message | None = message

    def default_message(self, value: Any) -> str:
        return self.message

    def replacements(self) -> Mapping[str, Any]:
        return {}

    def format_message(self, attribute: str, value: Any, data: Mapping[str, Any]) -> str:
        if callable(self.custom_message):
            return self.custom_message(attribute, value, data)
        template = self.custom_message or self.default_message(value)
        placeholders = {"attribute": humanize(attribute), **self.replacements()}
        return PLACEHOLDER.sub(lambda match: str(placeholders.get(match[1], match[0])), template)


class Rule(BaseRule):
    def passes(self, attribute: str, value: Any, data: Mapping[str, Any]) -> bool:
        return True


class AsyncRule(BaseRule):
    async def passes(self, attribute: str, value: Any, data: Mapping[str, Any]) -> bool:
        return True


class Required(Rule):
    message = "The :attribute field is required."
    implicit = True

    def passes(self, attribute: str, value: Any, data: Mapping[str, Any]) -> bool:
        return not is_empty(value)


class Nullable(Rule):
    pass


class RequiredIf(Rule):
    message = "The :attribute field is required when :other is :value."
    implicit = True

    def __init__(self, other: str, expected: Any, message: Message | None = None) -> None:
        super().__init__(message)
        self.other = other
        self.expected = expected

    def replacements(self) -> Mapping[str, Any]:
        return {"other": humanize(self.other), "value": self.expected}

    def passes(self, attribute: str, value: Any, data: Mapping[str, Any]) -> bool:
        return data.get(self.other) != self.expected or not is_empty(value)


class String(Rule):
    message = "The :attribute field must be a string."

    def passes(self, attribute: str, value: Any, data: Mapping[str, Any]) -> bool:
        return isinstance(value, str)


class Integer(Rule):
    message = "The :attribute field must be an integer."

    def passes(self, attribute: str, value: Any, data: Mapping[str, Any]) -> bool:
        if isinstance(value, bool):
            return False
        if isinstance(value, int):
            return True
        return isinstance(value, str) and re.fullmatch(r"[+-]?\d+", value.strip()) is not None


class Numeric(Rule):
    message = "The :attribute field must be a number."

    def passes(self, attribute: str, value: Any, data: Mapping[str, Any]) -> bool:
        return to_number(value) is not None


class Boolean(Rule):
    message = "The :attribute field must be true or false."

    def passes(self, attribute: str, value: Any, data: Mapping[str, Any]) -> bool:
        return isinstance(value, bool) or value in (0, 1, "0", "1")


def to_number(value: Any) -> int | float | Decimal | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        return value
    if isinstance(value, str):
        try:
            return Decimal(value.strip())
        except InvalidOperation:
            return None
    return None


class Size(Rule):
    messages: ClassVar[dict[str, str]] = {}

    def __init__(
        self, minimum: int | float | None = None, maximum: int | float | None = None, message: Message | None = None
    ) -> None:
        super().__init__(message)
        self.minimum = minimum
        self.maximum = maximum

    def replacements(self) -> Mapping[str, Any]:
        return {"min": self.minimum, "max": self.maximum}

    def default_message(self, value: Any) -> str:
        if isinstance(value, str):
            return self.messages["string"]
        if isinstance(value, Collection):
            return self.messages["array"]
        return self.messages["numeric"]

    def passes(self, attribute: str, value: Any, data: Mapping[str, Any]) -> bool:
        size = size_of(value)
        if size is None:
            return False
        return (self.minimum is None or size >= self.minimum) and (self.maximum is None or size <= self.maximum)


def size_of(value: Any) -> int | float | Decimal | None:
    if isinstance(value, str):
        return len(value)
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return value
    if isinstance(value, Collection):
        return len(value)
    return None


class Min(Size):
    messages = {
        "string": "The :attribute field must be at least :min characters.",
        "numeric": "The :attribute field must be at least :min.",
        "array": "The :attribute field must have at least :min items.",
    }

    def __init__(self, minimum: int | float, message: Message | None = None) -> None:
        super().__init__(minimum, None, message)


class Max(Size):
    messages = {
        "string": "The :attribute field must not be greater than :max characters.",
        "numeric": "The :attribute field must not be greater than :max.",
        "array": "The :attribute field must not have more than :max items.",
    }

    def __init__(self, maximum: int | float, message: Message | None = None) -> None:
        super().__init__(None, maximum, message)


class Between(Size):
    messages = {
        "string": "The :attribute field must be between :min and :max characters.",
        "numeric": "The :attribute field must be between :min and :max.",
        "array": "The :attribute field must have between :min and :max items.",
    }


class EmailRule(Rule):
    message = "The :attribute field must be a valid email address."
    pattern: ClassVar[re.Pattern[str]] = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")

    def passes(self, attribute: str, value: Any, data: Mapping[str, Any]) -> bool:
        return isinstance(value, str) and self.pattern.fullmatch(value) is not None


class Url(Rule):
    message = "The :attribute field must be a valid URL."

    def passes(self, attribute: str, value: Any, data: Mapping[str, Any]) -> bool:
        if not isinstance(value, str):
            return False
        parsed = urlparse(value)
        return bool(parsed.scheme and parsed.netloc)


class Regex(Rule):
    message = "The :attribute field format is invalid."

    def __init__(self, pattern: str | re.Pattern[str], message: Message | None = None) -> None:
        super().__init__(message)
        self.pattern = re.compile(pattern)

    def passes(self, attribute: str, value: Any, data: Mapping[str, Any]) -> bool:
        return isinstance(value, str) and self.pattern.search(value) is not None


class In(Rule):
    message = "The selected :attribute is invalid."

    def __init__(self, values: Collection[Any], message: Message | None = None) -> None:
        super().__init__(message)
        self.values = values

    def passes(self, attribute: str, value: Any, data: Mapping[str, Any]) -> bool:
        return value in self.values


class NotIn(In):
    def passes(self, attribute: str, value: Any, data: Mapping[str, Any]) -> bool:
        return value not in self.values


class SameAs(Rule):
    message = "The :attribute field must match :other."

    def __init__(self, other: str, message: Message | None = None) -> None:
        super().__init__(message)
        self.other = other

    def replacements(self) -> Mapping[str, Any]:
        return {"other": humanize(self.other)}

    def passes(self, attribute: str, value: Any, data: Mapping[str, Any]) -> bool:
        return value == data.get(self.other)


class Confirmed(Rule):
    message = "The :attribute field confirmation does not match."

    def passes(self, attribute: str, value: Any, data: Mapping[str, Any]) -> bool:
        return value == data.get(f"{attribute}_confirmation")


class DatabaseRule(AsyncRule):
    def __init__(self, table: str | type[Model], column: str | None = None, message: Message | None = None) -> None:
        super().__init__(message)
        self.table = table
        self.column = column

    def query(self, attribute: str, value: Any) -> QueryBuilder[Any]:
        if isinstance(self.table, str):
            from fastapi_startkit.masoniteorm.facades.DB import DB

            builder = DB.table(self.table)
        else:
            builder = self.table.query()
        return builder.where(self.column or attribute, value)


class Unique(DatabaseRule):
    message = "The :attribute has already been taken."

    def __init__(
        self,
        table: str | type[Model],
        column: str | None = None,
        ignore: Ignore = None,
        ignore_column: str = "id",
        message: Message | None = None,
    ) -> None:
        super().__init__(table, column, message)
        self.ignore = ignore
        self.ignore_column = ignore_column

    async def passes(self, attribute: str, value: Any, data: Mapping[str, Any]) -> bool:
        query = self.query(attribute, value)
        ignore = self.ignore(data) if callable(self.ignore) else self.ignore
        if ignore is not None:
            query = query.where(self.ignore_column, "!=", ignore)
        return not await query.exists()


class Exists(DatabaseRule):
    message = "The selected :attribute is invalid."

    async def passes(self, attribute: str, value: Any, data: Mapping[str, Any]) -> bool:
        return await self.query(attribute, value).exists()
