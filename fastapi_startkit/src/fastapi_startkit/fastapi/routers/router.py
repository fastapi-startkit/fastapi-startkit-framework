import inspect
from enum import Enum
from types import ModuleType
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Type, Union

from fastapi import APIRouter, params
from fastapi.datastructures import DefaultPlaceholder
from fastapi.routing import APIRoute
from fastapi.types import IncEx
from starlette.responses import Response
from starlette.routing import BaseRoute
from starlette.types import ASGIApp, Lifespan
from typing_extensions import TypedDict, Unpack


class RouterOptions(TypedDict, total=False):
    prefix: str
    tags: Optional[List[Union[str, Enum]]]
    dependencies: Optional[Sequence[params.Depends]]
    default_response_class: Type[Response]
    responses: Optional[Dict[Union[int, str], Dict[str, Any]]]
    callbacks: Optional[List[BaseRoute]]
    routes: Optional[List[BaseRoute]]
    redirect_slashes: bool
    default: Optional[ASGIApp]
    dependency_overrides_provider: Optional[Any]
    route_class: Type[APIRoute]
    on_startup: Optional[Sequence[Callable[[], Any]]]
    on_shutdown: Optional[Sequence[Callable[[], Any]]]
    lifespan: Optional[Lifespan[Any]]
    deprecated: Optional[bool]
    include_in_schema: bool
    generate_unique_id_function: Callable[[APIRoute], str]


class RouteOptions(TypedDict, total=False):
    response_model: Any
    status_code: Optional[int]
    tags: Optional[List[Union[str, Enum]]]
    dependencies: Optional[Sequence[params.Depends]]
    summary: Optional[str]
    description: Optional[str]
    response_description: str
    responses: Optional[Dict[Union[int, str], Dict[str, Any]]]
    deprecated: Optional[bool]
    operation_id: Optional[str]
    response_model_include: Optional[IncEx]
    response_model_exclude: Optional[IncEx]
    response_model_by_alias: bool
    response_model_exclude_unset: bool
    response_model_exclude_defaults: bool
    response_model_exclude_none: bool
    include_in_schema: bool
    response_class: Union[Type[Response], DefaultPlaceholder]
    name: Optional[str]
    route_class_override: Optional[Type[APIRoute]]
    callbacks: Optional[List[BaseRoute]]
    openapi_extra: Optional[Dict[str, Any]]
    generate_unique_id_function: Union[Callable[[APIRoute], str], DefaultPlaceholder]


class Router:
    def __init__(self, **kwargs: Unpack[RouterOptions]):
        self.router = APIRouter(**kwargs)

    def _add_route(
        self,
        path: str,
        action: Callable[..., Any],
        methods: List[str],
        **kwargs: Unpack[RouteOptions],
    ) -> None:
        self.router.add_api_route(
            path,
            action,
            methods=methods,
            responses=kwargs.pop("responses", None) or {},  # type: ignore[misc]
            **kwargs,
        )

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
        controller: Union[ModuleType, Any],
        *,
        only: Optional[Set[str]] = None,
        excepts: Optional[Set[str]] = None,
        names: Optional[Dict[str, str]] = None,
        parameters: Optional[Dict[str, str]] = None,
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
