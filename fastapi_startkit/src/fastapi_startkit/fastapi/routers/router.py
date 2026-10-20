import inspect
from collections.abc import Callable, Sequence
from enum import Enum
from types import ModuleType
from typing import Any, TypedDict, Unpack

from fastapi import APIRouter, params
from fastapi.datastructures import DefaultPlaceholder
from fastapi.routing import APIRoute
from fastapi.types import IncEx
from starlette.responses import Response
from starlette.routing import BaseRoute
from starlette.types import ASGIApp, Lifespan


class RouterOptions(TypedDict, total=False):
    prefix: str
    tags: list[str | Enum] | None
    dependencies: Sequence[params.Depends] | None
    default_response_class: type[Response]
    responses: dict[int | str, dict[str, Any]] | None
    callbacks: list[BaseRoute] | None
    routes: list[BaseRoute] | None
    redirect_slashes: bool
    default: ASGIApp | None
    dependency_overrides_provider: Any | None
    route_class: type[APIRoute]
    on_startup: Sequence[Callable[[], Any]] | None
    on_shutdown: Sequence[Callable[[], Any]] | None
    lifespan: Lifespan[Any] | None
    deprecated: bool | None
    include_in_schema: bool
    generate_unique_id_function: Callable[[APIRoute], str]


class RouteOptions(TypedDict, total=False):
    response_model: Any
    status_code: int | None
    tags: list[str | Enum] | None
    dependencies: Sequence[params.Depends] | None
    summary: str | None
    description: str | None
    response_description: str
    responses: dict[int | str, dict[str, Any]] | None
    deprecated: bool | None
    operation_id: str | None
    response_model_include: IncEx | None
    response_model_exclude: IncEx | None
    response_model_by_alias: bool
    response_model_exclude_unset: bool
    response_model_exclude_defaults: bool
    response_model_exclude_none: bool
    include_in_schema: bool
    response_class: type[Response] | DefaultPlaceholder
    name: str | None
    route_class_override: type[APIRoute] | None
    callbacks: list[BaseRoute] | None
    openapi_extra: dict[str, Any] | None
    generate_unique_id_function: Callable[[APIRoute], str] | DefaultPlaceholder


class Router:
    def __init__(self, **kwargs: Unpack[RouterOptions]):
        self.router = APIRouter(**kwargs)

    def _add_route(
        self,
        path: str,
        action: Callable[..., Any],
        methods: list[str],
        **kwargs: Unpack[RouteOptions],
    ) -> None:
        kwargs["responses"] = kwargs.get("responses") or {}
        self.router.add_api_route(path, action, methods=methods, **kwargs)

    def get(self, path: str, action: Callable[..., Any], **kwargs: Unpack[RouteOptions]) -> None:
        self._add_route(path, action, ["GET"], **kwargs)

    def post(self, path: str, action: Callable[..., Any], **kwargs: Unpack[RouteOptions]) -> None:
        self._add_route(path, action, ["POST"], **kwargs)

    def put(self, path: str, action: Callable[..., Any], **kwargs: Unpack[RouteOptions]) -> None:
        self._add_route(path, action, ["PUT"], **kwargs)

    def patch(self, path: str, action: Callable[..., Any], **kwargs: Unpack[RouteOptions]) -> None:
        self._add_route(path, action, ["PATCH"], **kwargs)

    def delete(self, path: str, action: Callable[..., Any], **kwargs: Unpack[RouteOptions]) -> None:
        self._add_route(path, action, ["DELETE"], **kwargs)

    def head(self, path: str, action: Callable[..., Any], **kwargs: Unpack[RouteOptions]) -> None:
        self._add_route(path, action, ["HEAD"], **kwargs)

    def options(self, path: str, action: Callable[..., Any], **kwargs: Unpack[RouteOptions]) -> None:
        self._add_route(path, action, ["OPTIONS"], **kwargs)

    def resource(
        self,
        resource: str,
        controller: ModuleType | Any,
        *,
        only: set[str] | None = None,
        excepts: set[str] | None = None,
        names: dict[str, str] | None = None,
        parameters: dict[str, str] | None = None,
    ) -> None:
        if inspect.isclass(controller):
            controller = controller()

        name: str = resource.strip("/").split("/")[-1]
        default_param = name.rstrip("s") if name.endswith("s") else name
        param: str = (parameters or {}).get(name, default_param)

        def route_name(route: str, default: str) -> str:
            return (names or {}).get(route, default)

        def include(route: str) -> bool:
            if only is not None:
                return route in only
            if excepts is not None:
                return route not in excepts
            return True

        def fn(method: str) -> Callable[..., Any]:
            return getattr(controller, method)

        if include("index") and hasattr(controller, "index"):
            self.get(f"/{name}", fn("index"), name=route_name("index", name))

        if include("create") and hasattr(controller, "create"):
            self.get(
                f"/{name}/create",
                fn("create"),
                name=route_name("create", f"{name}.create"),
            )

        if include("store") and hasattr(controller, "store"):
            self.post(f"/{name}", fn("store"), name=route_name("store", f"{name}.store"))

        if include("show") and hasattr(controller, "show"):
            self.get(
                f"/{name}/{{{param}}}",
                fn("show"),
                name=route_name("show", f"{name}.show"),
            )

        if include("edit") and hasattr(controller, "edit"):
            self.get(
                f"/{name}/{{{param}}}/edit",
                fn("edit"),
                name=route_name("edit", f"{name}.edit"),
            )

        if include("update") and hasattr(controller, "update"):
            self.put(
                f"/{name}/{{{param}}}",
                fn("update"),
                name=route_name("update", f"{name}.update"),
            )

        if include("destroy") and hasattr(controller, "destroy"):
            self.delete(
                f"/{name}/{{{param}}}",
                fn("destroy"),
                name=route_name("destroy", f"{name}.destroy"),
            )

    def __getattr__(self, name: str) -> Any:
        return getattr(self.router, name)

    def __call__(self, *args, **kwargs):
        return self.router(*args, **kwargs)
