import unittest
from fastapi_startkit.inertia.inertia import Inertia, ResponseFactory, InertiaResponse


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
