import json
import pytest
from starlette.websockets import WebSocketDisconnect
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

        asyncio.run(server.broadcast_to_channel("orders.1", "OrderShipped", {"order_id": 1}))

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


def _connect(ws):
    return json.loads(json.loads(ws.receive_text())["data"])["socket_id"]


def _ping(ws):
    ws.send_text(json.dumps({"event": "pusher:ping", "data": {}}))
    return json.loads(ws.receive_text())["event"]


@pytest.mark.parametrize(
    "frame",
    [
        "not json",
        "[1, 2]",
        "42",
        json.dumps({"event": "pusher:subscribe", "data": "x"}),
        json.dumps({"event": "pusher:subscribe", "data": {"channel": 1}}),
        json.dumps({"event": 5}),
    ],
)
def test_malformed_frame_replies_with_error_and_keeps_connection(client, frame):
    with client.websocket_connect("/app/local") as ws:
        _connect(ws)
        ws.send_text(frame)
        assert json.loads(ws.receive_text())["event"] == "pusher:error"
        assert _ping(ws) == "pusher:pong"


def test_binary_frame_replies_with_error(client):
    with client.websocket_connect("/app/local") as ws:
        _connect(ws)
        ws.send_bytes(b"\x00\x01")
        assert json.loads(ws.receive_text())["event"] == "pusher:error"
        assert _ping(ws) == "pusher:pong"


def test_oversized_frame_closes_connection(server, client):
    with client.websocket_connect("/app/local") as ws:
        _connect(ws)
        ws.send_text("x" * (server.max_message_size + 1))
        assert json.loads(ws.receive_text())["event"] == "pusher:error"
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_text()
        assert closed.value.code == 1009
    assert server.connections.all() == {}


def test_connection_is_cleaned_up_after_malformed_frames(server, client):
    with client.websocket_connect("/app/local") as ws:
        socket_id = _connect(ws)
        ws.send_text(json.dumps({"event": "pusher:subscribe", "data": {"channel": "orders.1"}}))
        ws.receive_text()
        ws.send_text("not json")
        ws.receive_text()
    assert socket_id not in server.connections.all()
    assert socket_id not in server.channels.subscribers("orders.1")


def test_connection_is_cleaned_up_when_handler_fails(server, client, monkeypatch):
    async def explode(*args):
        raise RuntimeError("boom")

    monkeypatch.setattr(server, "_handle_message", explode)
    with pytest.raises(RuntimeError):
        with client.websocket_connect("/app/local") as ws:
            _connect(ws)
            ws.send_text(json.dumps({"event": "pusher:ping"}))
            ws.receive_text()
    assert server.connections.all() == {}
