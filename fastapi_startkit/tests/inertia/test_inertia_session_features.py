import json
import logging
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError
from starlette.responses import Response

from fastapi_startkit.inertia import Inertia, InertiaMiddleware, ValidationErrors
from fastapi_startkit.inertia.constant import Header
from fastapi_startkit.inertia.redirect import InertiaRedirect
from fastapi_startkit.inertia.testing import FakeSessionMiddleware

INERTIA = {Header.INERTIA: "true"}


class FakeTemplates:
    def TemplateResponse(self, request, name, context):
        return HTMLResponse(json.dumps({"view": name, "page": context["page"]}))


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


def make_app(session: dict | None = None, middleware: type[InertiaMiddleware] = InertiaMiddleware) -> FastAPI:
    app = FastAPI()
    app.add_middleware(middleware)
    if session is not None:
        app.add_middleware(FakeSessionMiddleware, session=session)

    @app.get("/page")
    async def page():
        return Inertia.render("Page")

    return app


def test_location_on_inertia_visit_returns_409():
    app = make_app()

    @app.get("/external")
    async def external():
        return Inertia.location("https://example.com/pay")

    response = TestClient(app).get("/external", headers=INERTIA)

    assert response.status_code == 409
    assert response.headers[Header.INERTIA_LOCATION] == "https://example.com/pay"


def test_location_on_normal_visit_redirects():
    app = make_app()

    @app.get("/external")
    async def external():
        return Inertia.location("https://example.com/pay")

    response = TestClient(app).get("/external", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com/pay"


def test_location_without_middleware_redirects():
    response = Inertia.location("/elsewhere")

    assert response.status_code == 302


def back_app(session: dict) -> TestClient:
    app = make_app(session)

    @app.post("/back")
    async def back():
        return Inertia.back()

    @app.put("/invalid")
    async def invalid():
        return Inertia.back_with_errors({"email": ["Required", "Invalid"]})

    @app.post("/redirect")
    async def redirect():
        return Inertia.redirect("/page", status_code=303)

    return TestClient(app)


def test_back_uses_referer_and_falls_back_to_root():
    client = back_app({})

    with_referer = client.post("/back", headers={"referer": "/form"}, follow_redirects=False)
    without_referer = client.post("/back", follow_redirects=False)

    assert isinstance(Inertia.back(), InertiaRedirect)
    assert with_referer.headers["location"] == "/form"
    assert without_referer.headers["location"] == "/"


@pytest.mark.parametrize(
    ("referer", "expected"),
    [
        ("http://testserver/form?step=2", "http://testserver/form?step=2"),
        ("/form", "/form"),
        ("https://evil.example/phish", "/"),
        ("http://testserver.evil.example/form", "/"),
        ("//evil.example/form", "/"),
        ("javascript:alert(1)", "/"),
        ("form", "/"),
    ],
)
def test_back_only_follows_same_origin_referer(referer, expected):
    response = back_app({}).post("/back", headers={"referer": referer}, follow_redirects=False)

    assert response.headers["location"] == expected


def test_empty_response_redirect_ignores_cross_origin_referer():
    app = make_app({})

    @app.post("/empty")
    async def empty():
        return Response(status_code=200)

    response = TestClient(app).post(
        "/empty", headers={**INERTIA, "referer": "https://evil.example/"}, follow_redirects=False
    )

    assert response.headers["location"] == "/"


def test_flash_survives_converted_redirects():
    app = make_app({})

    @app.put("/empty")
    async def empty():
        Inertia.flash("saved", True)
        return Response(status_code=200)

    @app.post("/fragment")
    async def fragment():
        return Inertia.redirect("/page#details").flash("anchored", True)

    client = TestClient(app)

    converted = client.put("/empty", headers={**INERTIA, "referer": "/page"}, follow_redirects=False)
    after_empty = client.get("/page", headers=INERTIA).json()
    fragment = client.post("/fragment", headers=INERTIA, follow_redirects=False)
    after_fragment = client.get("/page", headers=INERTIA).json()

    assert converted.status_code == 303
    assert after_empty["flash"] == {"saved": True}
    assert fragment.status_code == 409
    assert after_fragment["flash"] == {"anchored": True}


def test_errors_survive_a_redirect_hop():
    app = make_app({})

    @app.post("/invalid")
    async def invalid():
        return Inertia.back_with_errors({"email": "Required"})

    @app.get("/hop")
    async def hop():
        return Inertia.redirect("/page")

    client = TestClient(app)
    client.post("/invalid", headers={**INERTIA, "referer": "/hop"}, follow_redirects=False)
    hop = client.get("/hop", headers=INERTIA, follow_redirects=False)
    page = client.get("/page", headers=INERTIA).json()

    assert hop.status_code == 302
    assert page["props"]["errors"] == {"email": "Required"}


def test_errors_set_during_the_request_render_on_that_page():
    app = make_app({})

    @app.get("/form")
    async def form():
        Inertia.with_errors({"email": "Required"})
        return Inertia.render("Form")

    assert TestClient(app).get("/form", headers=INERTIA).json()["props"]["errors"] == {"email": "Required"}


def test_redirect_uses_given_status():
    response = back_app({}).post("/redirect", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/page"


def test_back_with_errors_shows_first_error_on_next_page():
    client = back_app({})

    redirect = client.put("/invalid", headers={**INERTIA, "referer": "/page"}, follow_redirects=False)
    first = client.get("/page", headers=INERTIA).json()
    second = client.get("/page", headers=INERTIA).json()

    assert redirect.status_code == 303
    assert first["props"]["errors"] == {"email": "Required"}
    assert second["props"]["errors"] == {}


def test_error_bag_header_nests_errors():
    client = back_app({})

    client.put("/invalid", headers={**INERTIA, "referer": "/page"}, follow_redirects=False)
    page = client.get("/page", headers={**INERTIA, Header.ERROR_BAG: "login"}).json()

    assert page["props"]["errors"] == {"login": {"email": "Required"}}


def test_with_all_errors_returns_lists():
    class AllErrorsMiddleware(InertiaMiddleware):
        with_all_errors = True

    session = {}
    app = make_app(session, AllErrorsMiddleware)

    @app.post("/invalid")
    async def invalid():
        return Inertia.redirect("/page").with_errors({"email": "Required"}).with_errors({"email": "Invalid"})

    client = TestClient(app)
    client.post("/invalid", follow_redirects=False)

    assert client.get("/page", headers=INERTIA).json()["props"]["errors"] == {"email": ["Required", "Invalid"]}


def test_named_bags_without_default_are_returned_by_name():
    session = {}
    app = make_app(session)

    @app.post("/invalid")
    async def invalid():
        Inertia.with_errors_in("login", {"email": "Required"})
        return Inertia.redirect("/page").with_errors_in("register", {"name": "Taken"})

    client = TestClient(app)
    client.post("/invalid", follow_redirects=False)

    errors = client.get("/page", headers=INERTIA).json()["props"]["errors"]
    assert errors == {"login": {"email": "Required"}, "register": {"name": "Taken"}}


def test_legacy_session_errors_are_the_default_bag():
    session = {"errors": {"email": ["Required"]}}

    page = TestClient(make_app(session)).get("/page", headers=INERTIA).json()

    assert page["props"]["errors"] == {"email": "Required"}


def test_validation_errors_helper():
    errors = ValidationErrors({"email": "Required"}).add("email", "Invalid").merge({"name": ["Taken"]})

    assert errors.has("email")
    assert not errors.has("age")
    assert errors.first("email") == "Required"
    assert errors.first("age") is None
    assert errors.get("email") == ["Required", "Invalid"]
    assert errors.all() == {"email": ["Required", "Invalid"], "name": ["Taken"]}
    assert errors.firsts() == {"email": "Required", "name": "Taken"}
    assert ValidationErrors.make(errors).all() == errors.all()
    assert bool(errors)
    assert not ValidationErrors()


def test_validation_errors_from_pydantic_and_request_errors():
    class Signup(BaseModel):
        email: str

    with pytest.raises(ValidationError) as caught:
        Signup.model_validate({})
    request_error = RequestValidationError([{"loc": ("body", "user", "email"), "msg": "Required", "type": "missing"}])

    assert ValidationErrors.make(caught.value).get("email") == ["Field required"]
    assert ValidationErrors.make(request_error).all() == {"user.email": ["Required"]}


def flash_app(session: dict | None) -> FastAPI:
    app = make_app(session)

    @app.post("/save")
    async def save():
        Inertia.flash("success", "Saved")
        return Inertia.redirect("/page")

    @app.get("/inline")
    async def inline():
        Inertia.flash({"notice": "Queued"})
        return Inertia.render("Page").flash("toast", "Inline")

    return app


def test_flash_before_redirect_appears_once_on_next_page():
    client = TestClient(flash_app({}))

    client.post("/save", follow_redirects=False)
    first = client.get("/page", headers=INERTIA).json()
    second = client.get("/page", headers=INERTIA).json()

    assert first["flash"] == {"success": "Saved"}
    assert "flash" not in second
    assert "success" not in first["props"]


def test_flash_during_render_appears_on_that_page():
    page = TestClient(flash_app({})).get("/inline").json()["page"]

    assert page["flash"] == {"notice": "Queued", "toast": "Inline"}


def test_flash_survives_version_reload():
    Inertia.version("v2")
    client = TestClient(flash_app({}))

    client.post("/save", follow_redirects=False)
    conflict = client.get("/page", headers={**INERTIA, Header.INERTIA_VERSION: "v1"})
    page = client.get("/page", headers={**INERTIA, Header.INERTIA_VERSION: "v2"}).json()

    assert conflict.status_code == 409
    assert page["flash"] == {"success": "Saved"}


def test_flash_without_session_logs_warning_and_still_renders(caplog):
    with caplog.at_level(logging.WARNING, logger="fastapi_startkit.inertia"):
        page = TestClient(flash_app(None)).get("/inline", headers=INERTIA).json()

    assert page["flash"] == {"notice": "Queued", "toast": "Inline"}
    assert "without a session" in caplog.text


def test_session_helpers_require_middleware():
    with pytest.raises(RuntimeError, match="InertiaMiddleware"):
        Inertia.flash("success", "Saved")


def test_encrypt_history_globally_and_per_response():
    app = make_app()

    @app.get("/plain")
    async def plain():
        return Inertia.render("Page").encrypt_history(False)

    @app.get("/scoped")
    async def scoped():
        Inertia.encrypt_history(False)
        return Inertia.render("Page")

    client = TestClient(app)

    assert client.get("/page", headers=INERTIA).json()["encryptHistory"] is False
    Inertia.encrypt_history()
    assert client.get("/page", headers=INERTIA).json()["encryptHistory"] is True
    assert client.get("/plain", headers=INERTIA).json()["encryptHistory"] is False
    assert client.get("/scoped", headers=INERTIA).json()["encryptHistory"] is False
    assert Inertia.instance().encrypt_history_enabled is True


def test_encrypt_history_per_response_when_disabled_globally():
    app = make_app()

    @app.get("/secret")
    async def secret():
        return Inertia.render("Page").encrypt_history()

    assert TestClient(app).get("/secret", headers=INERTIA).json()["encryptHistory"] is True


def test_clear_history_and_preserve_fragment_apply_to_next_page_only():
    app = make_app({})

    @app.post("/logout")
    async def logout():
        Inertia.clear_history()
        return Inertia.redirect("/page").preserve_fragment()

    @app.post("/chained")
    async def chained():
        Inertia.preserve_fragment()
        return Inertia.redirect("/page").clear_history().flash("bye", True)

    client = TestClient(app)

    client.post("/logout", follow_redirects=False)
    first = client.get("/page", headers=INERTIA).json()
    second = client.get("/page", headers=INERTIA).json()
    client.post("/chained", follow_redirects=False)
    third = client.get("/page", headers=INERTIA).json()

    assert first["clearHistory"] is True
    assert first["preserveFragment"] is True
    assert second["clearHistory"] is False
    assert "preserveFragment" not in second
    assert third["clearHistory"] is True and third["preserveFragment"] is True
    assert third["flash"] == {"bye": True}


def test_fake_session_is_shared_between_requests():
    session: dict = {}
    app = make_app(session)

    @app.post("/remember")
    async def remember(request: Request):
        request.session["user"] = 1
        return {}

    TestClient(app).post("/remember")

    assert session["user"] == 1
    assert FakeSessionMiddleware(app).session == {}
