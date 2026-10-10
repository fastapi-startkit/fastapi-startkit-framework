import unittest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from fastapi_startkit.inertia.bigint import encode_big_integers
from fastapi_startkit.inertia.constant import Header
from fastapi_startkit.inertia.inertia import Inertia
from fastapi_startkit.inertia.middleware import InertiaMiddleware

MAX_SAFE = 2**53 - 1


def build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(InertiaMiddleware)

    @app.get("/page")
    def page():
        return Inertia.render("Users/Index", {"id": 2**53, "count": 3, "rows": [{"total": -(2**60)}]})

    @app.get("/per-response")
    def per_response():
        return Inertia.render("Users/Index", {"id": 2**53}).preserve_big_integers()

    @app.get("/nested-url")
    def nested_url():
        return Inertia.render("Users/Index", {})

    return app


class TestEncodeBigIntegers(unittest.TestCase):
    def test_safe_integers_are_unchanged(self):
        self.assertEqual(encode_big_integers([MAX_SAFE, -MAX_SAFE, 0]), [MAX_SAFE, -MAX_SAFE, 0])

    def test_unsafe_integers_are_wrapped_as_strings(self):
        self.assertEqual(encode_big_integers(MAX_SAFE + 1), {"$bigint": str(MAX_SAFE + 1)})
        self.assertEqual(encode_big_integers(-(MAX_SAFE + 1)), {"$bigint": str(-(MAX_SAFE + 1))})

    def test_nested_containers_are_walked(self):
        encoded = encode_big_integers({"a": [{"b": 2**60}], "c": "text"})

        self.assertEqual(encoded, {"a": [{"b": {"$bigint": str(2**60)}}], "c": "text"})


class TestPageOptions(unittest.TestCase):
    def setUp(self):
        Inertia._instance = None
        container_patch = patch("fastapi_startkit.application.app")
        mock_app_getter = container_patch.start()
        self.addCleanup(container_patch.stop)
        mock_app_getter.return_value = MagicMock(has=MagicMock(return_value=False))

    def get_page(self, client: TestClient, path: str = "/page") -> dict:
        return client.get(path, headers={Header.INERTIA: "true"}).json()

    def test_big_integers_are_not_encoded_by_default(self):
        page = self.get_page(TestClient(build_app()))

        self.assertIs(page["preserveBigIntegers"], False)
        self.assertEqual(page["props"]["id"], 2**53)

    def test_global_switch_encodes_big_integers(self):
        Inertia.preserve_big_integers(True)
        page = self.get_page(TestClient(build_app()))

        self.assertIs(page["preserveBigIntegers"], True)
        self.assertEqual(page["props"]["id"], {"$bigint": str(2**53)})
        self.assertEqual(page["props"]["count"], 3)
        self.assertEqual(page["props"]["rows"], [{"total": {"$bigint": str(-(2**60))}}])

    def test_per_response_switch_overrides_global_default(self):
        client = TestClient(build_app())

        page = self.get_page(client, "/per-response")

        self.assertIs(page["preserveBigIntegers"], True)
        self.assertEqual(page["props"]["id"], {"$bigint": str(2**53)})
        self.assertIs(self.get_page(client)["preserveBigIntegers"], False)

    def test_url_resolver_receives_request_and_sets_page_url(self):
        Inertia.url_resolver(lambda request: "/prefix" + request.url.path)

        page = self.get_page(TestClient(build_app()), "/nested-url")

        self.assertEqual(page["url"], "/prefix/nested-url")

    def test_url_defaults_to_path_and_query(self):
        page = self.get_page(TestClient(build_app()), "/nested-url?page=2")

        self.assertEqual(page["url"], "/nested-url?page=2")
