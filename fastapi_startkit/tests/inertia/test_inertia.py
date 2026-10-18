import unittest

import httpx

from fastapi_startkit.inertia.inertia import Inertia, ResponseFactory, InertiaResponse
from fastapi_startkit.inertia.ssr import HttpSSRGateway, ViteHotFileGateway


class TestInertia(unittest.TestCase):
    def setUp(self):
        # Reset the singleton instance before each test
        Inertia._instance = None

    def test_factory_share_single_key(self):
        factory = ResponseFactory()
        factory.share("app_name", "FastAPI Startkit")
        self.assertEqual(factory.shared_props["app_name"], "FastAPI Startkit")

    def test_factory_share_dict(self):
        factory = ResponseFactory()
        factory.share({"user": "John", "role": "admin"})
        self.assertEqual(factory.shared_props["user"], "John")
        self.assertEqual(factory.shared_props["role"], "admin")

    def test_factory_set_version(self):
        factory = ResponseFactory()
        factory.set_version("1.0.0")
        self.assertEqual(factory.get_version(), "1.0.0")

    def test_factory_set_version_callable(self):
        factory = ResponseFactory()
        factory.set_version(lambda: "2.0.0")
        self.assertEqual(factory.get_version(), "2.0.0")

    def test_factory_render_returns_response(self):
        factory = ResponseFactory()
        factory.share("auth", {"user": None})
        response = factory.render("Dashboard", {"count": 10})

        self.assertIsInstance(response, InertiaResponse)
        self.assertEqual(response.component, "Dashboard")
        self.assertEqual(response.props, {"count": 10})
        self.assertEqual(response.shared_props, {"auth": {"user": None}})

    def test_factory_ssr_configuration_is_forwarded_to_response(self):
        factory = ResponseFactory()
        factory.set_ssr("http://localhost:13714/", timeout=2.5, except_paths=["/admin/*"])

        response = factory.render("Dashboard", {})

        gateway = response.ssr_gateway
        assert isinstance(gateway, HttpSSRGateway)
        self.assertEqual(gateway.base_url, "http://localhost:13714")
        self.assertEqual(gateway.timeout, 2.5)
        self.assertEqual(response.ssr_except_paths, ("/admin/*",))

    def test_factory_without_ssr_passes_no_gateway(self):
        self.assertIsNone(ResponseFactory().render("Dashboard", {}).ssr_gateway)

    def test_factory_disabled_ssr_passes_no_gateway(self):
        factory = ResponseFactory()
        factory.set_ssr("http://localhost:13714", enabled=False)

        self.assertIsNone(factory.render("Dashboard", {}).ssr_gateway)

    def test_factory_ssr_url_none_disables(self):
        factory = ResponseFactory()
        factory.set_ssr("http://localhost:13714")
        factory.set_ssr(None)

        self.assertIsNone(factory.ssr_gateway)

    def test_facade_singleton(self):
        instance1 = Inertia.instance()
        instance2 = Inertia.instance()
        self.assertIs(instance1, instance2)

    def test_facade_proxies_to_instance(self):
        Inertia.share("foo", "bar")
        self.assertEqual(Inertia.instance().shared_props["foo"], "bar")

        Inertia.version("v1")
        self.assertEqual(Inertia.get_version(), "v1")

        Inertia.set_root_view("app.html")
        self.assertEqual(Inertia.instance().root_view, "app.html")

    def test_facade_ssr_configures_instance(self):
        Inertia.ssr("http://localhost:13714/", timeout=3.0)

        gateway = Inertia.instance().ssr_gateway
        assert isinstance(gateway, HttpSSRGateway)
        self.assertEqual(gateway.base_url, "http://localhost:13714")
        self.assertEqual(gateway.timeout, 3.0)
        self.assertTrue(Inertia.instance().ssr_enabled)

    def test_facade_ssr_hot_configures_vite_gateway(self):
        Inertia.ssr_hot("public/hot", timeout=2.0, except_paths=["/login"])

        gateway = Inertia.instance().ssr_gateway
        assert isinstance(gateway, ViteHotFileGateway)
        self.assertEqual(gateway.hot_file, "public/hot")
        self.assertEqual(gateway.timeout, 2.0)
        self.assertEqual(Inertia.instance().ssr_except_paths, ("/login",))

    def test_facade_ssr_gateway_accepts_custom_gateway(self):
        gateway = HttpSSRGateway("http://custom")
        Inertia.ssr_gateway(gateway, enabled=False)

        self.assertIs(Inertia.instance().ssr_gateway, gateway)
        self.assertFalse(Inertia.instance().ssr_enabled)


def healthy_gateway() -> HttpSSRGateway:
    return HttpSSRGateway("http://ssr", transport=httpx.MockTransport(lambda request: httpx.Response(200)))


class TestInertiaSSRHealth(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        Inertia._instance = None

    async def test_unhealthy_without_gateway(self):
        self.assertFalse(await Inertia.ssr_healthy())

    async def test_unhealthy_when_disabled(self):
        Inertia.ssr_gateway(healthy_gateway(), enabled=False)

        self.assertFalse(await Inertia.ssr_healthy())

    async def test_delegates_to_gateway(self):
        Inertia.ssr_gateway(healthy_gateway())

        self.assertTrue(await Inertia.ssr_healthy())
