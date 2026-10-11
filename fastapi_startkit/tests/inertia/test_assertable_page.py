import html
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from fastapi_startkit.inertia import Inertia, InertiaMiddleware
from fastapi_startkit.inertia.constant import Header
from fastapi_startkit.inertia.encoding import html_safe_json
from fastapi_startkit.inertia.testing import AssertablePage, FakeSessionMiddleware, assert_inertia

INERTIA = {Header.INERTIA: "true"}


class ScriptTemplates:
    def TemplateResponse(self, request, name, context):
        page = html_safe_json(context["page"])
        return HTMLResponse(
            f'<html><body><script data-page="app" type="application/json">{page}</script></body></html>'
        )


@pytest.fixture(autouse=True)
def container():
    Inertia._instance = None
    Inertia.version("v1")
    services = {"templates": ScriptTemplates()}
    mock = MagicMock()
    mock.has.side_effect = lambda key: key in services
    mock.make.side_effect = lambda key: services[key]
    with patch("fastapi_startkit.application.app", return_value=mock):
        yield
    Inertia._instance = None


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.add_middleware(InertiaMiddleware)
    app.add_middleware(FakeSessionMiddleware, session={})

    @app.get("/users")
    async def index():
        Inertia.flash("message", "Saved <b>")
        return Inertia.render(
            "Users/Index",
            {
                "users": [{"name": "Taylor", "roles": ["admin"]}, {"name": "Jess", "roles": []}],
                "filters": {"search": None},
                "stats": Inertia.defer(lambda: {"count": 2}, "metrics"),
                "chart": Inertia.defer(lambda: [], "metrics"),
            },
        )

    return TestClient(app)


@pytest.fixture(params=["html", "json"])
def page(request, client) -> AssertablePage:
    headers = {**INERTIA, Header.INERTIA_VERSION: "v1"} if request.param == "json" else {}
    return assert_inertia(client.get("/users?page=2", headers=headers))


def test_parses_html_and_json_responses_into_the_same_page(client):
    html_page = assert_inertia(client.get("/users")).page
    json_page = assert_inertia(client.get("/users", headers={**INERTIA, Header.INERTIA_VERSION: "v1"})).page

    assert html_page["props"] == json_page["props"]
    assert html_page["component"] == json_page["component"] == "Users/Index"


def test_parses_a_data_page_attribute_root():
    page = {"component": "Home", "props": {"title": "<Hi & bye>"}, "url": "/", "version": ""}
    body = f'<div id="app" data-page="{html.escape(html_safe_json(page))}"></div>'

    assert_inertia(HTMLResponse(body)).component("Home").equals("title", "<Hi & bye>")


def test_rejects_a_response_without_a_page():
    with pytest.raises(AssertionError, match="Inertia page"):
        assert_inertia(HTMLResponse("<html></html>"))


def test_component_url_and_version(page):
    page.component("Users/Index").url("/users?page=2").version("v1")


def test_assertions_chain_and_return_the_page(page):
    assert page.has("users").has_count("users", 2).missing("secret").equals("users.0.name", "Taylor") is page


def test_component_mismatch_message(page):
    with pytest.raises(AssertionError, match="Expected component 'Users/Show', got 'Users/Index'"):
        page.component("Users/Show")


def test_url_mismatch_message(page):
    with pytest.raises(AssertionError, match="Expected url '/users', got '/users\\?page=2'"):
        page.url("/users")


def test_version_mismatch_message(page):
    with pytest.raises(AssertionError, match="Expected version 'v2', got 'v1'"):
        page.version("v2")


def test_has_follows_dot_paths_and_list_indexes(page):
    page.has("users.1.roles").has("filters.search")


def test_has_reports_the_missing_path(page):
    with pytest.raises(AssertionError, match="Expected prop 'users.5.name' to exist"):
        page.has("users.5.name")


def test_has_count(page):
    page.has_count("users", 2).has_count("users.0.roles", 1)


def test_has_count_reports_the_actual_size(page):
    with pytest.raises(AssertionError, match="Expected prop 'users' to have 3 items, got 2"):
        page.has_count("users", 3)


def test_has_count_on_a_missing_prop_fails(page):
    with pytest.raises(AssertionError, match="Expected prop 'teams' to exist"):
        page.has_count("teams", 0)


def test_missing(page):
    page.missing("stats").missing("users.0.email").missing("users.0.name.first")


def test_missing_reports_the_present_value(page):
    with pytest.raises(AssertionError, match="Expected prop 'users.0.name' to be missing, got 'Taylor'"):
        page.missing("users.0.name")


def test_equals(page):
    page.equals("filters", {"search": None}).equals("users.1.roles", [])


def test_equals_reports_both_values(page):
    with pytest.raises(AssertionError, match="Expected prop 'users.0.name' to equal 'Jess', got 'Taylor'"):
        page.equals("users.0.name", "Jess")


def test_deferred_ignores_prop_order(page):
    page.deferred("metrics", ["chart", "stats"])


def test_deferred_reports_the_group(page):
    with pytest.raises(AssertionError, match="Expected deferred group 'metrics' to be \\['stats'\\]"):
        page.deferred("metrics", ["stats"])


def test_deferred_unknown_group(page):
    with pytest.raises(AssertionError, match="Expected deferred group 'default'"):
        page.deferred("default", ["stats"])


def test_flash(page):
    page.flash("message").flash("message", "Saved <b>")


def test_flash_missing_key(page):
    with pytest.raises(AssertionError, match="Expected flash 'error' to exist"):
        page.flash("error")


def test_flash_value_mismatch(page):
    with pytest.raises(AssertionError, match="Expected flash 'message' to equal 'Done', got 'Saved <b>'"):
        page.flash("message", "Done")
