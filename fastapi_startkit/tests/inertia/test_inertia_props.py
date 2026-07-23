"""Tests for InertiaProps evaluation (task #13).

Covers: OptionalProp (lazy) vs eager props, shared props merging,
full response structure, and InertiaResponse.with_() builder.
"""

import json
import unittest
from unittest.mock import MagicMock

from fastapi import Request

from fastapi_startkit.inertia.constant import Header
from fastapi_startkit.inertia.inertia import Inertia, InertiaResponse, OptionalProp, ResponseFactory


class TestOptionalProp(unittest.TestCase):
    def test_optional_prop_calls_callback(self):
        called = []

        def cb():
            called.append(True)
            return "value"

        prop = OptionalProp(cb)
        result = prop()
        assert result == "value"
        assert called

    def test_optional_prop_is_callable(self):
        prop = OptionalProp(lambda: 42)
        assert callable(prop)

    def test_optional_prop_wraps_any_callable(self):
        prop = OptionalProp(lambda: {"key": "val"})
        assert prop() == {"key": "val"}


class TestEagerProps(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.request = MagicMock(spec=Request)
        self.request.headers = {Header.INERTIA: "true"}
        self.request.url = "http://localhost/page"

    async def test_eager_props_always_included(self):
        response = InertiaResponse(
            component="Page",
            shared_props={},
            props={"eager": "value"},
        )
        actual = await response.to_response(self.request)
        data = json.loads(actual.body)
        assert data["props"]["eager"] == "value"

    async def test_lazy_prop_excluded_from_full_load(self):
        evaluated = []

        def expensive():
            evaluated.append(True)
            return "expensive"

        response = InertiaResponse(
            component="Page",
            shared_props={},
            props={"lazy": OptionalProp(expensive)},
        )
        actual = await response.to_response(self.request)
        data = json.loads(actual.body)
        assert "lazy" not in data["props"]
        assert not evaluated

    async def test_lazy_prop_included_in_partial_reload(self):
        evaluated = []

        def expensive():
            evaluated.append(True)
            return "computed"

        self.request.headers = {
            Header.INERTIA: "true",
            Header.INERTIA_PARTIAL_COMPONENT: "Page",
            "X-Inertia-Partial-Data": "lazy",
        }
        response = InertiaResponse(
            component="Page",
            shared_props={},
            props={"lazy": OptionalProp(expensive)},
        )
        actual = await response.to_response(self.request)
        data = json.loads(actual.body)
        assert data["props"]["lazy"] == "computed"
        assert evaluated


class TestSharedPropsmerging(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.request = MagicMock(spec=Request)
        self.request.headers = {Header.INERTIA: "true"}
        self.request.url = "http://localhost/"

    async def test_shared_props_merged_into_response(self):
        response = InertiaResponse(
            component="Dashboard",
            shared_props={"auth": {"user": "alice"}},
            props={"count": 5},
        )
        actual = await response.to_response(self.request)
        data = json.loads(actual.body)
        assert data["props"]["auth"] == {"user": "alice"}
        assert data["props"]["count"] == 5

    async def test_page_props_override_shared_on_conflict(self):
        response = InertiaResponse(
            component="Dashboard",
            shared_props={"key": "shared"},
            props={"key": "page"},
        )
        actual = await response.to_response(self.request)
        data = json.loads(actual.body)
        # page props win because all_props = {**shared, **props}
        assert data["props"]["key"] == "page"

    async def test_full_response_structure(self):
        response = InertiaResponse(
            component="Users/Index",
            shared_props={"app": "Startkit"},
            props={"users": []},
            version="v1.0",
        )
        actual = await response.to_response(self.request)
        data = json.loads(actual.body)
        assert "component" in data
        assert "props" in data
        assert "url" in data
        assert "version" in data
        assert data["component"] == "Users/Index"
        assert data["version"] == "v1.0"


class TestInertiaResponseBuilder(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.request = MagicMock(spec=Request)
        self.request.headers = {Header.INERTIA: "true"}
        self.request.url = "http://localhost/users"

    async def test_with_adds_props(self):
        response = InertiaResponse(
            component="Users",
            shared_props={},
            props={"initial": True},
        )
        response.with_("extra", "data")

        actual = await response.to_response(self.request)
        data = json.loads(actual.body)
        assert data["props"]["extra"] == "data"
        assert data["props"]["initial"] is True

    async def test_with_dict_merges_props(self):
        response = InertiaResponse(component="Users", shared_props={}, props={})
        response.with_({"a": 1, "b": 2})

        actual = await response.to_response(self.request)
        data = json.loads(actual.body)
        assert data["props"]["a"] == 1
        assert data["props"]["b"] == 2

    async def test_with_root_view_changes_view(self):
        response = InertiaResponse(component="Page", shared_props={}, props={})
        result = response.with_root_view("custom.html")
        assert result.root_view == "custom.html"


class TestResponseFactory(unittest.TestCase):
    def setUp(self):
        Inertia._instance = None

    def test_factory_renders_inertia_response(self):
        factory = ResponseFactory()
        factory.share("global", True)
        resp = factory.render("Home", {"title": "Hello"})
        assert isinstance(resp, InertiaResponse)
        assert resp.component == "Home"
        assert resp.props == {"title": "Hello"}
        assert resp.shared_props == {"global": True}

    def test_callable_version_resolved(self):
        factory = ResponseFactory()
        factory.set_version(lambda: "3.0")
        assert factory.get_version() == "3.0"

    def test_none_version_returns_none(self):
        factory = ResponseFactory()
        assert factory.get_version() is None
