import json
from typing import Optional
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi import Request

from fastapi_startkit.inertia.constant import Header
from fastapi_startkit.inertia.inertia import InertiaResponse
from fastapi_startkit.inertia.ssr import HttpSSRGateway, SSRGateway, ViteHotFileGateway, is_excepted

RENDERED = {"head": ["<title>Home</title>"], "body": "<main>SSR</main>"}
PAGE = {"component": "Dashboard", "url": "/", "props": {}}


def transport(handler, calls: Optional[list] = None) -> httpx.MockTransport:
    def record(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request)
        return handler(request)

    return httpx.MockTransport(record)


def ok(payload, calls: Optional[list] = None) -> httpx.MockTransport:
    return transport(lambda request: httpx.Response(200, json=payload), calls)


def raising(error: Exception) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        raise error

    return transport(handler)


class TestHttpSSRGateway:
    async def test_render_posts_page_as_json_to_render_endpoint(self):
        calls: list = []
        gateway = HttpSSRGateway("http://127.0.0.1:13714/", transport=ok(RENDERED, calls))

        assert await gateway.render(PAGE) == RENDERED
        assert calls[0].method == "POST"
        assert str(calls[0].url) == "http://127.0.0.1:13714/render"
        assert json.loads(calls[0].content) == PAGE

    async def test_render_defaults_head_to_empty_list(self):
        gateway = HttpSSRGateway("http://ssr", transport=ok({"body": "<main/>"}))

        assert await gateway.render(PAGE) == {"body": "<main/>", "head": []}

    async def test_render_uses_custom_render_path(self):
        calls: list = []
        gateway = HttpSSRGateway("http://ssr", render_path="/ssr", transport=ok(RENDERED, calls))

        await gateway.render(PAGE)

        assert calls[0].url.path == "/ssr"

    @pytest.mark.parametrize("payload", [{"body": None}, {"head": []}, ["<main/>"], "<main/>"])
    async def test_render_rejects_invalid_payload(self, payload):
        assert await HttpSSRGateway("http://ssr", transport=ok(payload)).render(PAGE) is None

    async def test_render_rejects_non_json_response(self):
        gateway = HttpSSRGateway("http://ssr", transport=transport(lambda r: httpx.Response(200, text="<html>")))

        assert await gateway.render(PAGE) is None

    async def test_render_returns_none_on_server_error(self):
        gateway = HttpSSRGateway("http://ssr", transport=transport(lambda r: httpx.Response(500, json=RENDERED)))

        assert await gateway.render(PAGE) is None

    @pytest.mark.parametrize("error", [httpx.ConnectError("refused"), httpx.ReadTimeout("slow")])
    async def test_render_returns_none_on_transport_failure(self, error):
        assert await HttpSSRGateway("http://ssr", transport=raising(error)).render(PAGE) is None

    async def test_render_passes_timeout_to_client(self):
        calls: list = []
        gateway = HttpSSRGateway("http://ssr", timeout=2.5, transport=ok(RENDERED, calls))

        await gateway.render(PAGE)

        assert calls[0].extensions["timeout"]["read"] == 2.5

    async def test_healthy_on_success_from_health_endpoint(self):
        calls: list = []
        gateway = HttpSSRGateway("http://ssr", transport=transport(lambda r: httpx.Response(200), calls))

        assert await gateway.healthy() is True
        assert calls[0].method == "GET"
        assert str(calls[0].url) == "http://ssr/health"

    async def test_unhealthy_on_error_status(self):
        gateway = HttpSSRGateway("http://ssr", transport=transport(lambda r: httpx.Response(503)))

        assert await gateway.healthy() is False

    async def test_unhealthy_when_unreachable(self):
        gateway = HttpSSRGateway("http://ssr", transport=raising(httpx.ConnectError("refused")))

        assert await gateway.healthy() is False

    def test_satisfies_gateway_protocol(self):
        assert isinstance(HttpSSRGateway("http://ssr"), SSRGateway)


class TestViteHotFileGateway:
    async def test_render_posts_to_inertia_ssr_endpoint_on_hot_origin(self, tmp_path):
        hot = tmp_path / "hot"
        hot.write_text("http://localhost:5173/\n")
        calls: list = []
        gateway = ViteHotFileGateway(str(hot), transport=ok(RENDERED, calls))

        assert await gateway.render(PAGE) == RENDERED
        assert str(calls[0].url) == "http://localhost:5173/__inertia_ssr"

    async def test_follows_origin_changes_between_calls(self, tmp_path):
        hot = tmp_path / "hot"
        hot.write_text("http://localhost:5173")
        calls: list = []
        gateway = ViteHotFileGateway(str(hot), transport=ok(RENDERED, calls))

        await gateway.render(PAGE)
        hot.write_text("http://localhost:5174")
        await gateway.render(PAGE)

        assert [call.url.port for call in calls] == [5173, 5174]

    @pytest.mark.parametrize("content", [None, "", "  \n"])
    async def test_without_hot_origin_renders_nothing_and_is_unhealthy(self, tmp_path, content):
        hot = tmp_path / "hot"
        if content is not None:
            hot.write_text(content)
        calls: list = []
        gateway = ViteHotFileGateway(str(hot), transport=ok(RENDERED, calls))

        assert await gateway.render(PAGE) is None
        assert await gateway.healthy() is False
        assert calls == []

    async def test_healthy_checks_dev_server(self, tmp_path):
        hot = tmp_path / "hot"
        hot.write_text("http://localhost:5173")
        calls: list = []
        gateway = ViteHotFileGateway(str(hot), transport=transport(lambda r: httpx.Response(200), calls))

        assert await gateway.healthy() is True
        assert str(calls[0].url) == "http://localhost:5173/health"

    def test_satisfies_gateway_protocol(self, tmp_path):
        assert isinstance(ViteHotFileGateway(str(tmp_path / "hot")), SSRGateway)


@pytest.mark.parametrize(
    ("path", "patterns", "expected"),
    [
        ("/admin", ["/admin"], True),
        ("/admin/users/1", ["/admin/*"], True),
        ("/admins", ["/admin"], False),
        ("/", [], False),
        ("/reports/2026/export", ["/login", "/reports/*/export"], True),
    ],
)
def test_is_excepted(path, patterns, expected):
    assert is_excepted(path, patterns) is expected


class FakeGateway:
    def __init__(self, result: Optional[dict] = RENDERED, error: Optional[Exception] = None):
        self.result = result
        self.error = error
        self.pages: list = []

    async def render(self, page: dict) -> Optional[dict]:
        self.pages.append(dict(page))
        if self.error:
            raise self.error
        return self.result

    async def healthy(self) -> bool:
        return True


def make_request(url: str = "http://localhost/dashboard", headers: Optional[dict] = None) -> MagicMock:
    request = MagicMock(spec=Request)
    request.headers = headers or {}
    request.url = url
    return request


async def render_page(response: InertiaResponse, request: MagicMock) -> dict:
    templates = MagicMock()
    with patch("fastapi_startkit.application.app") as container:
        container.return_value.has.return_value = True
        container.return_value.make.return_value = templates
        await response.to_response(request)
    return templates.TemplateResponse.call_args.args[2]["page"]


class TestResponseSSR:
    async def test_initial_visit_includes_rendered_page(self):
        gateway = FakeGateway()
        page = await render_page(InertiaResponse("Dashboard", {}, {"count": 1}, ssr_gateway=gateway), make_request())

        assert page["ssr"] == RENDERED
        assert gateway.pages[0]["component"] == "Dashboard"
        assert gateway.pages[0]["props"] == {"count": 1}
        assert "ssr" not in gateway.pages[0]

    async def test_without_gateway_renders_on_client(self):
        page = await render_page(InertiaResponse("Dashboard", {}, {}), make_request())

        assert "ssr" not in page

    async def test_gateway_returning_none_falls_back_to_client(self):
        response = InertiaResponse("Dashboard", {}, {}, ssr_gateway=FakeGateway(result=None))

        assert "ssr" not in await render_page(response, make_request())

    async def test_raising_gateway_falls_back_to_client(self):
        gateway = FakeGateway(error=RuntimeError("boom"))
        page = await render_page(InertiaResponse("Dashboard", {}, {}, ssr_gateway=gateway), make_request())

        assert "ssr" not in page
        assert gateway.pages

    async def test_unreachable_http_gateway_falls_back_to_client(self):
        gateway = HttpSSRGateway("http://ssr", transport=raising(httpx.ConnectError("refused")))
        page = await render_page(InertiaResponse("Dashboard", {}, {}, ssr_gateway=gateway), make_request())

        assert "ssr" not in page

    async def test_excepted_path_skips_gateway(self):
        gateway = FakeGateway()
        response = InertiaResponse("Admin", {}, {}, ssr_gateway=gateway, ssr_except_paths=("/admin/*",))

        page = await render_page(response, make_request("http://localhost/admin/users?page=2"))

        assert "ssr" not in page
        assert gateway.pages == []

    async def test_inertia_request_never_contacts_gateway(self):
        gateway = FakeGateway()
        response = InertiaResponse("Dashboard", {}, {}, ssr_gateway=gateway)

        actual = await response.to_response(make_request(headers={Header.INERTIA: "true"}))

        assert "ssr" not in json.loads(actual.body)
        assert gateway.pages == []
