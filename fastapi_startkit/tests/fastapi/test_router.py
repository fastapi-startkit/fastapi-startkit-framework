"""Tests for the FastAPI routing layer (task #9)."""

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from fastapi_startkit.fastapi.routers.router import Router


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_app(router: Router) -> TestClient:
    app = FastAPI()
    app.include_router(router.router)
    return TestClient(app)


def endpoint():
    return {"ok": True}


# ---------------------------------------------------------------------------
# HTTP methods
# ---------------------------------------------------------------------------


class TestHttpMethods:
    def test_get_route(self):
        r = Router()
        r.get("/items", endpoint)
        client = make_app(r)
        assert client.get("/items").status_code == 200

    def test_post_route(self):
        r = Router()
        r.post("/items", endpoint)
        client = make_app(r)
        assert client.post("/items").status_code == 200

    def test_put_route(self):
        r = Router()
        r.put("/items/1", endpoint)
        client = make_app(r)
        assert client.put("/items/1").status_code == 200

    def test_patch_route(self):
        r = Router()
        r.patch("/items/1", endpoint)
        client = make_app(r)
        assert client.patch("/items/1").status_code == 200

    def test_delete_route(self):
        r = Router()
        r.delete("/items/1", endpoint)
        client = make_app(r)
        assert client.delete("/items/1").status_code == 200

    def test_head_route(self):
        r = Router()
        r.head("/items", endpoint)
        client = make_app(r)
        assert client.head("/items").status_code == 200

    def test_options_route(self):
        r = Router()
        r.options("/items", endpoint)
        client = make_app(r)
        assert client.options("/items").status_code == 200

    def test_get_returns_json(self):
        r = Router()
        r.get("/ping", endpoint)
        client = make_app(r)
        assert client.get("/ping").json() == {"ok": True}


# ---------------------------------------------------------------------------
# resource() — full CRUD
# ---------------------------------------------------------------------------


class PostController:
    def index(self):
        return []

    def create(self):
        return {}

    def store(self):
        return {}

    def show(self, post):
        return {"id": post}

    def edit(self, post):
        return {"id": post}

    def update(self, post):
        return {"id": post}

    def destroy(self, post):
        return {"id": post}


class TestResourceFullCrud:
    def _routes(self) -> Router:
        r = Router()
        r.resource("posts", PostController)
        return r

    def _route_names(self) -> set:
        r = self._routes()
        return {route.name for route in r.router.routes}

    def test_generates_index_route(self):
        client = make_app(self._routes())
        assert client.get("/posts").status_code == 200

    def test_generates_create_route(self):
        client = make_app(self._routes())
        assert client.get("/posts/create").status_code == 200

    def test_generates_store_route(self):
        client = make_app(self._routes())
        assert client.post("/posts").status_code == 200

    def test_generates_show_route(self):
        client = make_app(self._routes())
        assert client.get("/posts/1").status_code == 200

    def test_generates_edit_route(self):
        client = make_app(self._routes())
        assert client.get("/posts/1/edit").status_code == 200

    def test_generates_update_route(self):
        client = make_app(self._routes())
        assert client.put("/posts/1").status_code == 200

    def test_generates_destroy_route(self):
        client = make_app(self._routes())
        assert client.delete("/posts/1").status_code == 200

    def test_seven_routes_total(self):
        r = self._routes()
        assert len(r.router.routes) == 7

    def test_default_route_names(self):
        names = self._route_names()
        assert "posts" in names
        assert "posts.store" in names
        assert "posts.show" in names
        assert "posts.edit" in names
        assert "posts.update" in names
        assert "posts.destroy" in names


# ---------------------------------------------------------------------------
# resource() — only=
# ---------------------------------------------------------------------------


class TestResourceOnly:
    def test_only_index(self):
        r = Router()
        r.resource("posts", PostController, only={"index"})
        assert len(r.router.routes) == 1
        client = make_app(r)
        assert client.get("/posts").status_code == 200
        assert client.get("/posts/create").status_code == 404

    def test_only_show_and_index(self):
        r = Router()
        r.resource("posts", PostController, only={"index", "show"})
        names = {route.name for route in r.router.routes}
        assert "posts" in names
        assert "posts.show" in names
        assert "posts.store" not in names
        assert len(r.router.routes) == 2


# ---------------------------------------------------------------------------
# resource() — excepts=
# ---------------------------------------------------------------------------


class TestResourceExcepts:
    def test_excepts_destroy(self):
        r = Router()
        r.resource("posts", PostController, excepts={"destroy"})
        names = {route.name for route in r.router.routes}
        assert "posts.destroy" not in names
        assert len(r.router.routes) == 6

    def test_excepts_create_and_edit(self):
        r = Router()
        r.resource("posts", PostController, excepts={"create", "edit"})
        names = {route.name for route in r.router.routes}
        assert "posts.create" not in names
        assert "posts.edit" not in names
        assert len(r.router.routes) == 5


# ---------------------------------------------------------------------------
# resource() — names=
# ---------------------------------------------------------------------------


class TestResourceNames:
    def test_custom_index_name(self):
        r = Router()
        r.resource("posts", PostController, names={"index": "post-list"})
        names = {route.name for route in r.router.routes}
        assert "post-list" in names
        assert "posts" not in names

    def test_custom_show_name(self):
        r = Router()
        r.resource("posts", PostController, names={"show": "post-detail"})
        names = {route.name for route in r.router.routes}
        assert "post-detail" in names


# ---------------------------------------------------------------------------
# resource() — parameters=
# ---------------------------------------------------------------------------


class TestResourceParameters:
    def test_custom_parameter_name(self):
        r = Router()
        r.resource("posts", PostController, parameters={"posts": "slug"})
        paths = [route.path for route in r.router.routes]
        assert "/posts/{slug}" in paths
        assert "/posts/{slug}/edit" in paths

    def test_default_parameter_strips_trailing_s(self):
        r = Router()
        r.resource("posts", PostController)
        paths = [route.path for route in r.router.routes]
        assert "/posts/{post}" in paths


# ---------------------------------------------------------------------------
# Router with class instance (not class)
# ---------------------------------------------------------------------------


class TestResourceWithInstance:
    def test_accepts_controller_instance(self):
        r = Router()
        r.resource("posts", PostController())
        assert len(r.router.routes) == 7


# ---------------------------------------------------------------------------
# Router prefix
# ---------------------------------------------------------------------------


class TestRouterPrefix:
    def test_prefix_applied_to_routes(self):
        r = Router(prefix="/api/v1")
        r.get("/items", endpoint)
        client = make_app(r)
        assert client.get("/api/v1/items").status_code == 200

    def test_without_prefix(self):
        r = Router()
        r.get("/items", endpoint)
        client = make_app(r)
        assert client.get("/items").status_code == 200


# ---------------------------------------------------------------------------
# Dependency injection
# ---------------------------------------------------------------------------


class TestDependencies:
    def test_dependency_injected_via_depends(self):
        def get_user():
            return "alice"

        def authed_endpoint(user: str = Depends(get_user)):
            return {"user": user}

        r = Router()
        r.get("/profile", authed_endpoint)
        client = make_app(r)
        response = client.get("/profile")
        assert response.status_code == 200
        assert response.json() == {"user": "alice"}

    def test_router_level_dependency(self):
        calls = []

        def auth_check():
            calls.append("checked")

        r = Router(dependencies=[Depends(auth_check)])
        r.get("/secure", endpoint)
        client = make_app(r)
        client.get("/secure")
        assert calls == ["checked"]


# ---------------------------------------------------------------------------
# __getattr__ delegation to underlying APIRouter
# ---------------------------------------------------------------------------


class TestRouterGetattr:
    def test_routes_attribute_delegated(self):
        r = Router()
        r.get("/x", endpoint)
        assert r.routes is r.router.routes

    def test_prefix_attribute_delegated(self):
        r = Router(prefix="/foo")
        assert r.prefix == "/foo"
