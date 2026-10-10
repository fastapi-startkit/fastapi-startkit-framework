import json
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi import Request

from fastapi_startkit.inertia.constant import Header
from fastapi_startkit.inertia.inertia import Inertia, InertiaResponse
from fastapi_startkit.inertia.ssr import HttpSSRGateway, SSRGateway, ViteHotFileGateway

PAGE = {"component": "Dashboard", "url": "/", "props": {}}
RENDERED = {"head": ["<title>Home</title>"], "body": "<main>SSR</main>"}


def http_gateway(handler, **kwargs) -> HttpSSRGateway:
    return HttpSSRGateway("http://127.0.0.1:13714/", transport=httpx.MockTransport(handler), **kwargs)


class TestHttpSSRGateway(unittest.IsolatedAsyncioTestCase):
    async def test_render_posts_page_to_render_endpoint(self):
        seen = {}

        def handler(request):
            seen["url"] = str(request.url)
            seen["page"] = json.loads(request.content)
            return httpx.Response(200, json=RENDERED)

        rendered = await http_gateway(handler).render(PAGE)

        self.assertEqual(seen["url"], "http://127.0.0.1:13714/render")
        self.assertEqual(seen["page"], PAGE)
        self.assertEqual(rendered, RENDERED)

    async def test_missing_head_defaults_to_empty_list(self):
        gateway = http_gateway(lambda request: httpx.Response(200, json={"body": "<main/>"}))

        self.assertEqual(await gateway.render(PAGE), {"body": "<main/>", "head": []})

    async def test_payload_without_string_body_returns_none(self):
        gateway = http_gateway(lambda request: httpx.Response(200, json={"body": None}))

        self.assertIsNone(await gateway.render(PAGE))

    async def test_non_json_payload_returns_none(self):
        gateway = http_gateway(lambda request: httpx.Response(200, text="<html>"))

        self.assertIsNone(await gateway.render(PAGE))

    async def test_error_status_returns_none(self):
        gateway = http_gateway(lambda request: httpx.Response(500))

        self.assertIsNone(await gateway.render(PAGE))

    async def test_connection_failure_returns_none(self):
        def handler(request):
            raise httpx.ConnectError("refused", request=request)

        self.assertIsNone(await http_gateway(handler).render(PAGE))

    async def test_timeout_returns_none(self):
        def handler(request):
            raise httpx.ReadTimeout("slow", request=request)

        self.assertIsNone(await http_gateway(handler).render(PAGE))

    async def test_healthy_when_health_endpoint_succeeds(self):
        seen = []

        def handler(request):
            seen.append(request.url.path)
            return httpx.Response(200)

        self.assertTrue(await http_gateway(handler).healthy())
        self.assertEqual(seen, ["/health"])

    async def test_unhealthy_when_health_endpoint_fails(self):
        gateway = http_gateway(lambda request: httpx.Response(503))

        self.assertFalse(await gateway.healthy())

    async def test_unhealthy_when_server_is_unreachable(self):
        def handler(request):
            raise httpx.ConnectError("refused", request=request)

        self.assertFalse(await http_gateway(handler).healthy())


class TestViteHotFileGateway(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.hot_file = os.path.join(directory.name, "hot")

    def write_hot_file(self, content: str):
        with open(self.hot_file, "w") as file:
            file.write(content)

    async def test_renders_through_the_origin_in_the_hot_file(self):
        self.write_hot_file("http://localhost:5173/\n")
        seen = []

        def handler(request):
            seen.append(str(request.url))
            return httpx.Response(200, json=RENDERED)

        rendered = await ViteHotFileGateway(self.hot_file, transport=httpx.MockTransport(handler)).render(PAGE)

        self.assertEqual(seen, ["http://localhost:5173/__inertia_ssr"])
        self.assertEqual(rendered, RENDERED)

    async def test_reads_the_origin_on_every_render(self):
        self.write_hot_file("http://localhost:5173")
        seen = []

        def handler(request):
            seen.append(request.url.host + ":" + str(request.url.port))
            return httpx.Response(200, json=RENDERED)

        gateway = ViteHotFileGateway(self.hot_file, transport=httpx.MockTransport(handler))
        await gateway.render(PAGE)
        self.write_hot_file("http://localhost:5174")
        await gateway.render(PAGE)

        self.assertEqual(seen, ["localhost:5173", "localhost:5174"])

    async def test_missing_hot_file_disables_rendering(self):
        gateway = ViteHotFileGateway(self.hot_file)

        self.assertIsNone(await gateway.render(PAGE))
        self.assertFalse(await gateway.healthy())

    async def test_empty_hot_file_disables_rendering(self):
        self.write_hot_file("  \n")

        self.assertIsNone(await ViteHotFileGateway(self.hot_file).render(PAGE))

    async def test_existing_hot_file_is_healthy(self):
        self.write_hot_file("http://localhost:5173")

        self.assertTrue(await ViteHotFileGateway(self.hot_file).healthy())


class TestSSRResponse(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_request = MagicMock(spec=Request)
        self.mock_request.scope = {}
        self.mock_request.headers = {}
        self.mock_request.url = "http://localhost/dashboard"

    def gateway(self, result=RENDERED) -> MagicMock:
        gateway = MagicMock(spec=SSRGateway)
        gateway.render = AsyncMock(return_value=result)
        return gateway

    async def render_initial(self, response: InertiaResponse) -> dict:
        templates = MagicMock()
        templates.TemplateResponse.return_value = MagicMock()
        with patch("fastapi_startkit.application.app") as container:
            container.return_value.has.return_value = True
            container.return_value.make.return_value = templates
            await response.to_response(self.mock_request)
        return templates.TemplateResponse.call_args.args[2]["page"]

    async def test_initial_visit_embeds_gateway_render(self):
        gateway = self.gateway()

        page = await self.render_initial(InertiaResponse("Dashboard", {}, {}, ssr_gateway=gateway))

        gateway.render.assert_awaited_once()
        self.assertEqual(page["ssr"], RENDERED)

    async def test_failed_render_leaves_page_without_ssr(self):
        page = await self.render_initial(InertiaResponse("Dashboard", {}, {}, ssr_gateway=self.gateway(None)))

        self.assertNotIn("ssr", page)

    async def test_inertia_visits_never_call_the_gateway(self):
        self.mock_request.headers = {Header.INERTIA: "true"}
        gateway = self.gateway()

        await InertiaResponse("Dashboard", {}, {}, ssr_gateway=gateway).to_response(self.mock_request)

        gateway.render.assert_not_awaited()

    async def test_excepted_paths_skip_the_gateway(self):
        self.mock_request.url = "http://localhost/admin/users"
        gateway = self.gateway()
        response = InertiaResponse("Dashboard", {}, {}, ssr_gateway=gateway, ssr_except_paths=("/admin/*",))

        page = await self.render_initial(response)

        gateway.render.assert_not_awaited()
        self.assertNotIn("ssr", page)

    async def test_unmatched_paths_still_use_the_gateway(self):
        gateway = self.gateway()
        response = InertiaResponse("Dashboard", {}, {}, ssr_gateway=gateway, ssr_except_paths=("/admin/*",))

        await self.render_initial(response)

        gateway.render.assert_awaited_once()


class TestSSRFacade(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        Inertia._instance = None

    async def test_ssr_hot_uses_vite_hot_file_gateway(self):
        Inertia.ssr_hot("does/not/exist/hot")

        self.assertIsInstance(Inertia.instance().ssr_gateway, ViteHotFileGateway)
        self.assertFalse(await Inertia.ssr_healthy())

    async def test_disabled_ssr_keeps_gateway_but_not_on_responses(self):
        Inertia.ssr("http://localhost:13714", enabled=False)

        self.assertIsNotNone(Inertia.instance().ssr_gateway)
        self.assertIsNone(Inertia.instance().render("Dashboard", {}).ssr_gateway)

    async def test_ssr_healthy_is_false_without_gateway(self):
        self.assertFalse(await Inertia.ssr_healthy())
