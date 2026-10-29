from __future__ import annotations

import inspect
from collections.abc import Iterator, Mapping
from typing import TYPE_CHECKING, Annotated, Any, LiteralString, Self, cast

from pydantic import (
    BaseModel,
    ModelWrapValidatorHandler,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic_core import InitErrorDetails, PydanticCustomError

from fastapi_startkit.exceptions import ValidationException
from fastapi_startkit.validation.field import Field, coerced_values
from fastapi_startkit.validation.message_bag import MessageBag


class FormRequest(BaseModel):
    @classmethod
    def rule_fields(cls) -> Iterator[tuple[str, Field]]:
        for name, info in cls.model_fields.items():
            for metadata in info.metadata:
                if isinstance(metadata, Field):
                    yield name, metadata

    @field_validator("*", mode="after")
    @classmethod
    def record_value(cls, value: Any, info: ValidationInfo) -> Any:
        values = coerced_values.get()
        if values is not None:
            values[str(info.field_name)] = value
        return value

    @model_validator(mode="wrap")
    @classmethod
    def run_rules(cls, data: Any, handler: ModelWrapValidatorHandler[Self]) -> Self:
        values: dict[str, Any] = {}
        token = coerced_values.set(values)
        try:
            instance = handler(cls.fill_missing(data))
        except ValidationError as error:
            raise cls.combine(cls.partial_data(data, values), error.errors(include_url=False)) from None
        finally:
            coerced_values.reset(token)
        failures = cls.rule_failures(dict(instance), set())
        if failures:
            raise ValidationError.from_exception_data(cls.__name__, failures)
        return instance

    @classmethod
    def fill_missing(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            return data
        missing: dict[str, None] = {}
        for name, field in cls.rule_fields():
            info = cls.model_fields[name]
            key = info.alias or name
            if field.defaults_to_none() and info.is_required() and key not in data:
                missing[key] = None
        return {**missing, **data} if missing else data

    @classmethod
    def partial_data(cls, data: Any, values: dict[str, Any]) -> dict[str, Any]:
        defaults = {
            name: info.get_default(call_default_factory=True)
            for name, info in cls.model_fields.items()
            if not info.is_required()
        }
        raw = data if isinstance(data, Mapping) else {}
        return {**defaults, **raw, **values}

    @classmethod
    def combine(cls, data: dict[str, Any], errors: list[Any]) -> ValidationError:
        failed = {error["loc"][0] for error in errors if error["loc"]}
        line_errors: list[InitErrorDetails] = [
            {
                "type": PydanticCustomError(error["type"], error["msg"]),
                "loc": tuple(error["loc"]),
                "input": error["input"],
            }
            for error in errors
        ]
        return ValidationError.from_exception_data(cls.__name__, line_errors + cls.rule_failures(data, failed))

    @classmethod
    def rule_failures(cls, data: Mapping[str, Any], failed: set[Any]) -> list[InitErrorDetails]:
        failures: list[InitErrorDetails] = []
        for name, field in cls.rule_fields():
            if name in failed:
                continue
            message = field.check(name, data.get(name), data)
            if message is not None:
                error = PydanticCustomError("rule", cast("LiteralString", message))
                failures.append({"type": error, "loc": (name,), "input": data.get(name)})
        return failures

    async def validate_async(self, context: Mapping[str, Any] | None = None) -> Self:
        data = {**(context or {}), **dict(self)}
        bag = MessageBag()
        for name, field in self.rule_fields():
            message = await field.check_async(name, data[name], data)
            if message is not None:
                bag.add(name, message)
        if bag.any():
            raise ValidationException(bag)
        return self

    @classmethod
    async def validate_input(cls, data: Any, context: Mapping[str, Any] | None = None) -> Self:
        try:
            instance = cls.model_validate(data)
        except ValidationError as error:
            raise ValidationException(MessageBag.from_errors(error.errors(include_url=False))) from None
        return await instance.validate_async(context)


def validated_dependency(model: type[FormRequest]) -> Any:
    from fastapi import Request

    async def dependency(request: Request, payload: Any) -> Any:
        return await payload.validate_async(request.path_params)

    setattr(
        dependency,
        "__signature__",
        inspect.Signature(
            [
                inspect.Parameter("request", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=Request),
                inspect.Parameter("payload", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=model),
            ]
        ),
    )
    return dependency


if TYPE_CHECKING:
    type Validated[T: FormRequest] = Annotated[T, ...]
else:

    class Validated:
        def __class_getitem__(cls, model: type[FormRequest]) -> Any:
            from fastapi import Depends

            return Annotated[model, Depends(validated_dependency(model))]
