import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient
from pydantic import BaseModel

from fastapi_startkit.fastapi.exceptions import ValidationExceptionHandler
from fastapi_startkit.inertia import Inertia, InertiaMiddleware
from fastapi_startkit.inertia.constant import Header
from fastapi_startkit.inertia.testing import FakeSessionMiddleware, assert_inertia

INERTIA = {Header.INERTIA: "true"}


class FakeTemplates:
    def TemplateResponse(self, request, name, context):
        return HTMLResponse(json.dumps({"view": name, "page": context["page"]}))


class UserForm(BaseModel):
    name: str
    email: str


@pytest.fixture(autouse=True)
def container():
    Inertia._instance = None
    services = {"templates": FakeTemplates()}
    mock = MagicMock()
    mock.has.side_effect = lambda key: key in services
    mock.make.side_effect = lambda key: services[key]
    with patch("fastapi_startkit.application.app", return_value=mock):
        yield
    Inertia._instance = None


def make_client(session: dict) -> TestClient:
    app = FastAPI()
    app.add_middleware(InertiaMiddleware)
    app.add_middleware(FakeSessionMiddleware, session=session)

    async def render_validation_error(request, exc):
        return await ValidationExceptionHandler().render(request, exc)

    app.add_exception_handler(RequestValidationError, render_validation_error)

    @app.get("/users/create")
    async def create():
        return Inertia.render("Users/Create")

    @app.post("/users")
    async def store(form: UserForm):
        return Inertia.redirect("/users/create", status_code=303)

    return TestClient(app)


def test_inertia_validation_failure_redirects_back_with_303():
    response = make_client({}).post(
        "/users",
        json={},
        headers={**INERTIA, "referer": "http://testserver/users/create"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "http://testserver/users/create"


def test_inertia_validation_failure_flashes_errors_to_the_next_page():
    response = make_client({}).post(
        "/users",
        json={"name": "Taylor"},
        headers={**INERTIA, "referer": "http://testserver/users/create"},
    )

    assert response.status_code == 200
    assert_inertia(response).component("Users/Create").equals("errors", {"email": "Field required"})


def test_inertia_validation_failure_respects_the_error_bag_header():
    response = make_client({}).post(
        "/users",
        json={"name": "Taylor"},
        headers={**INERTIA, Header.ERROR_BAG: "createUser", "referer": "http://testserver/users/create"},
    )

    assert_inertia(response).equals("errors", {"createUser": {"email": "Field required"}})


def test_inertia_validation_failure_stores_errors_in_the_named_bag():
    session: dict = {}

    make_client(session).post(
        "/users",
        json={},
        headers={**INERTIA, Header.ERROR_BAG: "createUser"},
        follow_redirects=False,
    )

    assert session["_inertia_errors"] == {"createUser": {"name": ["Field required"], "email": ["Field required"]}}


def test_inertia_validation_failure_without_referer_redirects_to_root():
    response = make_client({}).post("/users", json={}, headers=INERTIA, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_inertia_validation_failure_ignores_foreign_referer():
    response = make_client({}).post(
        "/users",
        json={},
        headers={**INERTIA, "referer": "https://evil.example/phish"},
        follow_redirects=False,
    )

    assert response.headers["location"] == "/"


def test_json_validation_failure_without_inertia_still_returns_422():
    response = make_client({}).post("/users", json={"name": "Taylor"})

    assert response.status_code == 422
    assert response.json() == {"errors": {"email": ["Field required"]}}
