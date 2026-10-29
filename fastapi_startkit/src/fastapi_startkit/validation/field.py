from __future__ import annotations

import re
from collections.abc import Collection, Mapping
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Self

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from fastapi_startkit.validation.rules import (
    AsyncRule,
    BaseRule,
    Between,
    Boolean,
    Confirmed,
    EmailRule,
    Exists,
    Ignore,
    In,
    Integer,
    Max,
    Message,
    Min,
    NotIn,
    Nullable,
    Numeric,
    Regex,
    Required,
    RequiredIf,
    Rule,
    SameAs,
    Size,
    String,
    Unique,
    Url,
    is_empty,
)

if TYPE_CHECKING:
    from fastapi_startkit.masoniteorm.models.model import Model

coerced_values: ContextVar[dict[str, Any] | None] = ContextVar("coerced_values", default=None)


class Field:
    def __init__(self) -> None:
        self.rules: list[BaseRule] = []

    def add(self, rule: BaseRule) -> Self:
        self.rules.append(rule)
        numeric = any(isinstance(rule, (Numeric, Integer)) for rule in self.rules)
        for size in self.rules:
            if isinstance(size, Size):
                size.numeric = numeric
        return self

    def msg(self, message: Message) -> Self:
        if not self.rules:
            raise ValueError("msg() needs a rule before it.")
        self.rules[-1].custom_message = message
        return self

    def required(self, msg: Message | None = None) -> Self:
        return self.add(Required(msg))

    def nullable(self) -> Self:
        return self.add(Nullable())

    def required_if(self, other: str, value: Any, msg: Message | None = None) -> Self:
        return self.add(RequiredIf(other, value, msg))

    def string(self, msg: Message | None = None) -> Self:
        return self.add(String(msg))

    def integer(self, msg: Message | None = None) -> Self:
        return self.add(Integer(msg))

    def numeric(self, msg: Message | None = None) -> Self:
        return self.add(Numeric(msg))

    def boolean(self, msg: Message | None = None) -> Self:
        return self.add(Boolean(msg))

    def min(self, minimum: int | float, msg: Message | None = None) -> Self:
        return self.add(Min(minimum, msg))

    def max(self, maximum: int | float, msg: Message | None = None) -> Self:
        return self.add(Max(maximum, msg))

    def between(self, minimum: int | float, maximum: int | float, msg: Message | None = None) -> Self:
        return self.add(Between(minimum, maximum, msg))

    def password(self, msg: Message | None = None) -> Self:
        return self.min(8, msg)

    def email(self, msg: Message | None = None) -> Self:
        return self.add(EmailRule(msg))

    def url(self, msg: Message | None = None) -> Self:
        return self.add(Url(msg))

    def regex(self, pattern: str | re.Pattern[str], msg: Message | None = None) -> Self:
        return self.add(Regex(pattern, msg))

    def in_(self, values: Collection[Any], msg: Message | None = None) -> Self:
        return self.add(In(values, msg))

    def not_in(self, values: Collection[Any], msg: Message | None = None) -> Self:
        return self.add(NotIn(values, msg))

    def same_as(self, other: str, msg: Message | None = None) -> Self:
        return self.add(SameAs(other, msg))

    def confirmed(self, msg: Message | None = None) -> Self:
        return self.add(Confirmed(msg))

    def unique(
        self,
        table: str | type[Model],
        column: str | None = None,
        ignore: Ignore = None,
        ignore_column: str = "id",
        msg: Message | None = None,
    ) -> Self:
        return self.add(Unique(table, column, ignore, ignore_column, msg))

    def exists(self, table: str | type[Model], column: str | None = None, msg: Message | None = None) -> Self:
        return self.add(Exists(table, column, msg))

    def accepts_none(self) -> bool:
        return any(isinstance(rule, (Required, RequiredIf, Nullable)) for rule in self.rules)

    def defaults_to_none(self) -> bool:
        return any(isinstance(rule, (Required, RequiredIf)) for rule in self.rules)

    def check(self, attribute: str, value: Any, data: Mapping[str, Any]) -> str | None:
        for rule in self.rules:
            if not isinstance(rule, Rule) or self.skips(rule, value):
                continue
            if not rule.passes(attribute, value, data):
                return rule.format_message(attribute, value, data)
        return None

    async def check_async(self, attribute: str, value: Any, data: Mapping[str, Any]) -> str | None:
        for rule in self.rules:
            if not isinstance(rule, AsyncRule) or self.skips(rule, value):
                continue
            if not await rule.passes(attribute, value, data):
                return rule.format_message(attribute, value, data)
        return None

    @staticmethod
    def skips(rule: BaseRule, value: Any) -> bool:
        return not rule.implicit and is_empty(value)

    def __get_pydantic_core_schema__(self, source_type: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        schema = handler(source_type)
        if self.accepts_none():
            schema = core_schema.nullable_schema(schema, metadata=self.json_schema_metadata(schema))
        schema = core_schema.no_info_after_validator_function(self.require_form_request, schema)
        return schema

    def json_schema_metadata(self, schema: CoreSchema) -> dict[str, Any] | None:
        required = any(isinstance(rule, Required) for rule in self.rules)
        if not required or any(isinstance(rule, Nullable) for rule in self.rules):
            return None
        return {"pydantic_js_functions": [lambda _, handler: handler(schema)]}

    @staticmethod
    def require_form_request(value: Any) -> Any:
        if coerced_values.get() is None:
            raise TypeError("Validation rules need a FormRequest model.")
        return value


class Email(Field):
    def __init__(self) -> None:
        super().__init__()
        self.email()
