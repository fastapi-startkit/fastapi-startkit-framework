from typing import Optional

from fastapi import status
from fastapi_startkit.inertia.constant import Header
from fastapi_startkit.inertia.inertia import Inertia
from fastapi_startkit.inertia.context import current_request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response


class InertiaMiddleware(BaseHTTPMiddleware):
    _root_view: str = "index.html"

    @staticmethod
    def version(request: Request) -> Optional[str]:
        """Determine the current asset version from the Vite manifest hash."""
        from fastapi_startkit.application import app as container

        if container().has("vite"):
            return container().make("vite").manifest_hash()
        return None

    @staticmethod
    def share(request: Request) -> dict:
        """Define props that are shared on every response."""
        return {
            "errors": InertiaMiddleware.resolve_validation_errors(request),
        }

    @classmethod
    def root_view(cls, request: Request) -> str:
        """Return the root template name for the first page visit."""
        return cls._root_view

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        Inertia.version(lambda: self.version(request))
        Inertia.share(self.share(request))
        Inertia.set_root_view(self.root_view(request))

        token = current_request.set(request)
        try:
            response = await call_next(request)
        finally:
            current_request.reset(token)

        response.headers["Vary"] = Header.INERTIA

        is_redirect = response.status_code in (301, 302, 303, 307, 308)
        if is_redirect:
            self.reflash(request)

        if not request.headers.get(Header.INERTIA):
            return response

        # Version conflict — ask client to do a full page reload
        if request.method == "GET" and request.headers.get(Header.INERTIA_VERSION, "") != (Inertia.get_version() or ""):
            return self.on_version_change(request, response)

        # 302 → 303 for PUT/PATCH/DELETE so browser issues a GET
        if response.status_code == 302 and request.method in ["PUT", "PATCH", "DELETE"]:
            response.status_code = status.HTTP_303_SEE_OTHER

        # Redirect with fragment → 409 so Inertia handles fragment preservation
        location = response.headers.get("location", "")
        if is_redirect and "#" in location:
            return self.on_redirect_with_fragment(request, response)
        return response

    @staticmethod
    def on_version_change(request: Request, response: Response) -> Response:
        return Response(
            status_code=status.HTTP_409_CONFLICT,
            headers={Header.INERTIA_LOCATION: str(request.url)},
        )

    @staticmethod
    def on_empty_response(request: Request, response: Response) -> Response:
        referer = request.headers.get("referer", "/")
        return RedirectResponse(url=referer, status_code=302)

    @staticmethod
    def on_redirect_with_fragment(request: Request, response: Response) -> Response:
        return Response(
            status_code=status.HTTP_409_CONFLICT,
            headers={Header.INERTIA_REDIRECT: response.headers.get("location", "/")},
        )

    @staticmethod
    def resolve_validation_errors(request: Request) -> dict:
        if "session" not in request.scope:
            return {}
        return request.session.pop("errors", {})

    @staticmethod
    def reflash(request: Request) -> None:
        """Re-flash session data so it survives the redirect."""
        if "session" not in request.scope:
            return
        flash = request.session.get("_flash", {})
        if flash:
            request.session["_flash"] = flash
