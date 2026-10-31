from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from fastapi_startkit.validation.form_request import (
    QUERY_METHODS,
    VALIDATED_KEY,
    declared,
    route_validation,
    validated_calls,
)

if TYPE_CHECKING:
    from fastapi import FastAPI
    from fastapi.routing import APIRoute
    from starlette.routing import BaseRoute


def resolve(schema: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    ref = node.get("$ref")
    return schema["components"]["schemas"][ref.rsplit("/", 1)[-1]] if isinstance(ref, str) else node


def query_parameters(model: dict[str, Any]) -> Iterable[dict[str, Any]]:
    required = set(model.get("required", []))
    for name, field in model.get("properties", {}).items():
        yield {"name": name, "in": "query", "required": name in required, "schema": field}


def document_route(schema: dict[str, Any], route: APIRoute) -> None:
    keys = [getattr(call, VALIDATED_KEY) for call in validated_calls(route.dependant)]
    if not keys or {param.name for param in declared(route.dependant, "body_params")} - set(keys):
        return
    for method in route.methods & QUERY_METHODS:
        operation = schema["paths"].get(route.path_format, {}).get(method.lower())
        if operation is None or "requestBody" not in operation:
            continue
        body = resolve(schema, operation.pop("requestBody")["content"]["application/json"]["schema"])
        models = [body["properties"][key] for key in keys] if route_validation(route).embedded else [body]
        parameters = {(item["name"], item["in"]): item for item in operation.get("parameters", [])}
        for model in models:
            for parameter in query_parameters(resolve(schema, model)):
                parameters.setdefault((parameter["name"], "query"), parameter)
        operation["parameters"] = list(parameters.values())


def document_routes(schema: dict[str, Any], routes: Iterable[BaseRoute]) -> None:
    from fastapi.routing import APIRoute

    for route in routes:
        if isinstance(route, APIRoute):
            document_route(schema, route)


def document_query_input(fastapi: FastAPI) -> None:
    generate = fastapi.openapi

    def openapi() -> dict[str, Any]:
        if fastapi.openapi_schema is None:
            document_routes(generate(), fastapi.routes)
        return generate()

    setattr(fastapi, "openapi", openapi)
