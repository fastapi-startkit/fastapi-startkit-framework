import asyncio
import json

import pytest
from starlette.testclient import TestClient

from fastapi_startkit.application import Application
from fastapi_startkit.broadcasting.provider import ReverbProvider
from fastapi_startkit.support import Provider

KEY = "local"


class RouteProvider(Provider):
    def register(self) -> None:
        pass

    def boot(self) -> None:
        @self.app.fastapi.get("/ping")
        async def ping():
            return {"pong": True}


class User:
    def __init__(self, id):
        self.id = id


@pytest.fixture
def base_path(tmp_path):
    routes = tmp_path / "routes"
    routes.mkdir()
    (routes / "channels.py").write_text(
        "from fastapi_startkit.broadcasting import channel\n"
        "\n"
        "@channel('private-orders.{order_id}')\n"
        "async def authorize_orders(user, order_id: int):\n"
        "    return user is not None and user.id == order_id\n"
        "\n"
        "@channel('presence-room.{room}')\n"
        "async def authorize_room(user, room):\n"
        "    return user is not None\n"
    )
    return tmp_path


def make_client(base_path, providers, user=None):
    app = Application(base_path=base_path, env="testing", providers=providers)

    @app.fastapi.middleware("http")
    async def attach_user(request, call_next):
        request.state.user = user
        return await call_next(request)

    @app.fastapi.get("/after")
    async def after():
        return {"after": True}

    return app, TestClient(app.fastapi)


def connect(ws):
    return json.loads(json.loads(ws.receive_text())["data"])["socket_id"]


def subscribe(ws, channel, auth=None, channel_data=None):
    data = {"channel": channel}
    if auth is not None:
        data["auth"] = auth
    if channel_data is not None:
        data["channel_data"] = channel_data
    ws.send_text(json.dumps({"event": "pusher:subscribe", "data": data}))
    return json.loads(ws.receive_text())


def ping(ws):
    ws.send_text(json.dumps({"event": "pusher:ping", "data": {}}))
    return json.loads(ws.receive_text())


class TestRouteOrder:
    @pytest.mark.parametrize("reverb_first", [True, False])
    def test_routes_and_auth_endpoint_reachable(self, base_path, reverb_first):
        providers = [ReverbProvider, RouteProvider] if reverb_first else [RouteProvider, ReverbProvider]
        _, client = make_client(base_path, providers, user=User(7))

        assert client.get("/ping").json() == {"pong": True}
        assert client.get("/after").json() == {"after": True}
        response = client.post("/broadcasting/auth", data={"socket_id": "1.1", "channel_name": "private-orders.7"})
        assert response.status_code == 200

        with client.websocket_connect(f"/app/{KEY}") as ws:
            assert connect(ws)


class TestPrivateSubscription:
    def test_unauthenticated_subscribe_is_rejected_and_receives_nothing(self, base_path):
        app, client = make_client(base_path, [ReverbProvider])
        server = app.make("reverb.server")

        with client.websocket_connect(f"/app/{KEY}") as ws:
            socket_id = connect(ws)
            reply = subscribe(ws, "private-orders.7")
            assert reply["event"] == "pusher:subscription_error"
            assert reply["channel"] == "private-orders.7"
            assert reply["data"]["status"] == 401
            assert socket_id not in server.channels.subscribers("private-orders.7")

            asyncio.run(server.broadcast_to_channel("private-orders.7", "OrderShipped", {"secret": 1}))
            assert ping(ws)["event"] == "pusher:pong"

    def test_forged_signature_is_rejected(self, base_path):
        _, client = make_client(base_path, [ReverbProvider])
        with client.websocket_connect(f"/app/{KEY}") as ws:
            connect(ws)
            assert subscribe(ws, "private-orders.7", auth=f"{KEY}:{'0' * 64}")["event"] == "pusher:subscription_error"
            assert subscribe(ws, "private-orders.7", auth="ünïcode")["event"] == "pusher:subscription_error"
            assert subscribe(ws, "private-orders.7", auth=123)["event"] == "pusher:subscription_error"

    def test_signature_for_another_socket_is_rejected(self, base_path):
        _, client = make_client(base_path, [ReverbProvider], user=User(7))
        auth = client.post(
            "/broadcasting/auth", data={"socket_id": "someone-else", "channel_name": "private-orders.7"}
        ).json()["auth"]
        with client.websocket_connect(f"/app/{KEY}") as ws:
            connect(ws)
            assert subscribe(ws, "private-orders.7", auth=auth)["event"] == "pusher:subscription_error"

    def test_unauthorized_user_cannot_obtain_signature(self, base_path):
        _, client = make_client(base_path, [ReverbProvider], user=User(8))
        response = client.post("/broadcasting/auth", data={"socket_id": "1.1", "channel_name": "private-orders.7"})
        assert response.status_code == 403

    def test_authorized_subscribe_receives_broadcast(self, base_path):
        app, client = make_client(base_path, [ReverbProvider], user=User(7))
        server = app.make("reverb.server")
        with client.websocket_connect(f"/app/{KEY}") as ws:
            socket_id = connect(ws)
            auth = client.post(
                "/broadcasting/auth", json={"socket_id": socket_id, "channel_name": "private-orders.7"}
            ).json()["auth"]
            assert subscribe(ws, "private-orders.7", auth=auth)["event"] == "pusher_internal:subscription_succeeded"

            asyncio.run(server.broadcast_to_channel("private-orders.7", "OrderShipped", {"order_id": 7}))
            message = json.loads(ws.receive_text())
            assert message["event"] == "OrderShipped"
            assert message["data"] == {"order_id": 7}


class TestPresenceSubscription:
    def test_presence_requires_signed_channel_data(self, base_path):
        _, client = make_client(base_path, [ReverbProvider], user=User(7))
        with client.websocket_connect(f"/app/{KEY}") as ws:
            socket_id = connect(ws)
            body = client.post(
                "/broadcasting/auth", json={"socket_id": socket_id, "channel_name": "presence-room.1"}
            ).json()
            assert json.loads(body["channel_data"])["user_id"] == "7"

            tampered = json.dumps({"user_id": "1", "user_info": {}})
            assert subscribe(ws, "presence-room.1", body["auth"], tampered)["event"] == "pusher:subscription_error"
            reply = subscribe(ws, "presence-room.1", body["auth"], body["channel_data"])
            assert reply["event"] == "pusher_internal:subscription_succeeded"
