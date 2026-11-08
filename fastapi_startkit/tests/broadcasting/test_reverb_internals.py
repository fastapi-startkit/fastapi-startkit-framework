from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.websockets import WebSocketDisconnect

from fastapi_startkit.broadcasting.reverb.channel_manager import ChannelManager
from fastapi_startkit.broadcasting.reverb.connection import ConnectionManager
from fastapi_startkit.broadcasting.reverb.server import ReverbServer
from fastapi_startkit.broadcasting.reverb.signature import sign, verify

KEY = "local"
SECRET = "unit-secret"
SOCKET_ID = "123.456"


def test_unsubscribe_from_unknown_channel_keeps_other_subscriptions():
    channels = ChannelManager()
    channels.subscribe("orders.1", "1.1")

    channels.unsubscribe("missing", "1.1")

    assert channels.subscribers("orders.1") == {"1.1"}
    assert channels.subscribers("missing") == set()


def test_connection_manager_retries_when_socket_id_is_taken(monkeypatch):
    connections = ConnectionManager()
    first, second = MagicMock(), MagicMock()
    ids = iter(["1.1", "1.1", "2.2"])
    monkeypatch.setattr(ConnectionManager, "_new_socket_id", staticmethod(lambda: next(ids)))

    first_id = connections.add(first)
    second_id = connections.add(second)

    assert (first_id, second_id) == ("1.1", "2.2")
    assert connections.get("1.1") is first
    assert connections.get("2.2") is second


@pytest.mark.parametrize(
    ("socket_id", "channel"),
    [
        ("not-a-socket-id", "private-orders.1"),
        (SOCKET_ID, "private-orders:1"),
        (SOCKET_ID, "orders.1"),
    ],
)
def test_verify_rejects_invalid_socket_id_or_unprotected_channel(socket_id, channel):
    auth = sign(KEY, SECRET, socket_id, channel)

    assert verify(KEY, SECRET, socket_id, channel, auth) is False


def test_verify_accepts_valid_signature_for_private_channel():
    channel = "private-orders.1"
    auth = sign(KEY, SECRET, SOCKET_ID, channel)

    assert verify(KEY, SECRET, SOCKET_ID, channel, auth) is True


async def test_disconnect_while_handshaking_releases_connection():
    server = ReverbServer(KEY, SECRET)
    websocket = MagicMock()
    websocket.accept = AsyncMock()
    websocket.send_text = AsyncMock(side_effect=WebSocketDisconnect(1006))

    await server.handle(websocket)

    assert server.connections.all() == {}


async def test_broadcast_skips_failing_socket_and_reaches_the_rest():
    server = ReverbServer(KEY, SECRET)
    broken, healthy = MagicMock(), MagicMock()
    broken.send_text = AsyncMock(side_effect=RuntimeError("closed"))
    healthy.send_text = AsyncMock()
    for websocket in (broken, healthy):
        socket_id = server.connections.add(websocket)
        server.channels.subscribe("orders.1", socket_id)

    await server.broadcast_to_channel("orders.1", "OrderShipped", {"order_id": 1})

    broken.send_text.assert_awaited_once()
    healthy.send_text.assert_awaited_once()
