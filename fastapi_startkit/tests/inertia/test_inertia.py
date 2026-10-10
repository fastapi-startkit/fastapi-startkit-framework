import unittest
from unittest.mock import MagicMock

from fastapi_startkit.inertia.inertia import Inertia, ResponseFactory, InertiaResponse
from fastapi_startkit.inertia.ssr import HttpSSRGateway


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
        gateway = MagicMock()
        factory.set_ssr(gateway, except_paths=["/admin/*"])

        response = factory.render("Dashboard", {})

        self.assertIs(factory.ssr_gateway, gateway)
        self.assertIs(response.ssr_gateway, gateway)
        self.assertEqual(response.ssr_except_paths, ("/admin/*",))

    def test_factory_disabled_ssr_is_not_forwarded_to_response(self):
        factory = ResponseFactory()
        factory.set_ssr(MagicMock(), enabled=False)

        self.assertIsNone(factory.render("Dashboard", {}).ssr_gateway)

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
        self.assertIsInstance(gateway, HttpSSRGateway)
        self.assertEqual(gateway.base_url, "http://localhost:13714")
        self.assertEqual(gateway.timeout, 3.0)

    def test_facade_ssr_none_disables_gateway(self):
        Inertia.ssr(None)

        self.assertIsNone(Inertia.instance().ssr_gateway)
