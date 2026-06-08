"""Tests for the ReverbServer WebSocket handler (Pusher protocol)."""
import json
import pytest
from starlette.testclient import TestClient

from fastapi_startkit.broadcasting.reverb.server import ReverbServer


@pytest.fixture
def server():
    return ReverbServer()


@pytest.fixture
def client(server):
    app = server.as_starlette_app(app_key="local")
    return TestClient(app)


class TestReverbServerConnect:
    def test_connection_established_on_connect(self, client):
        with client.websocket_connect("/app/local") as ws:
            msg = json.loads(ws.receive_text())
            assert msg["event"] == "pusher:connection_established"
            data = json.loads(msg["data"])
            assert "socket_id" in data
            assert data["activity_timeout"] == 120

    def test_ping_returns_pong(self, client):
        with client.websocket_connect("/app/local") as ws:
            ws.receive_text()  # consume connection_established
            ws.send_text(json.dumps({"event": "pusher:ping", "data": {}}))
            msg = json.loads(ws.receive_text())
            assert msg["event"] == "pusher:pong"

    def test_subscribe_returns_subscription_succeeded(self, client):
        with client.websocket_connect("/app/local") as ws:
            ws.receive_text()  # consume connection_established
            ws.send_text(json.dumps({
                "event": "pusher:subscribe",
                "data": {"channel": "orders"}
            }))
            msg = json.loads(ws.receive_text())
            assert msg["event"] == "pusher_internal:subscription_succeeded"
            assert msg["channel"] == "orders"


class TestReverbServerBroadcast:
    @pytest.mark.asyncio
    async def test_broadcast_to_subscribed_channel(self, server):
        app = server.as_starlette_app(app_key="local")
        client = TestClient(app)

        with client.websocket_connect("/app/local") as ws:
            ws.receive_text()  # connection_established
            ws.send_text(json.dumps({
                "event": "pusher:subscribe",
                "data": {"channel": "orders"}
            }))
            ws.receive_text()  # subscription_succeeded

            # Broadcast from server side
            await server.broadcast_to_channel("orders", "OrderShipped", {"order_id": 42})

            msg = json.loads(ws.receive_text())
            assert msg["event"] == "OrderShipped"
            assert msg["channel"] == "orders"
            assert msg["data"]["order_id"] == 42

    @pytest.mark.asyncio
    async def test_broadcast_not_received_without_subscription(self, server):
        """A channel with no subscribers should not error."""
        # Should simply not raise
        await server.broadcast_to_channel("no-subscribers", "SomeEvent", {"key": "val"})
