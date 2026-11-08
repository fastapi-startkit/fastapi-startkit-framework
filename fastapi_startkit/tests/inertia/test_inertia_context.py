"""Tests for Inertia context and middleware header behaviour (task #13).

Covers: current_request ContextVar, X-Inertia header presence,
non-Inertia passthrough, InertiaResponse.__call__ without middleware.
"""

import asyncio
import unittest
from unittest.mock import MagicMock

import httpx

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from fastapi_startkit.inertia.constant import Header
from fastapi_startkit.inertia.context import current_request
from fastapi_startkit.inertia.inertia import Inertia, InertiaResponse
from fastapi_startkit.inertia.middleware import InertiaMiddleware


class TestCurrentRequestContextVar(unittest.TestCase):
    def test_default_value_is_none(self):
        token = current_request.set(None)
        assert current_request.get() is None
        current_request.reset(token)

    def test_set_and_get_request(self):
        mock_req = MagicMock(spec=Request)
        token = current_request.set(mock_req)
        assert current_request.get() is mock_req
        current_request.reset(token)

    def test_reset_restores_previous(self):
        token = current_request.set(None)
        mock_req = MagicMock(spec=Request)
        token2 = current_request.set(mock_req)
        current_request.reset(token2)
        assert current_request.get() is None
        current_request.reset(token)


class TestInertiaResponseCallWithoutMiddleware(unittest.IsolatedAsyncioTestCase):
    async def test_call_without_middleware_raises_runtime_error(self):
        # Ensure context has no request set
        token = current_request.set(None)
        try:
            response = InertiaResponse(component="Test", shared_props={}, props={})
            with self.assertRaisesRegex(RuntimeError, "InertiaResponse requires InertiaMiddleware"):
                await response(scope={}, receive=None, send=None)
        finally:
            current_request.reset(token)


class TestMiddlewareHeaderBehaviour(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.add_middleware(InertiaMiddleware)

        @self.app.get("/ping")
        def ping():
            return {"ok": True}

        self.client = TestClient(self.app)
        Inertia._instance = None

    def test_non_inertia_request_passes_through(self):
        response = self.client.get("/ping")
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_inertia_request_gets_vary_header(self):
        response = self.client.get("/ping", headers={Header.INERTIA: "true"})
        assert response.headers.get("Vary") == Header.INERTIA

    def test_non_inertia_request_gets_vary_header(self):
        # Vary is set on all responses regardless of X-Inertia presence
        response = self.client.get("/ping")
        assert response.headers.get("Vary") == Header.INERTIA

    def test_x_inertia_header_name_constant(self):
        assert Header.INERTIA == "X-Inertia"

    def test_x_inertia_version_header_name_constant(self):
        assert Header.INERTIA_VERSION == "X-Inertia-Version"

    def test_x_inertia_location_header_name_constant(self):
        assert Header.INERTIA_LOCATION == "X-Inertia-Location"


class TestPerRequestRootViewAndVersion(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        Inertia._instance = None

    def tearDown(self):
        Inertia._instance = None

    async def test_concurrent_requests_do_not_share_root_view_or_version(self):
        app = FastAPI()
        app.add_middleware(InertiaMiddleware)
        both_set = asyncio.Barrier(2)

        @app.get("/{name}")
        async def page(name: str):
            Inertia.set_root_view(f"{name}.html")
            Inertia.version(f"v-{name}")
            await both_set.wait()
            return {"root_view": Inertia.instance().get_root_view(), "version": Inertia.get_version()}

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            first, second = await asyncio.gather(client.get("/first"), client.get("/second"))

        assert first.json() == {"root_view": "first.html", "version": "v-first"}
        assert second.json() == {"root_view": "second.html", "version": "v-second"}
        assert Inertia.instance().root_view == "index.html"
        assert Inertia.instance().version is None

    def test_set_root_view_and_version_outside_request_configure_defaults(self):
        Inertia.set_root_view("app.html")
        Inertia.version("v1")
        assert Inertia.instance().get_root_view() == "app.html"
        assert Inertia.get_version() == "v1"
