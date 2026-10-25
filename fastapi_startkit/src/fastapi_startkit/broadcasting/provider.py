from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from pathlib import Path

from fastapi_startkit.support import Provider
from .config import BroadcastingConfig
from .manager import BroadcastManager
from .reverb.server import ReverbServer
from .reverb.signature import sign


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
        server = ReverbServer(key=reverb.get("key", "local"), secret=reverb.get("secret", "secret"))
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
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                body = await request.json()
            else:
                body = await request.form()
            channel_name = body.get("channel_name", "")
            socket_id = body.get("socket_id", "")

            if not isinstance(channel_name, str) or not isinstance(socket_id, str):
                return JSONResponse({"error": "channel_name and socket_id must be strings"}, status_code=422)
            if not socket_id:
                return JSONResponse({"error": "socket_id is required"}, status_code=422)

            user = self._resolve_user(application, request)

            manager: BroadcastManager = application.make("broadcasting")
            if not await manager.channel_registry.authorize(channel_name, user):
                return JSONResponse({"error": "Forbidden"}, status_code=403)

            server: ReverbServer = application.make("reverb.server")
            if not channel_name.startswith("presence-"):
                return JSONResponse({"auth": sign(server.key, server.secret, socket_id, channel_name)})

            channel_data = json.dumps({"user_id": str(getattr(user, "id", ""))})
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
