import unittest
import warnings
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from fastapi_startkit.inertia.constant import Header
from fastapi_startkit.inertia.inertia import Inertia
from fastapi_startkit.inertia.middleware import InertiaMiddleware
from fastapi_startkit.inertia.session import ArraySession, InertiaSessionWarning


def build_app(session=None) -> FastAPI:
    app = FastAPI()
    if session is None:
        app.add_middleware(InertiaMiddleware)
    else:
        app.add_middleware(InertiaMiddleware, session=session)

    @app.post("/back-with-errors")
    def back_with_errors():
        return Inertia.back_with_errors({"email": ["Required"]})

    @app.get("/page")
    def page():
        return Inertia.render("Users/Index")

    return app


class TestArraySessionFallback(unittest.TestCase):
    def setUp(self):
        Inertia._instance = None
        container_patch = patch("fastapi_startkit.application.app")
        mock_app_getter = container_patch.start()
        self.addCleanup(container_patch.stop)
        mock_app_getter.return_value = MagicMock(has=MagicMock(return_value=False))

    def test_array_session_carries_errors_to_the_next_page(self):
        client = TestClient(build_app(session=ArraySession()))

        client.post("/back-with-errors", follow_redirects=False)
        response = client.get("/page", headers={Header.INERTIA: "true"})

        self.assertEqual(response.json()["props"]["errors"], {"email": "Required"})

    def test_array_session_is_not_used_when_scope_already_has_a_session(self):
        store = ArraySession()
        existing = ArraySession()
        app = build_app(session=store)

        @app.middleware("http")
        async def existing_session(request, call_next):
            request.scope["session"] = existing
            return await call_next(request)

        client = TestClient(app)
        client.post("/back-with-errors", follow_redirects=False)

        self.assertEqual(store, {})
        self.assertEqual(existing["errors"], {"default": {"email": ["Required"]}})

    def test_queueing_errors_without_session_warns_and_drops_them(self):
        client = TestClient(build_app())

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            response = client.post("/back-with-errors", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(any(issubclass(w.category, InertiaSessionWarning) for w in caught))
        self.assertIn("SessionMiddleware", str(caught[0].message))

    def test_queueing_errors_with_session_does_not_warn(self):
        client = TestClient(build_app(session=ArraySession()))

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            client.post("/back-with-errors", follow_redirects=False)

        self.assertFalse([w for w in caught if issubclass(w.category, InertiaSessionWarning)])
