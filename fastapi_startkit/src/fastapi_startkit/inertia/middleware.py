from typing import Optional

from fastapi import status
from fastapi_startkit.inertia.constant import Header
from fastapi_startkit.inertia.inertia import Inertia
from fastapi_startkit.inertia.context import InertiaRequestState, current_request, current_state
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

REDIRECT_STATUSES = (301, 302, 303, 307, 308)


class InertiaMiddleware(BaseHTTPMiddleware):
    _root_view: Optional[str] = None

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
    def root_view(cls, request: Request) -> Optional[str]:
        return cls._root_view

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        state = InertiaRequestState(
            root_view=self.root_view(request),
            version=lambda: self.version(request),
        )
        request_token = current_request.set(request)
        state_token = current_state.set(state)
        try:
            if self.has_version_conflict(request):
                response = self.on_version_change(request)
            else:
                Inertia.share(self.share(request))
                response = self.handle_response(request, await call_next(request))
        finally:
            current_state.reset(state_token)
            current_request.reset(request_token)

        self.append_vary(response)
        return response

    def handle_response(self, request: Request, response: Response) -> Response:
        if response.status_code in REDIRECT_STATUSES:
            self.reflash(request)

        if not request.headers.get(Header.INERTIA):
            return response

        if response.status_code == status.HTTP_200_OK and response.headers.get("content-length") == "0":
            response = self.on_empty_response(request, response)

        if response.status_code == status.HTTP_302_FOUND and request.method in ["PUT", "PATCH", "DELETE"]:
            response.status_code = status.HTTP_303_SEE_OTHER

        if self.redirects_to_fragment(request, response):
            return self.on_redirect_with_fragment(request, response)
        return response

    @staticmethod
    def has_version_conflict(request: Request) -> bool:
        return (
            request.method == "GET"
            and bool(request.headers.get(Header.INERTIA))
            and request.headers.get(Header.INERTIA_VERSION, "") != (Inertia.get_version() or "")
        )

    @staticmethod
    def redirects_to_fragment(request: Request, response: Response) -> bool:
        if request.headers.get(Header.PURPOSE, "").lower() == "prefetch":
            return False
        location = response.headers.get("location", "")
        is_redirect = response.status_code in REDIRECT_STATUSES or (
            response.status_code == status.HTTP_201_CREATED and bool(location)
        )
        return is_redirect and "#" in location

    @staticmethod
    def append_vary(response: Response) -> None:
        values = [value.strip() for value in response.headers.get("vary", "").split(",") if value.strip()]
        if Header.INERTIA.lower() not in (value.lower() for value in values):
            values.append(Header.INERTIA)
        response.headers["Vary"] = ", ".join(values)

    @classmethod
    def on_version_change(cls, request: Request) -> Response:
        cls.reflash(request)
        return Response(
            status_code=status.HTTP_409_CONFLICT,
            headers={
                Header.INERTIA_LOCATION: str(request.url),
                Header.INERTIA_VERSION: Inertia.get_version() or "",
            },
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
