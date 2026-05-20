import inspect
from typing import Any, Dict, Optional, Union
from urllib.parse import urlparse

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.responses import Response


from fastapi_startkit.inertia.props.props import OptionalProp
from fastapi_startkit.inertia.constant import Header
from fastapi_startkit.inertia.context import current_request


class ResponseFactory:
    """Holds all Inertia state: app container, root view, shared props, version."""

    def __init__(self):
        self.root_view: str = "index.html"
        self.shared_props: dict = {}
        self.version = None

    def set_root_view(self, view: str):
        self.root_view = view

    def share(self, key: Union[str, Dict[str, Any]], value: Any = None):
        if isinstance(key, dict):
            self.shared_props = {**self.shared_props, **key}
        else:
            self.shared_props[key] = value

    def set_version(self, version):
        self.version = version

    def get_version(self) -> Optional[str]:
        v = self.version() if callable(self.version) else self.version
        return str(v) if v is not None else None

    def render(self, component: str, props: dict) -> "InertiaResponse":
        return InertiaResponse(
            component=component,
            shared_props=self.shared_props,
            props=props,
            root_view=self.root_view,
            version=self.get_version() or "",
        )


class InertiaResponse(Response):
    def __init__(
        self,
        component: str,
        shared_props: dict,
        props: dict,
        root_view: str = "index.html",
        version: str = "",
    ):
        # Do not call supper().__init__() — body is built lazily in __call__
        self.background = None  # required by FastAPI's response handling
        self.component = component
        self.shared_props = shared_props
        self.props = props
        self.root_view = root_view
        self.version = version

    def with_(self, key: Union[str, Dict[str, Any]], value: Any = None) -> "InertiaResponse":
        if isinstance(key, dict):
            self.props = {**self.props, **key}
        else:
            self.props[key] = value
        return self

    def with_root_view(self, root_view: str) -> "InertiaResponse":
        self.root_view = root_view
        return self

    async def to_response(self, request: Request):
        # Determine partial reload scope
        partial_component = request.headers.get(Header.INERTIA_PARTIAL_COMPONENT)
        is_partial = partial_component == self.component
        partial_keys: set = set()
        if is_partial:
            raw = request.headers.get("X-Inertia-Partial-Data", "")
            partial_keys = set(filter(None, raw.split(",")))

        all_props = {**self.shared_props, **self.props}

        resolved: dict = {}
        for k, v in all_props.items():
            # OptionalProp: only include when explicitly requested in a partial reload
            if isinstance(v, OptionalProp):
                if not is_partial or k not in partial_keys:
                    continue
                v = v.callback

            # Skip keys aren't requested in partial reload
            if is_partial and partial_keys and k not in partial_keys:
                continue

            # Resolve callables — support both sync and async
            if callable(v):
                sig = inspect.signature(v)
                result = v(request) if len(sig.parameters) > 0 else v()
                if inspect.isawaitable(result):
                    result = await result
                resolved[k] = result
            else:
                resolved[k] = v

        page = {
            "component": self.component,
            "props": resolved,
            "url": self._get_url(request),
            "version": self.version,
        }

        if request.headers.get(Header.INERTIA):
            return JSONResponse(
                content=page,
                headers={Header.INERTIA: "true"},
            )

        from fastapi_startkit.application import app as container

        if not container().has("templates"):
            raise RuntimeError("Inertia requires 'templates' to be bound in the container for initial rendering.")

        return (
            container()
            .make("templates")
            .TemplateResponse(
                request,
                self.root_view,
                {"page": page},
            )
        )

    def _get_url(self, request: Request) -> str:
        parsed = urlparse(str(request.url))
        url = parsed.path
        if parsed.query:
            url = f"{url}?{parsed.query}"
        return url or "/"

    async def __call__(self, scope, receive, send):
        request = current_request.get()
        if request is None:
            raise RuntimeError(
                "InertiaResponse requires InertiaMiddleware to be registered. "
                "Add app.add_middleware(InertiaMiddleware) to your bootstrap."
            )
        actual_response = await self.to_response(request)
        await actual_response(scope, receive, send)


class Inertia:
    _instance: Optional[ResponseFactory] = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = ResponseFactory()
        return cls._instance

    @staticmethod
    def set_root_view(root_view: str):
        Inertia.instance().set_root_view(root_view)

    @staticmethod
    def share(key: Union[str, Dict[str, Any]], value: Any = None):
        Inertia.instance().share(key, value)

    @staticmethod
    def version(version):
        Inertia.instance().set_version(version)

    @staticmethod
    def get_version() -> Optional[str]:
        return Inertia.instance().get_version()

    @staticmethod
    def optional(callback) -> OptionalProp:
        return OptionalProp(callback)

    @staticmethod
    def render(component: str, props: Optional[Dict[str, Any]] = None) -> InertiaResponse:
        return Inertia.instance().render(component, props or {})
