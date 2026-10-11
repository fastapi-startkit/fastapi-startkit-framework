import asyncio
import json
import urllib.request
from typing import Any, Dict, Optional, Union
from urllib.parse import urlparse

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.responses import RedirectResponse, Response

from fastapi_startkit.inertia import session
from fastapi_startkit.inertia.errors import ErrorsInput
from fastapi_startkit.fastapi.referer import same_origin_referer
from fastapi_startkit.inertia.redirect import InertiaRedirect

from fastapi_startkit.inertia.props.props import OptionalProp, Prop
from fastapi_startkit.inertia.props.resolver import PropsResolver
from fastapi_startkit.inertia.props.scroll import ScrollMetadata
from fastapi_startkit.inertia.constant import Header
from fastapi_startkit.inertia.context import current_request, current_state


class ResponseFactory:
    """Holds all Inertia state: app container, root view, shared props, version."""

    def __init__(self):
        self.root_view: str = "index.html"
        self.shared_props: dict = {}
        self.version = None
        self.ssr_url: Optional[str] = None
        self.ssr_timeout: float = 1.0
        self.encrypt_history_enabled: bool = False
        self.expose_shared_prop_keys: bool = True

    def set_root_view(self, view: str):
        self.root_view = view

    def share(self, key: Union[str, Dict[str, Any]], value: Any = None):
        state = current_state.get()
        props = state.shared_props if state is not None else self.shared_props
        if isinstance(key, dict):
            props.update(key)
        else:
            props[key] = value

    def shared(self) -> dict:
        state = current_state.get()
        request_props = state.shared_props if state is not None else {}
        return {**self.shared_props, **request_props}

    def set_version(self, version):
        self.version = version

    def get_version(self) -> Optional[str]:
        state = current_state.get()
        if state is None:
            return self.resolve_version(self.version)
        if not state.version_resolved:
            state.resolved_version = self.resolve_version(self.version if self.version is not None else state.version)
            state.version_resolved = True
        return state.resolved_version

    @staticmethod
    def resolve_version(version) -> Optional[str]:
        v = version() if callable(version) else version
        return str(v) if v is not None else None

    def get_root_view(self) -> str:
        state = current_state.get()
        if state is not None and state.root_view:
            return state.root_view
        return self.root_view

    def set_encrypt_history(self, enabled: bool = True):
        state = current_state.get()
        if state is not None:
            state.encrypt_history = enabled
        else:
            self.encrypt_history_enabled = enabled

    def should_encrypt_history(self) -> bool:
        state = current_state.get()
        if state is not None and state.encrypt_history is not None:
            return state.encrypt_history
        return self.encrypt_history_enabled

    def set_ssr(self, url: Optional[str], timeout: float = 1.0):
        """Configure the Inertia SSR server endpoint. Pass None to disable SSR."""
        self.ssr_url = url.rstrip("/") if url else None
        self.ssr_timeout = timeout

    def render(self, component: str, props: dict) -> "InertiaResponse":
        return InertiaResponse(
            component=component,
            shared_props=self.shared(),
            props=props,
            root_view=self.get_root_view(),
            version=self.get_version() or "",
            ssr_url=self.ssr_url,
            ssr_timeout=self.ssr_timeout,
            encrypt_history=self.should_encrypt_history(),
            expose_shared_prop_keys=self.expose_shared_prop_keys,
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
        encrypt_history: bool = False,
        expose_shared_prop_keys: bool = True,
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
        self.encrypt_history_enabled = encrypt_history
        self.flash_data: dict = {}
        self.expose_shared_prop_keys = expose_shared_prop_keys

    def with_(self, key: Union[str, Dict[str, Any]], value: Any = None) -> "InertiaResponse":
        if isinstance(key, dict):
            self.props = {**self.props, **key}
        else:
            self.props[key] = value
        return self

    def with_root_view(self, root_view: str) -> "InertiaResponse":
        self.root_view = root_view
        return self

    def flash(self, key: Union[str, Dict[str, Any]], value: Any = None) -> "InertiaResponse":
        self.flash_data.update(key if isinstance(key, dict) else {key: value})
        return self

    def encrypt_history(self, enabled: bool = True) -> "InertiaResponse":
        self.encrypt_history_enabled = enabled
        return self

    def session_metadata(self, request: Request) -> dict:
        flash = {**(session.pull(request, session.FLASH) or {}), **self.flash_data}
        metadata: dict = {
            "encryptHistory": self.encrypt_history_enabled,
            "clearHistory": bool(session.pull(request, session.CLEAR_HISTORY, False)),
        }
        if session.pull(request, session.PRESERVE_FRAGMENT, False):
            metadata["preserveFragment"] = True
        if flash:
            metadata["flash"] = flash
        return metadata

    async def to_response(self, request: Request):
        props, metadata = await PropsResolver(request, self.component).resolve(
            self.shared_props, self.props, self.expose_shared_prop_keys
        )

        page = {
            "component": self.component,
            "props": props,
            "url": self._get_url(request),
            "version": self.version,
            **metadata,
        }
        page.update(self.session_metadata(request))

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
    def shared() -> dict:
        return Inertia.instance().shared()

    @staticmethod
    def version(version):
        Inertia.instance().set_version(version)

    @staticmethod
    def ssr(url: Optional[str] = "http://127.0.0.1:13714", timeout: float = 1.0):
        """Enable SSR through the standard Inertia SSR server endpoint."""
        Inertia.instance().set_ssr(url, timeout)

    @staticmethod
    def encrypt_history(enabled: bool = True):
        Inertia.instance().set_encrypt_history(enabled)

    @staticmethod
    def clear_history():
        session.clear_history()

    @staticmethod
    def preserve_fragment():
        session.preserve_fragment()

    @staticmethod
    def flash(key: Union[str, Dict[str, Any]], value: Any = None):
        session.flash(key, value)

    @staticmethod
    def with_errors(errors: ErrorsInput):
        session.with_errors(errors)

    @staticmethod
    def with_errors_in(bag: str, errors: ErrorsInput):
        session.with_errors(errors, bag)

    @staticmethod
    def location(url: str) -> Response:
        request = current_request.get()
        if request is not None and request.headers.get(Header.INERTIA):
            return Response(status_code=409, headers={Header.INERTIA_LOCATION: url})
        return RedirectResponse(url, status_code=302)

    @staticmethod
    def redirect(url: str, status_code: int = 302) -> InertiaRedirect:
        return InertiaRedirect(url, status_code=status_code)

    @staticmethod
    def back(status_code: int = 302) -> InertiaRedirect:
        return InertiaRedirect(same_origin_referer(current_request.get()), status_code=status_code)

    @staticmethod
    def back_with_errors(errors: ErrorsInput, bag: Optional[str] = None) -> InertiaRedirect:
        return Inertia.back().with_errors_in(bag or session.DEFAULT_BAG, errors)

    @staticmethod
    def get_version() -> Optional[str]:
        return Inertia.instance().get_version()

    @staticmethod
    def expose_shared_prop_keys(expose: bool = True):
        Inertia.instance().expose_shared_prop_keys = expose

    @staticmethod
    def optional(callback) -> OptionalProp:
        return OptionalProp(callback)

    @staticmethod
    def lazy(callback) -> Prop:
        return Prop(callback)

    @staticmethod
    def defer(callback, group: str = "default") -> Prop:
        return Prop(callback).defer(group)

    @staticmethod
    def always(value) -> Prop:
        return Prop(value).always()

    @staticmethod
    def merge(value) -> Prop:
        return Prop(value).merge()

    @staticmethod
    def deep_merge(value) -> Prop:
        return Prop(value).deep_merge()

    @staticmethod
    def once(callback) -> Prop:
        return Prop(callback).once()

    @staticmethod
    def scroll(page, metadata: Optional[ScrollMetadata] = None) -> Prop:
        return Prop(page).scroll(metadata)

    @staticmethod
    def scroll_with(callback) -> Prop:
        return Prop(callback).scroll()

    @staticmethod
    def render(component: str, props: Optional[Dict[str, Any]] = None) -> InertiaResponse:
        return Inertia.instance().render(component, props or {})
