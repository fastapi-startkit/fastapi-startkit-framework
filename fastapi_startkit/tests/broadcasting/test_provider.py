from types import SimpleNamespace

from fastapi.testclient import TestClient

from fastapi_startkit.application import Application
from fastapi_startkit.broadcasting.manager import BroadcastManager
from fastapi_startkit.broadcasting.provider import ReverbProvider
from fastapi_startkit.broadcasting.reverb.server import ReverbServer


_MISSING = object()


def make_app(tmp_path):
    return Application(base_path=tmp_path, env="testing", providers=[ReverbProvider])


def mount_auth(tmp_path):
    """Register broadcasting and mount only the auth endpoint.

    The full ``boot()`` mounts a catch-all WebSocket sub-app at ``""`` which
    shadows the HTTP auth route, so exercise the auth handler on its own.
    """
    app = Application(base_path=tmp_path, env="testing", providers=[])
    provider = ReverbProvider(app)
    provider.register()
    provider._mount_auth_endpoint()
    return app


def auth_handler(app):
    for route in app.fastapi.routes:
        if getattr(route, "path", None) == "/broadcasting/auth":
            return route.endpoint
    raise AssertionError("auth route not mounted")


class FakeRequest:
    """Stand-in for a Starlette Request.

    ``from __future__ import annotations`` in the provider turns the handler's
    ``Request`` annotation into an unresolved forward-ref, so FastAPI cannot
    inject a real request through the test client. Calling the handler with
    this fake exercises the same body directly.
    """

    def __init__(self, content_type, *, json_body=None, form_body=None, user=_MISSING):
        self.headers = {"content-type": content_type}
        self._json = json_body or {}
        self._form = form_body or {}
        self.state = SimpleNamespace()
        if user is not _MISSING:
            self.state.user = user

    async def json(self):
        return self._json

    async def form(self):
        return self._form


class TestRegister:
    def test_binds_manager_and_server(self, tmp_path):
        app = make_app(tmp_path)
        assert isinstance(app.make("broadcasting"), BroadcastManager)
        assert isinstance(app.make("reverb.server"), ReverbServer)

    def test_publishes_channels_stub(self, tmp_path):
        app = make_app(tmp_path)
        published = app.published_resources.get("broadcasting", {})
        assert any(dest == "routes/channels.py" for dest in published.values())


class TestAuthEndpoint:
    async def test_public_channel_allowed_json(self, tmp_path):
        handler = auth_handler(mount_auth(tmp_path))
        response = await handler(FakeRequest("application/json", json_body={"channel_name": "orders"}))
        assert response.status_code == 200

    async def test_private_channel_denied_without_rule(self, tmp_path):
        handler = auth_handler(mount_auth(tmp_path))
        response = await handler(
            FakeRequest("application/json", json_body={"channel_name": "private-secret"})
        )
        assert response.status_code == 403

    async def test_accepts_form_encoded_body(self, tmp_path):
        handler = auth_handler(mount_auth(tmp_path))
        response = await handler(
            FakeRequest("application/x-www-form-urlencoded", form_body={"channel_name": "public-room"})
        )
        assert response.status_code == 200

    async def test_uses_request_state_user(self, tmp_path):
        handler = auth_handler(mount_auth(tmp_path))
        response = await handler(
            FakeRequest("application/json", json_body={"channel_name": "orders"}, user=object())
        )
        assert response.status_code == 200

    async def test_resolves_user_from_callable_auth_service(self, tmp_path):
        app = mount_auth(tmp_path)
        app.bind("auth", SimpleNamespace(user=lambda: SimpleNamespace(id=1)))
        handler = auth_handler(app)
        response = await handler(FakeRequest("application/json", json_body={"channel_name": "orders"}))
        assert response.status_code == 200

    async def test_resolves_user_from_attribute_auth_service(self, tmp_path):
        app = mount_auth(tmp_path)
        app.bind("auth", SimpleNamespace(user=SimpleNamespace(id=2)))
        handler = auth_handler(app)
        response = await handler(FakeRequest("application/json", json_body={"channel_name": "orders"}))
        assert response.status_code == 200


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
        # No routes/channels.py — boot must still succeed.
        app = make_app(tmp_path)
        assert isinstance(app.make("broadcasting"), BroadcastManager)


class _RaisingFastapiApp:
    """Minimal app whose ``.fastapi`` raises, mimicking FastAPI not installed."""

    base_path = "/nonexistent-base-path"

    @property
    def fastapi(self):
        raise RuntimeError("FastAPI not available")


class TestMountingWithoutFastapi:
    def test_mount_websocket_skips_when_fastapi_unavailable(self):
        provider = ReverbProvider(_RaisingFastapiApp())
        provider._mount_websocket()  # returns without raising

    def test_mount_auth_endpoint_skips_when_fastapi_unavailable(self):
        provider = ReverbProvider(_RaisingFastapiApp())
        provider._mount_auth_endpoint()  # returns without raising

    def test_load_channels_file_skips_when_absent(self):
        provider = ReverbProvider(_RaisingFastapiApp())
        provider._load_channels_file()  # base_path has no routes/channels.py
