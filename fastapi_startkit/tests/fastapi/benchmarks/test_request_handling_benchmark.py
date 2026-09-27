"""Benchmarks for request handling through the FastAPI integration layer (task #1045).

Deselected by default (see `addopts` in pyproject.toml); run explicitly with:

    uv run pytest -m benchmark tests/fastapi/benchmarks/test_request_handling_benchmark.py
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fastapi_startkit.fastapi.routers.router import Router


def ping():
    return {"ok": True}


def show_post(post: int):
    return {"id": post}


class PostController:
    def show(self, post):
        return show_post(post)


@pytest.fixture(scope="module")
def router_based_client():
    """A trivial GET endpoint registered through the Router wrapper."""
    router = Router()
    router.get("/ping", ping)
    app = FastAPI()
    app.include_router(router.router)
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="module")
def raw_fastapi_client():
    """The same endpoint registered directly on FastAPI, bypassing the Router wrapper."""
    app = FastAPI()
    app.get("/ping")(ping)
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="module")
def resource_client():
    """A resource()-expanded route with a path parameter, exercising Starlette's path matching."""
    router = Router()
    router.resource("posts", PostController)
    app = FastAPI()
    app.include_router(router.router)
    with TestClient(app) as client:
        yield client


@pytest.mark.benchmark(group="request-handling-json-get")
class TestRequestHandlingBenchmarks:
    def test_router_based_request(self, benchmark, router_based_client):
        benchmark(router_based_client.get, "/ping")

    def test_raw_fastapi_request_baseline(self, benchmark, raw_fastapi_client):
        benchmark(raw_fastapi_client.get, "/ping")

    def test_resource_route_with_path_param(self, benchmark, resource_client):
        benchmark(resource_client.get, "/posts/1")
