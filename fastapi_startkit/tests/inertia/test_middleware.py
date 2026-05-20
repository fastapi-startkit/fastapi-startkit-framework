import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from fastapi_startkit.inertia.middleware import InertiaMiddleware
from fastapi_startkit.inertia.constant import Header
from fastapi_startkit.inertia.inertia import Inertia


class TestInertiaMiddleware(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.add_middleware(InertiaMiddleware)

        @self.app.get("/test")
        async def test_route():
            return {"message": "ok"}

        @self.app.post("/redirect")
        async def test_redirect():
            from fastapi.responses import RedirectResponse

            return RedirectResponse(url="/test", status_code=302)

        @self.app.put("/redirect-put")
        async def test_redirect_put():
            from fastapi.responses import RedirectResponse

            return RedirectResponse(url="/test", status_code=302)

        @self.app.get("/fragment-redirect")
        async def test_fragment_redirect():
            from fastapi.responses import RedirectResponse

            return RedirectResponse(url="/test#section", status_code=302)

        self.client = TestClient(self.app)
        # Reset Inertia singleton
        Inertia._instance = None

    def test_middleware_adds_vary_header(self):
        response = self.client.get("/test")
        self.assertEqual(response.headers["Vary"], Header.INERTIA)

    @patch("fastapi_startkit.application.app")
    def test_middleware_version_conflict(self, mock_app_getter):
        # Setup mock container
        mock_container = MagicMock()
        mock_app_getter.return_value = mock_container

        # Mock Vite version
        mock_vite = MagicMock()
        mock_vite.manifest_hash.return_value = "v2"
        mock_container.has.side_effect = lambda k: k == "vite"
        mock_container.make.side_effect = lambda k: mock_vite if k == "vite" else None

        # Request with old version
        response = self.client.get("/test", headers={Header.INERTIA: "true", Header.INERTIA_VERSION: "v1"})

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.headers[Header.INERTIA_LOCATION], "http://testserver/test")

    def test_middleware_changes_302_to_303_on_put_patch_delete(self):
        # POST stays 302
        response = self.client.post("/redirect", follow_redirects=False)
        self.assertEqual(response.status_code, 302)

        # PUT changes to 303
        response = self.client.put("/redirect-put", follow_redirects=False, headers={Header.INERTIA: "true"})
        self.assertEqual(response.status_code, 303)

    def test_middleware_redirect_with_fragment(self):
        response = self.client.get("/fragment-redirect", headers={Header.INERTIA: "true"})

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.headers[Header.INERTIA_REDIRECT], "/test#section")

    @patch("fastapi_startkit.application.app")
    def test_middleware_resolves_validation_errors_from_session(self, mock_app_getter):
        # We need a fresh app and session-enabled middleware
        from fastapi import Request
        from starlette.middleware.sessions import SessionMiddleware

        app = FastAPI()
        app.add_middleware(InertiaMiddleware)
        app.add_middleware(SessionMiddleware, secret_key="secret")

        @app.get("/set-errors")
        def set_errors(request: Request):
            request.session["errors"] = {"email": "Required"}
            return "ok"

        @app.get("/check-errors")
        def check_errors(request: Request):
            # Middleware should have shared the errors from the session
            # We access the singleton via the facade
            return Inertia.instance().shared_props.get("errors", {})

        # Mock container for version check (avoiding 409)
        mock_container = MagicMock()
        mock_app_getter.return_value = mock_container
        mock_container.has.return_value = False

        client = TestClient(app)

        # Reset Inertia singleton for this specific test
        Inertia._instance = None

        # 1. First request sets the errors in session
        client.get("/set-errors")

        # 2. Second request should have errors shared by middleware
        response = client.get("/check-errors")
        self.assertEqual(response.json(), {"email": "Required"})
