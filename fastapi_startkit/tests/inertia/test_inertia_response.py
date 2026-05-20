import json
import unittest
from unittest.mock import MagicMock
from fastapi import Request
from fastapi_startkit.inertia.inertia import InertiaResponse, OptionalProp
from fastapi_startkit.inertia.constant import Header


class TestInertiaResponse(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_request = MagicMock(spec=Request)
        self.mock_request.headers = {}
        self.mock_request.url = "http://localhost/test"

    async def test_inertia_response_to_json_on_inertia_request(self):
        self.mock_request.headers = {Header.INERTIA: "true"}

        response = InertiaResponse(
            component="User/Index", shared_props={"app": "Test"}, props={"users": []}, version="v1"
        )

        actual_response = await response.to_response(self.mock_request)

        self.assertEqual(actual_response.status_code, 200)
        self.assertEqual(actual_response.headers[Header.INERTIA], "true")

        content = json.loads(actual_response.body)
        self.assertEqual(content["component"], "User/Index")
        self.assertEqual(content["props"], {"app": "Test", "users": []})
        self.assertEqual(content["version"], "v1")
        self.assertEqual(content["url"], "/test")

    async def test_inertia_response_partial_reload(self):
        self.mock_request.headers = {
            Header.INERTIA: "true",
            Header.INERTIA_PARTIAL_COMPONENT: "User/Index",
            "X-Inertia-Partial-Data": "users",
        }

        response = InertiaResponse(
            component="User/Index",
            shared_props={"app": "Test"},
            props={"users": ["user1"], "stats": {"likes": 10}},
        )

        actual_response = await response.to_response(self.mock_request)
        data = json.loads(actual_response.body)

        # Should only include "users", exclude "app" and "stats"
        self.assertIn("users", data["props"])
        self.assertNotIn("app", data["props"])
        self.assertNotIn("stats", data["props"])

    async def test_inertia_response_optional_props(self):
        # 1. Normal request - optional prop should be excluded
        self.mock_request.headers = {Header.INERTIA: "true"}

        lazy_called = False

        def get_lazy():
            nonlocal lazy_called
            lazy_called = True
            return "lazy data"

        response = InertiaResponse(
            component="User/Index",
            shared_props={},
            props={"regular": "data", "lazy": OptionalProp(get_lazy)},
        )

        actual_response = await response.to_response(self.mock_request)
        data = json.loads(actual_response.body)
        self.assertEqual(data["props"], {"regular": "data"})
        self.assertFalse(lazy_called)

        # 2. Partial reload requesting lazy prop - should be included
        self.mock_request.headers = {
            Header.INERTIA: "true",
            Header.INERTIA_PARTIAL_COMPONENT: "User/Index",
            "X-Inertia-Partial-Data": "lazy",
        }

        actual_response = await response.to_response(self.mock_request)
        data = json.loads(actual_response.body)
        self.assertEqual(data["props"], {"lazy": "lazy data"})
        self.assertTrue(lazy_called)

    async def test_inertia_response_resolves_callable_props(self):
        self.mock_request.headers = {Header.INERTIA: "true"}

        async def get_async_data():
            return "async result"

        response = InertiaResponse(
            component="Test",
            shared_props={"sync": lambda: "sync result"},
            props={"async": get_async_data},
        )

        actual_response = await response.to_response(self.mock_request)
        data = json.loads(actual_response.body)
        self.assertEqual(data["props"]["sync"], "sync result")
        self.assertEqual(data["props"]["async"], "async result")

    async def test_inertia_response_initial_render_raises_if_no_templates(self):
        # Standard request (no X-Inertia header)
        self.mock_request.headers = {}

        response = InertiaResponse(component="Test", shared_props={}, props={})

        # This should fail because we haven't mocked the application container
        with self.assertRaisesRegex(RuntimeError, "Inertia requires 'templates' to be bound"):
            await response.to_response(self.mock_request)
