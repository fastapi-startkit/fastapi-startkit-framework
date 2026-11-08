import asyncio
import json

import httpx
import pytest
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

from fastapi_startkit.vite import Vite, ViteMiddleware


MANIFEST = {
    "resources/js/app.js": {"file": "assets/app.js", "src": "resources/js/app.js", "isEntry": True},
    "resources/js/admin.js": {"file": "assets/admin.js", "src": "resources/js/admin.js", "isEntry": True},
}


@pytest.fixture(autouse=True)
def _clear_manifest_cache():
    Vite._manifests.clear()
    yield
    Vite._manifests.clear()


@pytest.fixture
def vite(tmp_path):
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "manifest.json").write_text(json.dumps(MANIFEST))
    return Vite(str(tmp_path))


def client(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


class LinkHeaderMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, vite):
        super().__init__(app)
        self.vite = vite

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["link"] = ", ".join(sorted(self.vite.preloaded_assets()))
        return response


def scoped_app(vite, barrier=None):
    app = FastAPI()

    @app.get("/{name}")
    async def page(name: str, nonce: str | None = None):
        if nonce:
            vite.use_csp_nonce(nonce)
        vite.preloaded_assets()[f"/req-{name}"] = []
        if barrier:
            await barrier.wait()
        return {"assets": sorted(vite.preloaded_assets()), "nonce": vite.csp_nonce()}

    return app


class TestRequestScope:
    def test_scope_starts_empty_and_restores_outer_state(self, vite):
        vite.preloaded_assets()["/outer"] = []
        with vite.request_scope():
            assert vite.preloaded_assets() == {}
            vite.preloaded_assets()["/inner"] = []
        assert vite.preloaded_assets() == {"/outer": []}

    def test_nested_scope_reuses_outer_request_state(self, vite):
        with vite.request_scope():
            vite.preloaded_assets()["/a"] = []
            with vite.request_scope():
                assert vite.preloaded_assets() == {"/a": []}

    def test_nonce_set_outside_a_request_is_the_process_default(self, vite):
        vite.use_csp_nonce("boot")
        with vite.request_scope():
            assert vite.csp_nonce() == "boot"
            vite.use_csp_nonce("request")
            assert vite.csp_nonce() == "request"
        assert vite.csp_nonce() == "boot"

    async def test_nonce_set_in_a_separate_startup_task_reaches_requests(self, vite):
        async def lifespan():
            vite.use_csp_nonce("lifespan")

        await asyncio.create_task(lifespan())
        app = scoped_app(vite)
        app.add_middleware(ViteMiddleware, vite=vite)

        async with client(app) as http:
            response = await http.get("/a")

        assert response.json()["nonce"] == "lifespan"


class TestViteMiddleware:
    async def test_outer_render_does_not_leak_into_concurrent_requests(self, vite):
        vite("resources/js/app.js")
        app = scoped_app(vite, asyncio.Barrier(2))
        app.add_middleware(ViteMiddleware, vite=vite)

        async with client(app) as http:
            first, second = await asyncio.gather(http.get("/a"), http.get("/b"))

        assert first.json()["assets"] == ["/req-a"]
        assert second.json()["assets"] == ["/req-b"]

    async def test_concurrent_requests_keep_their_own_nonce(self, vite):
        vite.use_csp_nonce("default")
        app = scoped_app(vite, asyncio.Barrier(3))
        app.add_middleware(ViteMiddleware, vite=vite)

        async with client(app) as http:
            first, second, third = await asyncio.gather(
                http.get("/a", params={"nonce": "nonce-a"}),
                http.get("/b", params={"nonce": "nonce-b"}),
                http.get("/c"),
            )

        assert first.json()["nonce"] == "nonce-a"
        assert second.json()["nonce"] == "nonce-b"
        assert third.json()["nonce"] == "default"
        assert vite.csp_nonce() == "default"

    async def test_inner_middleware_reads_preloaded_assets_after_call_next(self, vite):
        app = FastAPI()

        @app.get("/")
        async def page():
            return {"html": vite("resources/js/app.js")}

        app.add_middleware(LinkHeaderMiddleware, vite=vite)
        app.add_middleware(ViteMiddleware, vite=vite)

        async with client(app) as http:
            response = await http.get("/")

        assert response.headers["link"] == "/build/assets/app.js"

    async def test_outermost_vite_middleware_wraps_middleware_added_after_provider(self, vite):
        app = FastAPI()

        @app.get("/")
        async def page():
            return {"html": vite("resources/js/admin.js")}

        app.add_middleware(ViteMiddleware, vite=vite)
        app.add_middleware(LinkHeaderMiddleware, vite=vite)
        app.add_middleware(ViteMiddleware, vite=vite)

        async with client(app) as http:
            response = await http.get("/")

        assert response.headers["link"] == "/build/assets/admin.js"
        assert vite.preloaded_assets() == {}

    async def test_lifespan_passes_through_without_a_scope(self, vite):
        async def inner(scope, receive, send):
            vite.preloaded_assets()["/lifespan"] = []

        await ViteMiddleware(inner, vite=vite)({"type": "lifespan"}, None, None)

        assert vite.preloaded_assets() == {"/lifespan": []}

    async def test_resolves_vite_from_the_container_when_not_given(self, vite, monkeypatch):
        container = type("Container", (), {"make": lambda self, key: vite})()
        monkeypatch.setattr("fastapi_startkit.application.app", lambda: container)
        app = scoped_app(vite)
        app.add_middleware(ViteMiddleware)

        async with client(app) as http:
            response = await http.get("/a")

        assert response.json()["assets"] == ["/req-a"]
        assert vite.preloaded_assets() == {}


def test_provider_registers_vite_middleware(tmp_path):
    from fastapi_startkit.application import Application
    from fastapi_startkit.vite import ViteProvider

    app = Application(base_path=tmp_path, providers=[ViteProvider])

    assert ViteMiddleware in [m.cls for m in app.fastapi.user_middleware]
