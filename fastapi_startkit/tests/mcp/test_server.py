"""Tests for the Server class and its FastAPI router."""

import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.routing import APIRouter

from fastapi_startkit.mcp.server import Server
from fastapi_startkit.mcp.tool import Tool
from fastapi_startkit.mcp.prompt import Prompt
from fastapi_startkit.mcp.resource import Resource
from fastapi_startkit.mcp.argument import Argument
from fastapi_startkit.mcp.response import Response


# ---------------------------------------------------------------------------
# Fixtures / concrete impls
# ---------------------------------------------------------------------------


class PingTool(Tool):
    name = "ping"
    description = "Returns pong."

    async def handle(self, arguments: dict) -> Response:
        return Response.text("pong")


class HelloPrompt(Prompt):
    name = "hello"
    description = "Says hello."

    async def handle(self, arguments: dict) -> Response:
        return Response.text("hello!")


class InfoResource(Resource):
    uri = "resource:///info"
    name = "info"

    async def read(self, **kwargs) -> str:
        return "info content"


class TestServer(Server):
    name = "test-server"

    def tools(self):
        return [PingTool]

    def prompts(self):
        return [HelloPrompt]

    def resources(self):
        return [InfoResource]


def make_client(prefix="/mcp") -> TestClient:
    server = TestServer()
    app = FastAPI()
    app.include_router(server.router(prefix=prefix))
    return TestClient(app)


def rpc(method: str, params: dict | None = None, req_id: int = 1) -> dict:
    payload: dict = {"jsonrpc": "2.0", "method": method, "id": req_id}
    if params:
        payload["params"] = params
    return payload


def notification(method: str) -> dict:
    return {"jsonrpc": "2.0", "method": method}


# ---------------------------------------------------------------------------
# Server.router()
# ---------------------------------------------------------------------------


class TestServerRouter:
    def test_router_returns_api_router(self):
        server = TestServer()
        r = server.router("/mcp")
        assert isinstance(r, APIRouter)

    def test_router_has_post_route(self):
        server = TestServer()
        r = server.router("/mcp")
        methods = {m for route in r.routes for m in getattr(route, "methods", [])}
        assert "POST" in methods

    def test_router_has_get_route(self):
        server = TestServer()
        r = server.router("/mcp")
        methods = {m for route in r.routes for m in getattr(route, "methods", [])}
        assert "GET" in methods


# ---------------------------------------------------------------------------
# POST /mcp — happy-path dispatches
# ---------------------------------------------------------------------------


class TestPostDispatch:
    def test_initialize(self):
        client = make_client()
        resp = client.post("/mcp", json=rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"},
        }))
        assert resp.status_code == 200
        body = resp.json()
        assert body["result"]["serverInfo"]["name"] == "test-server"

    def test_tools_list(self):
        client = make_client()
        resp = client.post("/mcp", json=rpc("tools/list"))
        assert resp.status_code == 200
        names = [t["name"] for t in resp.json()["result"]["tools"]]
        assert "ping" in names

    def test_tools_call(self):
        client = make_client()
        resp = client.post("/mcp", json=rpc("tools/call", {"name": "ping", "arguments": {}}))
        assert resp.status_code == 200
        assert resp.json()["result"]["content"][0]["text"] == "pong"

    def test_prompts_list(self):
        client = make_client()
        resp = client.post("/mcp", json=rpc("prompts/list"))
        assert resp.status_code == 200
        names = [p["name"] for p in resp.json()["result"]["prompts"]]
        assert "hello" in names

    def test_prompts_get(self):
        client = make_client()
        resp = client.post("/mcp", json=rpc("prompts/get", {"name": "hello"}))
        assert resp.status_code == 200
        text = resp.json()["result"]["messages"][0]["content"]["text"]
        assert text == "hello!"

    def test_resources_list(self):
        client = make_client()
        resp = client.post("/mcp", json=rpc("resources/list"))
        assert resp.status_code == 200
        uris = [r["uri"] for r in resp.json()["result"]["resources"]]
        assert "resource:///info" in uris

    def test_resources_read(self):
        client = make_client()
        resp = client.post("/mcp", json=rpc("resources/read", {"uri": "resource:///info"}))
        assert resp.status_code == 200
        assert resp.json()["result"]["contents"][0]["text"] == "info content"

    def test_unknown_method_returns_error(self):
        client = make_client()
        resp = client.post("/mcp", json=rpc("unknown/method"))
        assert resp.status_code == 200
        assert "error" in resp.json()


# ---------------------------------------------------------------------------
# GET /mcp — must return 405
# ---------------------------------------------------------------------------


class TestGetReturns405:
    def test_get_returns_405(self):
        client = make_client()
        resp = client.get("/mcp")
        assert resp.status_code == 405

    def test_get_allow_header(self):
        client = make_client()
        resp = client.get("/mcp")
        assert "POST" in resp.headers.get("allow", "")


# ---------------------------------------------------------------------------
# Notifications — must return 202
# ---------------------------------------------------------------------------


class TestNotifications:
    def test_notification_returns_202(self):
        client = make_client()
        resp = client.post("/mcp", json=notification("tools/list"))
        assert resp.status_code == 202

    def test_notification_body_is_empty(self):
        client = make_client()
        resp = client.post("/mcp", json=notification("initialize"))
        assert resp.content == b""


# ---------------------------------------------------------------------------
# Custom prefix
# ---------------------------------------------------------------------------


class TestCustomPrefix:
    def test_custom_prefix_works(self):
        client = make_client(prefix="/api/mcp")
        resp = client.post("/api/mcp", json=rpc("tools/list"))
        assert resp.status_code == 200

    def test_default_prefix_not_accessible_under_custom(self):
        client = make_client(prefix="/api/mcp")
        resp = client.post("/mcp", json=rpc("tools/list"))
        assert resp.status_code == 404
