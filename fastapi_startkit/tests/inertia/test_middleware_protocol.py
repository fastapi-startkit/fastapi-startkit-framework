import asyncio
import json
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.testclient import TestClient
from starlette.responses import Response

from fastapi_startkit.inertia.constant import Header
from fastapi_startkit.inertia.encoding import html_safe_json
from fastapi_startkit.inertia.inertia import Inertia
from fastapi_startkit.inertia.middleware import InertiaMiddleware

INERTIA = {Header.INERTIA: "true"}


class FakeTemplates:
    def TemplateResponse(self, request, name, context):
        return HTMLResponse(json.dumps({"view": name, "page": context["page"]}))


class SessionFromHeader:
    last: dict = {}

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope["headers"])
            scope["session"] = json.loads(headers.get(b"x-test-session", b"{}"))
            SessionFromHeader.last = scope["session"]
        await self.app(scope, receive, send)


@pytest.fixture
def container():
    Inertia._instance = None
    services = {"templates": FakeTemplates()}
    mock = MagicMock()
    mock.has.side_effect = lambda key: key in services
    mock.make.side_effect = lambda key: services[key]
    with patch("fastapi_startkit.application.app", return_value=mock):
        yield services
    Inertia._instance = None


def make_app(middleware=InertiaMiddleware):
    app = FastAPI()
    app.add_middleware(middleware)
    app.add_middleware(SessionFromHeader)

    @app.get("/page")
    async def page():
        return Inertia.render("Page", {"title": "Hello"})

    return app


def session_header(session):
    return {"x-test-session": json.dumps(session)}


async def test_concurrent_requests_only_see_their_own_errors(container):
    app = make_app()
    a_ready, b_ready = asyncio.Event(), asyncio.Event()

    @app.get("/a")
    async def a():
        a_ready.set()
        await b_ready.wait()
        return Inertia.render("Page")

    @app.get("/b")
    async def b():
        b_ready.set()
        await a_ready.wait()
        return Inertia.render("Page")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response_a, response_b = await asyncio.gather(
            client.get("/a", headers={**INERTIA, **session_header({"errors": {"email": "A"}})}),
            client.get("/b", headers={**INERTIA, **session_header({"errors": {"name": "B"}})}),
        )

    assert response_a.json()["props"]["errors"] == {"email": "A"}
    assert response_b.json()["props"]["errors"] == {"name": "B"}
    assert "errors" not in Inertia.instance().shared_props


def test_boot_shares_reach_every_page_and_render_props_override(container):
    Inertia.share({"app_name": "Startkit", "title": "Shared"})
    client = TestClient(make_app())

    props = client.get("/page", headers=INERTIA).json()["props"]

    assert props == {"app_name": "Startkit", "title": "Hello", "errors": {}}


def test_share_during_request_does_not_leak(container):
    app = make_app()

    @app.get("/scoped")
    async def scoped():
        Inertia.share("only_here", True)
        return Inertia.render("Page")

    client = TestClient(app)

    assert client.get("/scoped", headers=INERTIA).json()["props"]["only_here"] is True
    assert "only_here" not in client.get("/page", headers=INERTIA).json()["props"]


def test_boot_version_is_used_for_conflict_and_page(container):
    container["vite"] = MagicMock(manifest_hash=MagicMock(return_value="vite-hash"))
    Inertia.version("1.0.0")
    client = TestClient(make_app())

    assert client.get("/page", headers={**INERTIA, Header.INERTIA_VERSION: "1.0.0"}).json()["version"] == "1.0.0"
    conflict = client.get("/page", headers={**INERTIA, Header.INERTIA_VERSION: "vite-hash"})
    assert conflict.status_code == 409


def test_vite_manifest_hash_is_the_fallback_version(container):
    container["vite"] = MagicMock(manifest_hash=MagicMock(return_value="vite-hash"))
    client = TestClient(make_app())

    response = client.get("/page", headers={**INERTIA, Header.INERTIA_VERSION: "vite-hash"})

    assert response.json()["version"] == "vite-hash"


def test_callable_version_is_evaluated_per_request(container):
    versions = iter(["v1", "v2"])
    Inertia.version(lambda: next(versions))
    client = TestClient(make_app())

    assert client.get("/page", headers={**INERTIA, Header.INERTIA_VERSION: "v1"}).status_code == 200
    assert client.get("/page", headers={**INERTIA, Header.INERTIA_VERSION: "v1"}).status_code == 409


def test_version_conflict_sends_location_and_version_and_keeps_flash(container):
    Inertia.version("v2")
    app = make_app()
    handled = []

    @app.get("/flash")
    async def flash(request: Request):
        handled.append(True)
        return Inertia.render("Page")

    session = {"_flash": {"success": "Saved"}, "errors": {"email": "Required"}}
    response = TestClient(app).get(
        "/flash", headers={**INERTIA, Header.INERTIA_VERSION: "v1", **session_header(session)}
    )

    assert response.status_code == 409
    assert response.headers[Header.INERTIA_LOCATION] == "http://testserver/flash"
    assert response.headers[Header.INERTIA_VERSION] == "v2"
    assert response.headers["Vary"] == Header.INERTIA
    assert handled == []
    assert SessionFromHeader.last == session


def test_boot_root_view_is_used_for_first_visit(container):
    Inertia.set_root_view("app.html")

    assert TestClient(make_app()).get("/page").json()["view"] == "app.html"


def test_middleware_subclass_root_view_wins(container):
    class AdminMiddleware(InertiaMiddleware):
        @classmethod
        def root_view(cls, request):
            return "admin.html"

    Inertia.set_root_view("app.html")

    assert TestClient(make_app(AdminMiddleware)).get("/page").json()["view"] == "admin.html"


def test_with_root_view_wins_for_its_response(container):
    Inertia.set_root_view("app.html")
    app = make_app()

    @app.get("/custom")
    async def custom():
        return Inertia.render("Page").with_root_view("custom.html")

    assert TestClient(app).get("/custom").json()["view"] == "custom.html"


def test_unsafe_props_render_inertly_and_round_trip():
    value = {"html": "</script><script>alert(1)</script>", "amp": "a & b > c", "separators": "\u2028\u2029"}

    encoded = html_safe_json(value)

    assert not set("<>&\u2028\u2029") & set(encoded)
    assert "\\u2028\\u2029" in encoded
    assert json.loads(encoded) == value


def empty_response_app():
    app = make_app()

    @app.put("/empty")
    async def empty_put():
        return Response(status_code=200)

    @app.post("/empty")
    async def empty_post():
        return Response(status_code=200)

    return TestClient(app)


def test_empty_inertia_response_redirects_back(container):
    response = empty_response_app().post("/empty", headers={**INERTIA, "referer": "/form"}, follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/form"


def test_empty_inertia_response_after_put_redirects_with_303_to_root(container):
    response = empty_response_app().put("/empty", headers=INERTIA, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_empty_non_inertia_response_is_unchanged(container):
    response = empty_response_app().post("/empty", follow_redirects=False)

    assert response.status_code == 200
    assert response.content == b""


def fragment_app():
    app = make_app()

    @app.post("/created")
    async def created():
        return Response(status_code=201, headers={"location": "/items/1#details"})

    @app.get("/fragment")
    async def fragment():
        return RedirectResponse("/page#section", status_code=302)

    return TestClient(app)


def test_created_with_fragment_location_becomes_inertia_redirect(container):
    response = fragment_app().post("/created", headers=INERTIA)

    assert response.status_code == 409
    assert response.headers[Header.INERTIA_REDIRECT] == "/items/1#details"


def test_prefetch_keeps_the_original_fragment_redirect(container):
    response = fragment_app().get("/fragment", headers={**INERTIA, Header.PURPOSE: "prefetch"}, follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/page#section"


def test_vary_header_is_appended_once(container):
    app = make_app()

    @app.get("/vary")
    async def vary():
        return Response("ok", headers={"Vary": "Accept-Encoding, x-inertia, Cookie"})

    @app.get("/vary-other")
    async def vary_other():
        return Response("ok", headers={"Vary": "Accept-Encoding, Cookie"})

    client = TestClient(app)

    assert client.get("/vary").headers["Vary"] == "Accept-Encoding, x-inertia, Cookie"
    assert client.get("/vary-other").headers["Vary"] == "Accept-Encoding, Cookie, X-Inertia"
