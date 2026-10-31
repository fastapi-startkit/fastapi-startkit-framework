from __future__ import annotations

import inspect
from dataclasses import dataclass
from collections.abc import Awaitable, Iterator, Mapping
from types import UnionType
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, Self, Union, get_args, get_origin
from weakref import finalize

from inflection import underscore
from pydantic import (
    BaseModel,
    GetCoreSchemaHandler,
    ModelWrapValidatorHandler,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic_core import CoreSchema, core_schema

from fastapi_startkit.exceptions import AuthorizationException, ValidationException
from fastapi_startkit.validation.field import Field, coerced_values
from fastapi_startkit.validation.message_bag import MessageBag
from fastapi_startkit.validation.rules import resolve
from fastapi_startkit.validation.validator import Validator

if TYPE_CHECKING:
    from fastapi.dependencies.models import Dependant
    from fastapi.routing import APIRoute
    from starlette.datastructures import QueryParams
    from starlette.requests import Request

REQUEST_PARAMETER = "__validated_request"
RECORDED = "fastapi_startkit.validation.recorded"
PENDING_ERRORS = "fastapi_startkit.validation.errors"
VALIDATED_KEY = "__validated_key__"
SEQUENCES = (list, set, frozenset, tuple)


def has_rules(model: type[BaseModel]) -> bool:
    return any(isinstance(metadata, Field) for info in model.model_fields.values() for metadata in info.metadata)


def is_sequence(annotation: Any) -> bool:
    origin = get_origin(annotation)
    if annotation in SEQUENCES or origin in SEQUENCES:
        return True
    return origin in (Union, UnionType) and any(is_sequence(argument) for argument in get_args(annotation))


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

    stop_on_first_failure: ClassVar[bool] = False

    @classmethod
    def authorize(cls, validator: Validator) -> bool | Awaitable[bool]:
        return True

    @classmethod
    def prepare_for_validation(cls, validator: Validator) -> None | Awaitable[None]:
        return None

    @classmethod
    def after(cls, validator: Validator) -> None | Awaitable[None]:
        return None

    @field_validator("*", mode="after")
    @classmethod
    def record_value(cls, value: Any, info: ValidationInfo) -> Any:
        values = coerced_values.get()
        if values is not None:
            values[str(info.field_name)] = value
        return value

    @model_validator(mode="wrap")
    @classmethod
    def record_values(cls, data: Any, handler: ModelWrapValidatorHandler[Self], info: ValidationInfo) -> Self:
        values: dict[str, Any] = {}
        token = coerced_values.set(values)
        try:
            return handler(data)
        finally:
            coerced_values.reset(token)
            if isinstance(info.context, dict):
                info.context[RECORDED] = values

    @classmethod
    async def validate_input(
        cls, data: Any, context: Mapping[str, Any] | None = None, request: Request | None = None
    ) -> Self:
        validator = Validator({}, context or {}, request)
        if not await resolve(cls.authorize(validator)):
            raise AuthorizationException("This action is unauthorized.")
        validator.data = dict(cls.as_mapping(data))
        await resolve(cls.prepare_for_validation(validator))
        instance, failed = cls.parse(validator)
        await cls.apply_rules(validator, failed)
        await resolve(cls.after(validator))
        if validator.fails() or instance is None:
            raise ValidationException(validator.errors)
        return instance

    @classmethod
    def query_input(cls, params: QueryParams) -> dict[str, Any]:
        fields = {info.alias or name: info for name, info in cls.model_fields.items()}
        return {
            key: params.getlist(key) if is_sequence(fields[key].annotation) else params[key]
            for key in params.keys()
            if key in fields
        }

    @classmethod
    def request_input(cls, params: QueryParams, body: Any) -> Any:
        if body is None:
            return cls.query_input(params)
        if isinstance(body, Mapping):
            return {**cls.query_input(params), **body}
        return body

    @classmethod
    def as_mapping(cls, data: Any) -> Mapping[str, Any]:
        if isinstance(data, Mapping):
            return data
        try:
            return dict(cls.model_validate(data))
        except ValidationError as error:
            raise ValidationException(MessageBag.from_errors(error.errors(include_url=False))) from None

    @classmethod
    def parse(cls, validator: Validator) -> tuple[Self | None, set[str]]:
        data = validator.data
        recorded: dict[str, Any] = {}
        try:
            instance = cls.model_validate(cls.fill_missing(data), context=recorded)
        except ValidationError as error:
            errors = error.errors(include_url=False)
            validator.errors.merge(MessageBag.from_errors(errors))
            validator.data = {**validator.context, **cls.partial_data(data, recorded.get(RECORDED, {}))}
            return None, {str(error["loc"][0]) for error in errors if error["loc"]}
        validator.data = {**validator.context, **cls.partial_data(data, dict(instance))}
        return instance, set()

    @classmethod
    def fill_missing(cls, data: Mapping[str, Any]) -> Mapping[str, Any]:
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
    async def apply_rules(cls, validator: Validator, failed: set[str]) -> None:
        data = validator.data
        for name, field in cls.rule_fields():
            if cls.stop_on_first_failure and validator.fails():
                return
            if name in failed:
                continue
            message = await field.check(name, data.get(name), data)
            if message is not None:
                validator.errors.add(name, message)


class RawInput:
    def __init__(self, model: type[FormRequest]) -> None:
        self.model = model

    def __get_pydantic_core_schema__(self, source_type: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        return core_schema.no_info_plain_validator_function(
            lambda value: value, json_schema_input_schema=handler.generate_schema(self.model)
        )


def declared(dependant: Dependant, attribute: str) -> list[Any]:
    return [
        *getattr(dependant, attribute),
        *(item for sub in dependant.dependencies for item in declared(sub, attribute)),
    ]


def validated_calls(dependant: Dependant) -> list[Any]:
    calls = [call for sub in dependant.dependencies for call in validated_calls(sub)]
    return [*calls, dependant.call] if hasattr(dependant.call, VALIDATED_KEY) else calls


@dataclass(frozen=True)
class RouteValidation:
    path_params: list[Any]
    embedded: bool
    last: Any

    @classmethod
    def of(cls, dependant: Dependant) -> RouteValidation:
        body_params = declared(dependant, "body_params")
        embedded = len({param.name for param in body_params}) > 1 or any(
            getattr(param.field_info, "embed", False) for param in body_params
        )
        calls = validated_calls(dependant)
        return cls(declared(dependant, "path_params"), embedded, calls[-1] if calls else None)


routes: dict[int, RouteValidation] = {}


def route_validation(route: APIRoute) -> RouteValidation:
    key = id(route)
    if key not in routes:
        routes[key] = RouteValidation.of(route.dependant)
        finalize(route, routes.pop, key, None)
    return routes[key]


def matched_route(request: Request) -> RouteValidation | None:
    from fastapi.routing import APIRoute

    route = request.scope.get("route")
    return route_validation(route) if isinstance(route, APIRoute) else None


def typed_path_params(request: Request) -> dict[str, Any] | None:
    from fastapi.dependencies.utils import request_params_to_args

    route = matched_route(request)
    if route is None:
        return dict(request.path_params)
    values, errors = request_params_to_args(route.path_params, request.path_params)
    return None if errors else {**request.path_params, **values}


def pending_errors(request: Request) -> MessageBag:
    return request.scope.setdefault(PENDING_ERRORS, MessageBag())


def validated_dependency(model: type[FormRequest]) -> Any:
    from fastapi import Body, Request

    key = underscore(model.__name__)

    async def dependency(**parameters: Any) -> Any:
        request = parameters[REQUEST_PARAMETER]
        context = typed_path_params(request)
        if context is None:
            return None
        route = matched_route(request)
        errors = pending_errors(request)
        try:
            instance = await model.validate_input(
                model.request_input(request.query_params, parameters[key]), context, request
            )
        except ValidationException as error:
            instance = None
            errors.merge(error.bag, prefix=key if route is not None and route.embedded else None)
        if errors.any() and (route is None or route.last is dependency):
            raise ValidationException(errors)
        return instance

    setattr(dependency, VALIDATED_KEY, key)
    setattr(
        dependency,
        "__signature__",
        inspect.Signature(
            [
                inspect.Parameter(REQUEST_PARAMETER, inspect.Parameter.KEYWORD_ONLY, annotation=Request),
                inspect.Parameter(
                    key,
                    inspect.Parameter.KEYWORD_ONLY,
                    default=None,
                    annotation=Annotated[Any, RawInput(model), Body()],
                ),
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
