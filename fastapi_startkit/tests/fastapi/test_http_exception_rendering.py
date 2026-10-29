import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException

from fastapi_startkit.application import Application
from fastapi_startkit.container.container import Container
from fastapi_startkit.fastapi import FastAPIProvider
from fastapi_startkit.fastapi.testing import HttpTestCase
from fastapi_startkit.masoniteorm.exceptions import ModelNotFoundException


def make_application(base_path: Path) -> Application:
    app = Application(base_path=base_path, env="testing", providers=[FastAPIProvider])

    @app.fastapi.get("/email-taken")
    def email_taken():
        raise HTTPException(400, "Email taken", headers={"X-Reason": "duplicate"})

    @app.fastapi.get("/teapot")
    def teapot():
        raise StarletteHTTPException(418, "I'm a teapot")

    @app.fastapi.get("/missing-model")
    def missing_model():
        raise ModelNotFoundException("User with primary key 7 not found.")

    return app


class HttpExceptionRenderingTest(HttpTestCase):
    def get_application(self) -> Application:
        if not hasattr(self, "_application"):
            self._tmp_dir = tempfile.TemporaryDirectory()
            self.addCleanup(self._tmp_dir.cleanup)
            original_instance = Container._instance
            self.addCleanup(lambda: setattr(Container, "_instance", original_instance))
            self._application = make_application(Path(self._tmp_dir.name))
        return self._application

    async def test_http_exception_keeps_status_detail_and_headers(self):
        response = await self.get("/email-taken")

        response.assert_status(400)
        self.assertEqual(response.json()["detail"], "Email taken")
        self.assertEqual(response.headers["X-Reason"], "duplicate")

    async def test_starlette_http_exception_keeps_status_and_detail(self):
        response = await self.get("/teapot")

        response.assert_status(418)
        self.assertEqual(response.json()["detail"], "I'm a teapot")

    async def test_unknown_route_returns_404(self):
        response = await self.get("/does-not-exist")

        response.assert_status(404)
        self.assertEqual(response.json()["detail"], "Not Found")

    async def test_model_not_found_returns_404(self):
        response = await self.get("/missing-model")

        response.assert_status(404)
        self.assertEqual(response.json()["detail"], "User with primary key 7 not found.")


class FastAPITitleTest(HttpTestCase):
    def get_application(self) -> Application:
        if not hasattr(self, "_application"):
            self._tmp_dir = tempfile.TemporaryDirectory()
            self.addCleanup(self._tmp_dir.cleanup)
            original_instance = Container._instance
            self.addCleanup(lambda: setattr(Container, "_instance", original_instance))
            with patch.dict(os.environ, {"APP_NAME": "Acme Portal"}):
                self._application = Application(
                    base_path=Path(self._tmp_dir.name), env="testing", providers=[FastAPIProvider]
                )
        return self._application

    async def test_title_comes_from_app_name(self):
        response = await self.get("/openapi.json")

        self.assertEqual(response.json()["info"]["title"], "Acme Portal")


def test_title_defaults_to_fastapi_startkit():
    original_instance = Container._instance
    try:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, clear=False) as environ:
            environ.pop("APP_NAME", None)
            app = Application(base_path=Path(tmp), env="testing", providers=[FastAPIProvider])
            assert app.fastapi.title == "FastAPI Startkit"
    finally:
        Container._instance = original_instance
