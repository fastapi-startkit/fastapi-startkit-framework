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

    @app.post("/save")
    def save():
        Inertia.preserve_fragment()
        return Inertia.back()

    @app.get("/page")
    def page():
        return Inertia.render("Users/Index")

    return app


class TestPreserveFragment(unittest.TestCase):
    def setUp(self):
        Inertia._instance = None
        container_patch = patch("fastapi_startkit.application.app")
        mock_app_getter = container_patch.start()
        self.addCleanup(container_patch.stop)
        mock_app_getter.return_value = MagicMock(has=MagicMock(return_value=False))

    def page(self, client: TestClient) -> dict:
        return client.get("/page", headers={Header.INERTIA: "true"}).json()

    def test_page_preserve_fragment_is_false_by_default(self):
        client = TestClient(build_app(session=ArraySession()))

        self.assertIs(self.page(client)["preserveFragment"], False)

    def test_flag_set_before_redirect_reaches_the_next_page(self):
        client = TestClient(build_app(session=ArraySession()))

        response = client.post("/save", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertIs(self.page(client)["preserveFragment"], True)

    def test_flag_is_consumed_by_the_page_it_reaches(self):
        client = TestClient(build_app(session=ArraySession()))

        client.post("/save", follow_redirects=False)
        self.page(client)

        self.assertIs(self.page(client)["preserveFragment"], False)

    def test_queueing_without_session_warns(self):
        client = TestClient(build_app())

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            client.post("/save", follow_redirects=False)

        self.assertTrue(any(issubclass(w.category, InertiaSessionWarning) for w in caught))
        self.assertIs(self.page(client)["preserveFragment"], False)
