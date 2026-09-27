"""Tests for the FastAPI exception handlers (task #722).

Covers ``HTTPExceptionHandler`` (debug vs production rendering) and
``ValidationExceptionHandler`` (JSON vs redirect content negotiation). The
container and request/exception objects are faked so the tests need no live
application, session middleware, or network.
"""

import json
from types import SimpleNamespace
from unittest.mock import patch

from fastapi_startkit.container import Container
from fastapi_startkit.fastapi.exceptions import (
    HTTPExceptionHandler,
    ValidationExceptionHandler,
)


def _raised(message: str) -> Exception:
    """Return an exception instance carrying a real traceback."""
    try:
        raise ValueError(message)
    except ValueError as exc:
        return exc


class FakeRequest:
    def __init__(self, headers=None, scope=None, session=None):
        self.headers = headers or {}
        self.scope = scope or {}
        self.session = session if session is not None else {}


class FakeValidationError:
    def __init__(self, errors):
        self._errors = errors

    def errors(self):
        return self._errors


class TestHTTPExceptionHandler:
    async def test_debug_response_includes_trace(self):
        exc = _raised("boom")
        app = SimpleNamespace(is_debug=lambda: True)

        with patch.object(Container, "instance", return_value=app):
            response = await HTTPExceptionHandler().render(FakeRequest(), exc)

        assert response.status_code == 500
        body = json.loads(response.body)
        assert body["message"] == "boom"
        assert body["exception"].endswith("ValueError")
        assert body["file"] is not None
        assert body["line"] is not None
        assert isinstance(body["trace"], list) and body["trace"]

    async def test_production_response_hides_details(self):
        exc = _raised("boom")
        app = SimpleNamespace(is_debug=lambda: False)

        with patch.object(Container, "instance", return_value=app):
            response = await HTTPExceptionHandler().render(FakeRequest(), exc)

        assert response.status_code == 500
        assert json.loads(response.body) == {"message": "Server Error"}


class TestValidationExceptionHandler:
    def test_report_is_noop(self):
        assert ValidationExceptionHandler().report(FakeValidationError([])) is None

    async def test_json_request_returns_422(self):
        exc = FakeValidationError(
            [
                {"loc": ("body", "email"), "msg": "field required"},
                {"loc": ("body", "email"), "msg": "invalid email"},
            ]
        )
        request = FakeRequest(headers={"accept": "application/json"})

        response = await ValidationExceptionHandler().render(request, exc)

        assert response.status_code == 422
        assert json.loads(response.body) == {"errors": {"email": ["field required", "invalid email"]}}

    async def test_content_type_json_returns_422(self):
        exc = FakeValidationError([{"loc": ("body", "name"), "msg": "required"}])
        request = FakeRequest(headers={"content-type": "application/json; charset=utf-8"})

        response = await ValidationExceptionHandler().render(request, exc)

        assert response.status_code == 422
        assert json.loads(response.body) == {"errors": {"name": ["required"]}}

    async def test_non_json_flashes_errors_and_redirects(self):
        exc = FakeValidationError([{"loc": ("body", "name"), "msg": "required"}])
        request = FakeRequest(
            headers={"accept": "text/html", "referer": "/register"},
            scope={"session": {}},
            session={},
        )

        response = await ValidationExceptionHandler().render(request, exc)

        assert response.status_code == 303
        assert response.headers["location"] == "/register"
        assert request.session["errors"] == {"name": ["required"]}

    async def test_non_json_without_session_redirects_to_root(self):
        exc = FakeValidationError([{"loc": ("body", "name"), "msg": "required"}])
        request = FakeRequest(headers={"accept": "text/html"})

        response = await ValidationExceptionHandler().render(request, exc)

        assert response.status_code == 303
        assert response.headers["location"] == "/"
