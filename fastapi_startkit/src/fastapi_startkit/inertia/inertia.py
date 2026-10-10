import inspect
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, Union
from urllib.parse import urlparse

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.responses import RedirectResponse, Response


from fastapi_startkit.inertia.bigint import encode_big_integers
from fastapi_startkit.inertia.props.props import OptionalProp
from fastapi_startkit.inertia.constant import Header
from fastapi_startkit.inertia.context import current_request
from fastapi_startkit.inertia.errors import (
    Bags,
    ValidationErrors,
    flash_errors,
    merge_error_bag,
    resolve_error_bag,
    shape_error_bags,
)
from fastapi_startkit.inertia.session import session_for_queue
from fastapi_startkit.inertia.ssr import HttpSSRGateway, SSRGateway, ViteHotFileGateway, is_excepted

PRESERVE_FRAGMENT_KEY = "preserveFragment"
UrlResolver = Callable[[Request], str]


def _current_request() -> Request:
    request = current_request.get()
    if request is None:
        raise RuntimeError(
            "Inertia requires InertiaMiddleware to be registered. "
            "Add app.add_middleware(InertiaMiddleware) to your bootstrap."
        )
    return request


class ResponseFactory:
    """Holds all Inertia state: app container, root view, shared props, version."""

    def __init__(self):
        self.root_view: str = "index.html"
        self.shared_props: dict = {}
        self.version = None
        self.ssr_gateway: Optional[SSRGateway] = None
        self.ssr_enabled: bool = True
        self.ssr_except_paths: Tuple[str, ...] = ()
        self.with_all_errors: bool = False
        self.url_resolver: Optional[UrlResolver] = None
        self.preserve_big_integers: bool = False

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

    def set_ssr(self, gateway: Optional[SSRGateway], *, enabled: bool = True, except_paths: Sequence[str] = ()):
        self.ssr_gateway = gateway
        self.ssr_enabled = enabled
        self.ssr_except_paths = tuple(except_paths)

    async def ssr_healthy(self) -> bool:
        return self.ssr_gateway is not None and await self.ssr_gateway.healthy()

    def render(self, component: str, props: dict) -> "InertiaResponse":
        return InertiaResponse(
            component=component,
            shared_props=self.shared_props,
            props=props,
            root_view=self.root_view,
            version=self.get_version() or "",
            ssr_gateway=self.ssr_gateway if self.ssr_enabled else None,
            ssr_except_paths=self.ssr_except_paths,
            with_all_errors=self.with_all_errors,
            url_resolver=self.url_resolver,
            preserve_big_integers=self.preserve_big_integers,
        )


class InertiaResponse(Response):
    def __init__(
        self,
        component: str,
        shared_props: dict,
        props: dict,
        root_view: str = "index.html",
        version: str = "",
        ssr_gateway: Optional[SSRGateway] = None,
        ssr_except_paths: Sequence[str] = (),
        with_all_errors: bool = False,
        url_resolver: Optional[UrlResolver] = None,
        preserve_big_integers: bool = False,
    ):
        # Do not call supper().__init__() — body is built lazily in __call__
        self.background = None  # required by FastAPI's response handling
        self.component = component
        self.shared_props = shared_props
        self.props = props
        self.root_view = root_view
        self.version = version
        self.ssr_gateway = ssr_gateway
        self.ssr_except_paths = tuple(ssr_except_paths)
        self.with_all_errors = with_all_errors
        self.url_resolver = url_resolver
        self.big_integers = preserve_big_integers
        self.pending_errors: List[Tuple[Optional[str], ValidationErrors]] = []

    def preserve_big_integers(self, enabled: bool = True) -> "InertiaResponse":
        self.big_integers = enabled
        return self

    def with_(self, key: Union[str, Dict[str, Any]], value: Any = None) -> "InertiaResponse":
        if isinstance(key, dict):
            self.props = {**self.props, **key}
        else:
            self.props[key] = value
        return self

    def with_errors(self, errors: Union[ValidationErrors, Mapping[str, Any]]) -> "InertiaResponse":
        self.pending_errors.append((None, ValidationErrors.of(errors)))
        return self

    def with_errors_in(self, bag: str, errors: Union[ValidationErrors, Mapping[str, Any]]) -> "InertiaResponse":
        self.pending_errors.append((bag, ValidationErrors.of(errors)))
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
        if self.pending_errors:
            all_props["errors"] = {**all_props.get("errors", {}), **self._page_errors(request)}

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

        if self.big_integers:
            resolved = encode_big_integers(resolved)

        session = request.scope.get("session")
        preserve_fragment = bool(session.pop(PRESERVE_FRAGMENT_KEY, False)) if session is not None else False

        page = {
            "component": self.component,
            "props": resolved,
            "url": self._page_url(request),
            "version": self.version,
            "preserveBigIntegers": self.big_integers,
            "preserveFragment": preserve_fragment,
        }

        # SSR is used only for the initial HTML response. Inertia XHR requests
        # continue returning the regular page JSON and never contact Node.
        gateway = self._ssr_gateway_for(request)
        if gateway is not None:
            rendered = await gateway.render(page)
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

    def _page_errors(self, request: Request) -> dict:
        bags: Bags = {}
        for bag, errors in self.pending_errors:
            bags = merge_error_bag(bags, resolve_error_bag(request, bag), errors)
        return shape_error_bags(bags, self.with_all_errors)

    def _ssr_gateway_for(self, request: Request) -> Optional[SSRGateway]:
        if request.headers.get(Header.INERTIA) or self.ssr_gateway is None:
            return None
        if is_excepted(urlparse(str(request.url)).path, self.ssr_except_paths):
            return None
        return self.ssr_gateway

    def _page_url(self, request: Request) -> str:
        if self.url_resolver is not None:
            return self.url_resolver(request)
        return self._get_url(request)

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
    def ssr(
        url: Optional[str] = "http://127.0.0.1:13714",
        timeout: float = 1.0,
        *,
        enabled: bool = True,
        except_paths: Sequence[str] = (),
    ):
        gateway = HttpSSRGateway(url, timeout) if url else None
        Inertia.instance().set_ssr(gateway, enabled=enabled, except_paths=except_paths)

    @staticmethod
    def ssr_hot(
        hot_file: str,
        timeout: float = 1.0,
        *,
        enabled: bool = True,
        except_paths: Sequence[str] = (),
    ):
        Inertia.instance().set_ssr(ViteHotFileGateway(hot_file, timeout), enabled=enabled, except_paths=except_paths)

    @staticmethod
    async def ssr_healthy() -> bool:
        return await Inertia.instance().ssr_healthy()

    @staticmethod
    def get_version() -> Optional[str]:
        return Inertia.instance().get_version()

    @staticmethod
    def with_all_errors(enabled: bool = True):
        Inertia.instance().with_all_errors = enabled

    @staticmethod
    def url_resolver(resolver: Optional[UrlResolver]):
        Inertia.instance().url_resolver = resolver

    @staticmethod
    def preserve_big_integers(enabled: bool = True):
        Inertia.instance().preserve_big_integers = enabled

    @staticmethod
    def preserve_fragment():
        session = session_for_queue(_current_request(), "preserved fragment")
        if session is not None:
            session[PRESERVE_FRAGMENT_KEY] = True

    @staticmethod
    def optional(callback) -> OptionalProp:
        return OptionalProp(callback)

    @staticmethod
    def render(component: str, props: Optional[Dict[str, Any]] = None) -> InertiaResponse:
        return Inertia.instance().render(component, props or {})

    @staticmethod
    def back() -> RedirectResponse:
        return RedirectResponse(url=_current_request().headers.get("referer", "/"), status_code=302)

    @staticmethod
    def back_with_errors(
        errors: Union[ValidationErrors, Mapping[str, Any]],
        bag: Optional[str] = None,
    ) -> RedirectResponse:
        request = _current_request()
        session = session_for_queue(request, "validation errors")
        if session is not None:
            flash_errors(session, resolve_error_bag(request, bag), ValidationErrors.of(errors))
        return RedirectResponse(url=request.headers.get("referer", "/"), status_code=302)
