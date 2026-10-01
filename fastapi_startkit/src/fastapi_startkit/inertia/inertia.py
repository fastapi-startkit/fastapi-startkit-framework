import inspect
import asyncio
import json
import urllib.request
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
        self.ssr_url: Optional[str] = None
        self.ssr_timeout: float = 1.0

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

    def set_ssr(self, url: Optional[str], timeout: float = 1.0):
        """Configure the Inertia SSR server endpoint. Pass None to disable SSR."""
        self.ssr_url = url.rstrip("/") if url else None
        self.ssr_timeout = timeout

    def render(self, component: str, props: dict) -> "InertiaResponse":
        return InertiaResponse(
            component=component,
            shared_props=self.shared_props,
            props=props,
            root_view=self.root_view,
            version=self.get_version() or "",
            ssr_url=self.ssr_url,
            ssr_timeout=self.ssr_timeout,
        )


class InertiaResponse(Response):
    def __init__(
        self,
        component: str,
        shared_props: dict,
        props: dict,
        root_view: str = "index.html",
        version: str = "",
        ssr_url: Optional[str] = None,
        ssr_timeout: float = 1.0,
    ):
        # Do not call supper().__init__() — body is built lazily in __call__
        self.background = None  # required by FastAPI's response handling
        self.component = component
        self.shared_props = shared_props
        self.props = props
        self.root_view = root_view
        self.version = version
        self.ssr_url = ssr_url
        self.ssr_timeout = ssr_timeout

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

        # SSR is used only for the initial HTML response. Inertia XHR requests
        # continue returning the regular page JSON and never contact Node.
        if not request.headers.get(Header.INERTIA) and self.ssr_url:
            rendered = await self._render_ssr(page)
            if rendered:
                page["ssr"] = rendered

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

    async def _render_ssr(self, page: dict) -> Optional[dict]:
        """Ask the configured Inertia Node server to render this page."""
        ssr_url = self.ssr_url
        if ssr_url is None:
            return None

        def request_ssr():
            body = json.dumps(page).encode("utf-8")
            req = urllib.request.Request(
                ssr_url.rstrip("/") + "/render",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.ssr_timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
            if not isinstance(result, dict) or not isinstance(result.get("body"), str):
                raise ValueError("Invalid Inertia SSR response")
            return {"body": result["body"], "head": result.get("head", [])}

        try:
            return await asyncio.to_thread(request_ssr)
        except Exception:
            # SSR is an enhancement: if its process is unavailable, send the
            # normal page shell so the client can still hydrate it.
            return None

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
    def ssr(url: Optional[str] = "http://127.0.0.1:13714", timeout: float = 1.0):
        """Enable SSR through the standard Inertia SSR server endpoint."""
        Inertia.instance().set_ssr(url, timeout)

    @staticmethod
    def get_version() -> Optional[str]:
        return Inertia.instance().get_version()

    @staticmethod
    def optional(callback) -> OptionalProp:
        return OptionalProp(callback)

    @staticmethod
    def render(component: str, props: Optional[Dict[str, Any]] = None) -> InertiaResponse:
        return Inertia.instance().render(component, props or {})
