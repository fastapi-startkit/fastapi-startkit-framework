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


def test_connection_established(client):
    with client.websocket_connect("/app/local") as ws:
        msg = json.loads(ws.receive_text())
        assert msg["event"] == "pusher:connection_established"
        data = json.loads(msg["data"])
        assert "socket_id" in data
        assert data["activity_timeout"] == 120


def test_ping_pong(client):
    with client.websocket_connect("/app/local") as ws:
        ws.receive_text()  # connection_established
        ws.send_text(json.dumps({"event": "pusher:ping", "data": {}}))
        msg = json.loads(ws.receive_text())
        assert msg["event"] == "pusher:pong"


def test_subscribe_to_channel(client):
    with client.websocket_connect("/app/local") as ws:
        ws.receive_text()  # connection_established
        ws.send_text(json.dumps({"event": "pusher:subscribe", "data": {"channel": "orders.1"}}))
        msg = json.loads(ws.receive_text())
        assert msg["event"] == "pusher_internal:subscription_succeeded"
        assert msg["channel"] == "orders.1"


def test_broadcast_delivers_to_subscriber(server):
    app = server.as_starlette_app(app_key="local")
    client = TestClient(app)

    with client.websocket_connect("/app/local") as ws:
        ws.receive_text()  # connection_established

        # Subscribe
        ws.send_text(json.dumps({"event": "pusher:subscribe", "data": {"channel": "orders.1"}}))
        ws.receive_text()  # subscription_succeeded

        # Broadcast from server side
        import asyncio

        asyncio.get_event_loop().run_until_complete(
            server.broadcast_to_channel("orders.1", "OrderShipped", {"order_id": 1})
        )

        msg = json.loads(ws.receive_text())
        assert msg["event"] == "OrderShipped"
        assert msg["channel"] == "orders.1"
        assert msg["data"]["order_id"] == 1


def test_socket_id_is_unique(client):
    socket_ids = []
    for _ in range(3):
        with client.websocket_connect("/app/local") as ws:
            msg = json.loads(ws.receive_text())
            data = json.loads(msg["data"])
            socket_ids.append(data["socket_id"])
    assert len(set(socket_ids)) == 3
