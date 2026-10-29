from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from collections.abc import Mapping
from pathlib import Path

from fastapi_startkit.support import Provider
from .config import BroadcastingConfig
from .manager import BroadcastManager
from .reverb.server import ReverbServer
from .reverb.signature import is_presence, requires_auth, sign, valid_channel, valid_socket_id

UNSAFE_SECRETS = ("", "secret")
INSECURE_ENVIRONMENTS = ("local", "testing")


class ReverbProvider(Provider):
    """Service provider that wires up the Reverb broadcasting stack.

    Registering ``ReverbProvider`` in the providers list is the **only** thing
    a user needs to do to get broadcasting working.  The provider:

    * Binds a :class:`~.manager.BroadcastManager` and a
      :class:`~.reverb.server.ReverbServer` into the container.
    * Mounts the Pusher-protocol WebSocket endpoint on the FastAPI app.
    * Mounts a ``/broadcasting/auth`` HTTP endpoint for private/presence
      channel authorisation (Laravel Echo handshake).
    * Auto-loads ``routes/channels.py`` from the application base path so
      ``@Broadcast.channel()`` decorators in that file are registered before
      any subscription is attempted.

    Configuration is read from environment variables — see
    :class:`~.config.BroadcastingConfig` for the full list.
    """

    provider_key = "broadcasting"

    def register(self) -> None:
        config_data = self.resolve_config(BroadcastingConfig)
        self.merge_config_from(config_data, "broadcasting")

        reverb = config_data.get("connections", {}).get("reverb", {})
        secret = reverb.get("secret") or ""
        if secret in UNSAFE_SECRETS and self.app.env not in INSECURE_ENVIRONMENTS:
            raise RuntimeError(
                f"REVERB_APP_SECRET must be set to a private value when APP_ENV is {self.app.env!r}; "
                "private and presence channel signatures would otherwise be forgeable."
            )
        server = ReverbServer(key=reverb.get("key", "local"), secret=secret)
        manager = BroadcastManager(config_data, server)

        self.app.bind("broadcasting", manager)
        self.app.bind("reverb.server", server)

    def boot(self) -> None:
        import os

        # Publish the channels.py stub so developers can scaffold it
        stub_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "stubs/channels.py"))
        self.publishes({stub_src: "routes/channels.py"})

        self._load_channels_file()
        self._mount_websocket()
        self._mount_auth_endpoint()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_channels_file(self) -> None:
        """Auto-load ``routes/channels.py`` from the application base path.

        This is the file developers fill in with ``@channel()`` decorators
        (imported from ``fastapi_startkit.broadcasting``).  Importing it
        registers the callbacks with the ``ChannelAuthRegistry`` on the
        ``BroadcastManager``.

        The file is optional — its absence is silently ignored.
        """
        channels_path = Path(self.app.base_path) / "routes" / "channels.py"
        if not channels_path.exists():
            return

        module_name = "app.routes.channels"
        spec = importlib.util.spec_from_file_location(module_name, str(channels_path))
        if spec is None or spec.loader is None:
            return

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)  # type: ignore[union-attr]

    def _mount_websocket(self) -> None:
        try:
            fastapi_app = self.app.fastapi
        except RuntimeError:
            return

        server: ReverbServer = self.app.make("reverb.server")

        async def ws_endpoint(websocket):
            await server.handle(websocket)

        fastapi_app.router.add_websocket_route(f"/app/{server.key}", ws_endpoint)

    def _mount_auth_endpoint(self) -> None:
        try:
            fastapi_app = self.app.fastapi
        except RuntimeError:
            return

        from starlette.requests import Request
        from starlette.responses import JSONResponse

        application = self.app

        async def broadcasting_auth(request: Request):
            if "application/json" in request.headers.get("content-type", ""):
                try:
                    body = await request.json()
                except ValueError:
                    return JSONResponse({"error": "Malformed JSON body"}, status_code=400)
            else:
                body = await request.form()
            if not isinstance(body, Mapping):
                return JSONResponse({"error": "Request body must be an object"}, status_code=422)

            channel_name = body.get("channel_name", "")
            socket_id = body.get("socket_id", "")
            if not valid_socket_id(socket_id):
                return JSONResponse({"error": "socket_id is invalid"}, status_code=422)
            if not valid_channel(channel_name):
                return JSONResponse({"error": "channel_name is invalid"}, status_code=422)

            server: ReverbServer = application.make("reverb.server")
            user = self._resolve_user(application, request)
            if not server.secret or not requires_auth(channel_name) or user is None:
                return JSONResponse({"error": "Forbidden"}, status_code=403)

            manager: BroadcastManager = application.make("broadcasting")
            if not await manager.channel_registry.authorize(channel_name, user):
                return JSONResponse({"error": "Forbidden"}, status_code=403)

            if not is_presence(channel_name):
                return JSONResponse({"auth": sign(server.key, server.secret, socket_id, channel_name)})

            user_id = getattr(user, "id", None)
            if user_id is None:
                return JSONResponse({"error": "Forbidden"}, status_code=403)
            channel_data = json.dumps({"user_id": str(user_id)})
            auth = sign(server.key, server.secret, socket_id, channel_name, channel_data)
            return JSONResponse({"auth": auth, "channel_data": channel_data})

        fastapi_app.router.add_route("/broadcasting/auth", broadcasting_auth, methods=["POST"])

    @staticmethod
    def _resolve_user(application, request):
        user = getattr(request.state, "user", None)
        if user is not None:
            return user
        try:
            user_attr = getattr(application.make("auth"), "user", None)
        except Exception:
            return None
        return user_attr() if callable(user_attr) else user_attr
