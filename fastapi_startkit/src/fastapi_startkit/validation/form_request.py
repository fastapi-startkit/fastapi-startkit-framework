from __future__ import annotations

import inspect
from collections.abc import Iterator, Mapping
from weakref import finalize
from typing import TYPE_CHECKING, Annotated, Any, LiteralString, Self, cast, get_args

from inflection import underscore
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

if TYPE_CHECKING:
    from fastapi.dependencies.models import Dependant
    from fastapi.routing import APIRoute
    from starlette.requests import Request

REQUEST_PARAMETER = "__validated_request"


def has_rules(model: type[BaseModel]) -> bool:
    return any(isinstance(metadata, Field) for info in model.model_fields.values() for metadata in info.metadata)


def nested_models(annotation: Any) -> Iterator[type[BaseModel]]:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        yield annotation
    for argument in get_args(annotation):
        yield from nested_models(argument)


class FormRequest(BaseModel):
    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        for name, info in cls.model_fields.items():
            for model in nested_models(info.annotation):
                if has_rules(model):
                    raise TypeError(
                        f"{cls.__name__}.{name}: validation rules on nested model {model.__name__} are not supported."
                    )

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
            raise cls.combine(data, values, error.errors(include_url=False)) from None
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
    def partial_data(cls, data: Mapping[str, Any], values: dict[str, Any]) -> dict[str, Any]:
        defaults = {
            name: info.get_default(call_default_factory=True)
            for name, info in cls.model_fields.items()
            if not info.is_required()
        }
        return {**defaults, **data, **values}

    @classmethod
    def combine(cls, data: Any, values: dict[str, Any], errors: list[Any]) -> ValidationError:
        line_errors: list[InitErrorDetails] = [
            {
                "type": PydanticCustomError(error["type"], error["msg"]),
                "loc": tuple(error["loc"]),
                "input": error["input"],
            }
            for error in errors
        ]
        if isinstance(data, Mapping):
            failed = {error["loc"][0] for error in errors if error["loc"]}
            line_errors += cls.rule_failures(cls.partial_data(data, values), failed)
        return ValidationError.from_exception_data(cls.__name__, line_errors)

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


def declared_path_params(dependant: Dependant) -> list[Any]:
    return [*dependant.path_params, *(param for sub in dependant.dependencies for param in declared_path_params(sub))]


route_path_params: dict[int, list[Any]] = {}


def path_params_of(route: APIRoute) -> list[Any]:
    key = id(route)
    if key not in route_path_params:
        route_path_params[key] = declared_path_params(route.dependant)
        finalize(route, route_path_params.pop, key, None)
    return route_path_params[key]


def typed_path_params(request: Request) -> dict[str, Any] | None:
    from fastapi.dependencies.utils import request_params_to_args
    from fastapi.routing import APIRoute

    route = request.scope.get("route")
    if not isinstance(route, APIRoute):
        return dict(request.path_params)
    values, errors = request_params_to_args(path_params_of(route), request.path_params)
    return None if errors else {**request.path_params, **values}


def validated_dependency(model: type[FormRequest]) -> Any:
    from fastapi import Request

    key = underscore(model.__name__)

    async def dependency(**parameters: Any) -> Any:
        payload = parameters[key]
        context = typed_path_params(parameters[REQUEST_PARAMETER])
        if context is None:
            return payload
        return await payload.validate_async(context)

    setattr(
        dependency,
        "__signature__",
        inspect.Signature(
            [
                inspect.Parameter(REQUEST_PARAMETER, inspect.Parameter.KEYWORD_ONLY, annotation=Request),
                inspect.Parameter(key, inspect.Parameter.KEYWORD_ONLY, annotation=model),
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
