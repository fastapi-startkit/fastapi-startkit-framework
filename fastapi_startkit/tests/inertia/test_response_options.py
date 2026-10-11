import json
from types import SimpleNamespace
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from fastapi_startkit.inertia import Inertia, InertiaMiddleware, InertiaProvider
from fastapi_startkit.inertia.constant import Header
from fastapi_startkit.inertia.encoding import encode_big_integers
from fastapi_startkit.inertia.testing import FakeSessionMiddleware

INERTIA = {Header.INERTIA: "true"}
MAX_SAFE = 2**53 - 1


class FakeTemplates:
    def TemplateResponse(self, request, name, context):
        return HTMLResponse(json.dumps({key: value for key, value in context.items()}))


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


def client_for(handler, session: dict | None = None) -> TestClient:
    app = FastAPI()
    app.add_middleware(InertiaMiddleware)
    if session is not None:
        app.add_middleware(FakeSessionMiddleware, session=session)
    app.get("/page")(handler)
    return TestClient(app)


def html_context(response) -> dict:
    return json.loads(response.text)


async def page_with_view_data():
    return Inertia.render("Page", {"name": "Ada"}).with_view_data("title", "Home").with_view_data({"lang": "en"})


def test_view_data_is_available_in_the_root_template():
    context = html_context(client_for(page_with_view_data).get("/page"))

    assert context["title"] == "Home"
    assert context["lang"] == "en"
    assert "title" not in context["page"]["props"]


def test_view_data_is_not_sent_on_inertia_visits():
    page = client_for(page_with_view_data).get("/page", headers=INERTIA).json()

    assert "title" not in page
    assert "title" not in page["props"]


def test_view_data_cannot_replace_the_page():
    async def handler():
        return Inertia.render("Page").with_view_data("page", "nope")

    assert html_context(client_for(handler).get("/page"))["page"]["component"] == "Page"


def make_helper():
    templates = SimpleNamespace(env=SimpleNamespace(globals={}))
    app = MagicMock()
    app.has.return_value = True
    app.make.side_effect = lambda key: {"templates": templates, "inertia": Inertia}[key]
    InertiaProvider(app).boot()
    return templates.env.globals["inertia"]


def test_inertia_helper_uses_default_root_id():
    html = str(make_helper()({"component": "Page", "props": {}}))

    assert 'data-page="app"' in html
    assert '<div id="app"></div>' in html


def test_inertia_helper_uses_configured_root_id():
    helper = make_helper()
    Inertia.root_id("admin")

    html = str(helper({"component": "Page", "props": {}, "ssr": {"body": "<main></main>"}}))

    assert 'data-page="admin"' in html
    assert '<div id="admin"><main></main></div>' in html
    assert 'id="app"' not in html


async def plain_page():
    return Inertia.render("Page")


def test_default_url_keeps_path_and_query():
    response = client_for(plain_page).get("/page?search=ada&page=2", headers=INERTIA)

    assert response.json()["url"] == "/page?search=ada&page=2"


def test_url_resolver_output_becomes_page_url():
    Inertia.resolve_url_using(lambda request: f"/prefix{request.url.path}?via=proxy")

    client = client_for(plain_page)

    assert client.get("/page", headers=INERTIA).json()["url"] == "/prefix/page?via=proxy"
    assert html_context(client.get("/page"))["page"]["url"] == "/prefix/page?via=proxy"


def test_url_resolver_can_be_reset():
    Inertia.resolve_url_using(lambda request: "/elsewhere")
    Inertia.resolve_url_using(None)

    assert client_for(plain_page).get("/page", headers=INERTIA).json()["url"] == "/page"


def test_encode_big_integers_boundaries_and_nesting():
    value = {
        "safe": MAX_SAFE,
        "unsafe": MAX_SAFE + 1,
        "negative": -(MAX_SAFE + 1),
        "safe_negative": -MAX_SAFE,
        "flag": True,
        "nested": [{"id": 2**64}, (1, 2**60)],
        "text": "x",
        "ratio": 1.5,
    }

    assert encode_big_integers(value) == {
        "safe": MAX_SAFE,
        "unsafe": {"$bigint": str(MAX_SAFE + 1)},
        "negative": {"$bigint": str(-(MAX_SAFE + 1))},
        "safe_negative": -MAX_SAFE,
        "flag": True,
        "nested": [{"id": {"$bigint": str(2**64)}}, [1, {"$bigint": str(2**60)}]],
        "text": "x",
        "ratio": 1.5,
    }


async def big_page():
    return Inertia.render("Page", {"id": 2**60, "count": 3})


def test_big_integers_are_not_encoded_by_default():
    page = client_for(big_page).get("/page", headers=INERTIA).json()

    assert page["props"]["id"] == 2**60
    assert "preserveBigIntegers" not in page


def test_big_integers_are_encoded_when_enabled_globally():
    Inertia.preserve_big_integers()
    client = client_for(big_page)

    for page in (client.get("/page", headers=INERTIA).json(), html_context(client.get("/page"))["page"]):
        assert page["props"]["id"] == {"$bigint": str(2**60)}
        assert page["props"]["count"] == 3
        assert page["preserveBigIntegers"] is True


def test_big_integers_are_encoded_in_flash_data():
    Inertia.preserve_big_integers()

    async def handler():
        return Inertia.render("Page").flash("order", 2**60)

    page = client_for(handler).get("/page", headers=INERTIA).json()

    assert page["flash"] == {"order": {"$bigint": str(2**60)}}


def test_per_response_switch_enables_encoding():
    async def handler():
        return Inertia.render("Page", {"id": 2**60}).preserve_big_integers()

    page = client_for(handler).get("/page", headers=INERTIA).json()

    assert page["props"]["id"] == {"$bigint": str(2**60)}
    assert page["preserveBigIntegers"] is True


def test_per_response_switch_overrides_global_setting():
    Inertia.preserve_big_integers()

    async def handler():
        return Inertia.render("Page", {"id": 2**60}).preserve_big_integers(False)

    page = client_for(handler).get("/page", headers=INERTIA).json()

    assert page["props"]["id"] == 2**60
    assert "preserveBigIntegers" not in page


async def page_with_headers():
    return (
        Inertia.render("Page")
        .with_header("Cache-Control", "no-store")
        .with_headers({"X-Trace": "abc", "Link": "</app.css>; rel=preload"})
    )


@pytest.mark.parametrize("headers", [{}, INERTIA])
def test_headers_appear_on_html_and_json_responses(headers):
    response = client_for(page_with_headers).get("/page", headers=headers)

    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-trace"] == "abc"
    assert response.headers["link"] == "</app.css>; rel=preload"


def test_with_header_keeps_inertia_header_on_json_responses():
    response = client_for(page_with_headers).get("/page", headers=INERTIA)

    assert response.headers[Header.INERTIA] == "true"


class FakeGateway:
    def __init__(self):
        self.pages: list[dict] = []

    async def render(self, page: dict) -> Optional[dict]:
        self.pages.append(page)
        return {"head": [], "body": "<main></main>"}

    async def healthy(self) -> bool:
        return True


def test_without_ssr_skips_the_gateway():
    gateway = FakeGateway()
    Inertia.ssr_gateway(gateway)

    async def handler():
        return Inertia.render("Page").without_ssr()

    page = html_context(client_for(handler).get("/page"))["page"]

    assert gateway.pages == []
    assert "ssr" not in page


def test_ssr_still_runs_without_the_override():
    gateway = FakeGateway()
    Inertia.ssr_gateway(gateway)

    page = html_context(client_for(plain_page).get("/page"))["page"]

    assert len(gateway.pages) == 1
    assert page["ssr"] == {"head": [], "body": "<main></main>"}
