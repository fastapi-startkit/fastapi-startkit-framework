"""Benchmarks for Router route registration and resource() CRUD expansion (task #1045).

Deselected by default (see `addopts` in pyproject.toml); run explicitly with:

    uv run pytest -m benchmark tests/fastapi/benchmarks/test_router_benchmark.py
"""

import pytest
from fastapi import APIRouter

from fastapi_startkit.fastapi.routers.router import Router


def endpoint():
    return {"ok": True}


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


@pytest.mark.benchmark(group="router-single-route")
class TestSingleRouteRegistrationBenchmarks:
    def test_router_get(self, benchmark):
        benchmark(lambda: Router().get("/items", endpoint))

    def test_raw_apirouter_get_baseline(self, benchmark):
        """Registering the same route directly on APIRouter, bypassing the Router wrapper."""
        benchmark(lambda: APIRouter().add_api_route("/items", endpoint, methods=["GET"]))


@pytest.mark.benchmark(group="router-resource-expansion")
class TestResourceExpansionBenchmarks:
    def test_resource_full_crud(self, benchmark):
        """Router.resource() expanding a controller into all 7 CRUD routes."""
        benchmark(lambda: Router().resource("posts", PostController))

    def test_raw_apirouter_equivalent_crud_baseline(self, benchmark):
        """Hand-registering the same 7 routes directly — the floor resource() is measured against."""

        def register():
            router = APIRouter()
            controller = PostController()
            router.add_api_route("/posts", controller.index, methods=["GET"], name="posts")
            router.add_api_route("/posts/create", controller.create, methods=["GET"], name="posts.create")
            router.add_api_route("/posts", controller.store, methods=["POST"], name="posts.store")
            router.add_api_route("/posts/{post}", controller.show, methods=["GET"], name="posts.show")
            router.add_api_route("/posts/{post}/edit", controller.edit, methods=["GET"], name="posts.edit")
            router.add_api_route("/posts/{post}", controller.update, methods=["PUT"], name="posts.update")
            router.add_api_route("/posts/{post}", controller.destroy, methods=["DELETE"], name="posts.destroy")

        benchmark(register)
