import json
from types import SimpleNamespace

import pytest
from starlette.testclient import TestClient

from fastapi_startkit.application import Application
from fastapi_startkit.broadcasting.config import ReverbConnectionConfig
from fastapi_startkit.broadcasting.manager import BroadcastManager
from fastapi_startkit.broadcasting.provider import ReverbProvider
from fastapi_startkit.broadcasting.reverb.server import ReverbServer
from fastapi_startkit.broadcasting.reverb.signature import sign

from .conftest import SECRET


class TestSecret:
    def test_has_no_default_secret(self, monkeypatch):
        monkeypatch.delenv("REVERB_APP_SECRET")
        assert ReverbConnectionConfig().secret == ""

    @pytest.mark.parametrize("secret", [None, "", "secret"])
    def test_refuses_to_boot_outside_local_and_testing_without_real_secret(self, monkeypatch, tmp_path, secret):
        monkeypatch.delenv("PYTEST_CURRENT_TEST")
        if secret is None:
            monkeypatch.delenv("REVERB_APP_SECRET")
        else:
            monkeypatch.setenv("REVERB_APP_SECRET", secret)
        with pytest.raises(RuntimeError, match="REVERB_APP_SECRET"):
            Application(base_path=tmp_path, env="production", providers=[ReverbProvider])

    def test_boots_in_production_with_real_secret(self, monkeypatch, tmp_path):
        monkeypatch.delenv("PYTEST_CURRENT_TEST")
        app = Application(base_path=tmp_path, env="production", providers=[ReverbProvider])
        assert app.make("reverb.server").secret == SECRET

    @pytest.mark.parametrize("env", ["local", "testing"])
    def test_boots_in_local_and_testing_without_secret(self, monkeypatch, tmp_path, env):
        monkeypatch.delenv("PYTEST_CURRENT_TEST")
        monkeypatch.delenv("REVERB_APP_SECRET")
        app = Application(base_path=tmp_path, env=env, providers=[ReverbProvider])
        assert app.make("reverb.server").secret == ""

    def test_empty_secret_rejects_every_protected_subscription(self, monkeypatch, tmp_path):
        monkeypatch.delenv("REVERB_APP_SECRET")
        app = make_app(tmp_path)
        register_rule(app, "private-room.{room}", lambda user, room: True)
        app.bind("auth", SimpleNamespace(user=SimpleNamespace(id=1)))
        client = client_for(app)
        with client.websocket_connect("/app/local") as ws:
            socket_id = json.loads(json.loads(ws.receive_text())["data"])["socket_id"]
            assert post_auth(app, channel_name="private-room.7", socket_id=socket_id).status_code == 403

            auth = sign("local", "", socket_id, "private-room.7")
            ws.send_text(json.dumps({"event": "pusher:subscribe", "data": {"channel": "private-room.7", "auth": auth}}))
            assert json.loads(ws.receive_text())["event"] == "pusher:subscription_error"


def make_app(tmp_path):
    return Application(base_path=tmp_path, env="testing", providers=[ReverbProvider])


def client_for(app):
    return TestClient(app.fastapi)


def register_rule(app, pattern, callback):
    app.make("broadcasting").channel_registry.register(pattern, callback)


def post_auth(app, **body):
    return client_for(app).post("/broadcasting/auth", data=body)


class TestRegister:
    def test_binds_manager_and_server(self, tmp_path):
        app = make_app(tmp_path)
        assert isinstance(app.make("broadcasting"), BroadcastManager)
        assert isinstance(app.make("reverb.server"), ReverbServer)

    def test_server_uses_configured_credentials(self, tmp_path, reverb_secret):
        server = make_app(tmp_path).make("reverb.server")
        assert (server.key, server.secret) == ("local", reverb_secret)

    def test_publishes_channels_stub(self, tmp_path):
        app = make_app(tmp_path)
        published = app.published_resources.get("broadcasting", {})
        assert any(dest == "routes/channels.py" for dest in published.values())


class TestAuthEndpoint:
    def test_auth_route_is_reachable_after_full_boot(self, tmp_path):
        response = post_auth(make_app(tmp_path), channel_name="private-secret", socket_id="1.1")
        assert response.status_code == 403

    def test_routes_added_after_boot_are_not_shadowed(self, tmp_path):
        app = make_app(tmp_path)
        app.fastapi.get("/ping")(lambda: {"ok": True})
        assert client_for(app).get("/ping").status_code == 200

    def test_private_channel_returns_signed_auth(self, tmp_path):
        app = make_app(tmp_path)
        register_rule(app, "private-room.{room}", lambda user, room: True)
        app.bind("auth", SimpleNamespace(user=SimpleNamespace(id=1)))
        response = post_auth(app, channel_name="private-room.7", socket_id="123.456")
        assert response.status_code == 200
        assert response.json() == {"auth": sign("local", SECRET, "123.456", "private-room.7")}

    def test_accepts_json_body(self, tmp_path):
        app = make_app(tmp_path)
        register_rule(app, "private-room.{room}", lambda user, room: True)
        app.bind("auth", SimpleNamespace(user=SimpleNamespace(id=1)))
        response = client_for(app).post(
            "/broadcasting/auth", json={"channel_name": "private-room.7", "socket_id": "123.456"}
        )
        assert response.json()["auth"] == sign("local", SECRET, "123.456", "private-room.7")

    def test_presence_channel_signs_channel_data(self, tmp_path):
        app = make_app(tmp_path)
        register_rule(app, "presence-room", lambda user: True)
        app.bind("auth", SimpleNamespace(user=SimpleNamespace(id=9)))
        body = post_auth(app, channel_name="presence-room", socket_id="1.2").json()
        assert body["channel_data"] == '{"user_id": "9"}'
        assert body["auth"] == sign("local", SECRET, "1.2", "presence-room", body["channel_data"])

    def test_denied_callback_returns_403(self, tmp_path):
        app = make_app(tmp_path)
        register_rule(app, "private-room.{room}", lambda user, room: False)
        assert post_auth(app, channel_name="private-room.7", socket_id="1.1").status_code == 403

    def test_requires_socket_id(self, tmp_path):
        assert post_auth(make_app(tmp_path), channel_name="orders").status_code == 422

    def test_rejects_non_string_json_channel_name(self, tmp_path):
        response = client_for(make_app(tmp_path)).post(
            "/broadcasting/auth", json={"channel_name": 42, "socket_id": "1.1"}
        )
        assert response.status_code == 422

    def test_rejects_file_upload_as_channel_name(self, tmp_path):
        response = client_for(make_app(tmp_path)).post(
            "/broadcasting/auth", data={"socket_id": "1.1"}, files={"channel_name": ("x.txt", b"x")}
        )
        assert response.status_code == 422

    def test_uses_request_state_user(self, tmp_path):
        app = make_app(tmp_path)
        register_rule(app, "private-me", lambda user: user.id == 3)

        @app.fastapi.middleware("http")
        async def authenticate(request, call_next):
            request.state.user = SimpleNamespace(id=3)
            return await call_next(request)

        assert post_auth(app, channel_name="private-me", socket_id="1.1").status_code == 200

    def test_resolves_user_from_callable_auth_service(self, tmp_path):
        app = make_app(tmp_path)
        register_rule(app, "private-me", lambda user: user.id == 1)
        app.bind("auth", SimpleNamespace(user=lambda: SimpleNamespace(id=1)))
        assert post_auth(app, channel_name="private-me", socket_id="1.1").status_code == 200

    def test_resolves_user_from_attribute_auth_service(self, tmp_path):
        app = make_app(tmp_path)
        register_rule(app, "private-me", lambda user: user.id == 2)
        app.bind("auth", SimpleNamespace(user=SimpleNamespace(id=2)))
        assert post_auth(app, channel_name="private-me", socket_id="1.1").status_code == 200


class TestWebsocketSubscription:
    def test_private_subscribe_requires_signature_from_auth_endpoint(self, tmp_path):
        app = make_app(tmp_path)
        register_rule(app, "private-room.{room}", lambda user, room: True)
        app.bind("auth", SimpleNamespace(user=SimpleNamespace(id=1)))
        client = client_for(app)
        with client.websocket_connect("/app/local") as ws:
            socket_id = json.loads(json.loads(ws.receive_text())["data"])["socket_id"]

            ws.send_text(json.dumps({"event": "pusher:subscribe", "data": {"channel": "private-room.7"}}))
            assert json.loads(ws.receive_text())["event"] == "pusher:subscription_error"

            auth = post_auth(app, channel_name="private-room.7", socket_id=socket_id).json()["auth"]
            ws.send_text(json.dumps({"event": "pusher:subscribe", "data": {"channel": "private-room.7", "auth": auth}}))
            assert json.loads(ws.receive_text())["event"] == "pusher_internal:subscription_succeeded"


class TestChannelsFileAutoloading:
    async def test_registered_channel_authorizer_is_used(self, tmp_path):
        routes = tmp_path / "routes"
        routes.mkdir()
        (routes / "channels.py").write_text(
            "from fastapi_startkit.broadcasting import channel\n"
            "\n"
            "@channel('private-room.{room}')\n"
            "async def authorize_room(user, room):\n"
            "    return True\n"
        )

        app = make_app(tmp_path)
        registry = app.make("broadcasting").channel_registry
        assert await registry.authorize("private-room.7", None) is True

    def test_missing_channels_file_is_ignored(self, tmp_path):
        app = make_app(tmp_path)
        assert isinstance(app.make("broadcasting"), BroadcastManager)


class _RaisingFastapiApp:
    base_path = "/nonexistent-base-path"

    @property
    def fastapi(self):
        raise RuntimeError("FastAPI not available")


class TestMountingWithoutFastapi:
    def test_mount_websocket_skips_when_fastapi_unavailable(self):
        ReverbProvider(_RaisingFastapiApp())._mount_websocket()

    def test_mount_auth_endpoint_skips_when_fastapi_unavailable(self):
        ReverbProvider(_RaisingFastapiApp())._mount_auth_endpoint()

    def test_load_channels_file_skips_when_absent(self):
        ReverbProvider(_RaisingFastapiApp())._load_channels_file()
