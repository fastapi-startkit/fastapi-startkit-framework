from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

from fastapi_startkit.support import Provider
from .config import BroadcastingConfig
from .manager import BroadcastManager
from .reverb.server import ReverbServer


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

        server = ReverbServer()
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
        """Mount the Reverb WebSocket endpoint on the FastAPI application.

        The endpoint path is ``/app/{app_key}``, matching the Pusher protocol
        expected by Laravel Echo.  The ``app_key`` is taken from the
        ``reverb.connections.reverb.key`` config value (default: ``"local"``).
        """
        try:
            fastapi_app = self.app.fastapi
        except RuntimeError:
            # FastAPI not installed or app not yet booted — skip
            return

        config = self.app.make("config").get("broadcasting") or {}
        connections = config.get("connections", {}) if isinstance(config, dict) else {}
        reverb_conn = connections.get("reverb", {}) if isinstance(connections, dict) else {}
        app_key = reverb_conn.get("key", "local") if isinstance(reverb_conn, dict) else "local"

        server: ReverbServer = self.app.make("reverb.server")

        from starlette.routing import WebSocketRoute
        from starlette.applications import Starlette

        async def ws_endpoint(websocket):
            await server.handle(websocket)

        ws_app = Starlette(routes=[WebSocketRoute(f"/app/{app_key}", ws_endpoint)])
        fastapi_app.mount("", ws_app)

    def _mount_auth_endpoint(self) -> None:
        """Mount the ``/broadcasting/auth`` HTTP endpoint.

        The endpoint handles the Laravel Echo authentication handshake for
        private and presence channels.  It:

        1. Reads ``channel_name`` from the POST body (form or JSON).
        2. Resolves the current user via the container's ``auth`` binding (if
           available), falling back to ``request.state.user``.
        3. Calls :meth:`~.auth.ChannelAuthRegistry.authorize` with the channel
           name and the resolved user.
        4. Returns **200** on success or **403** on denial.
        """
        try:
            fastapi_app = self.app.fastapi
        except RuntimeError:
            return

        from fastapi import Request
        from fastapi.responses import JSONResponse

        application = self.app

        @fastapi_app.post("/broadcasting/auth")
        async def broadcasting_auth(request: Request):
            # Resolve channel name from form data or JSON body
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                body = await request.json()
                channel_name = body.get("channel_name", "")
            else:
                form = await request.form()
                channel_name = form.get("channel_name", "")

            # Resolve authenticated user.
            # Prefer request.state.user (set by auth middleware), then fall
            # back to the container's "auth" service.
            user = getattr(request.state, "user", None)
            if user is None:
                try:
                    auth_service = application.make("auth")
                    user_attr = getattr(auth_service, "user", None)
                    if callable(user_attr):
                        user = user_attr()
                    else:
                        user = user_attr
                except Exception:
                    user = None

            # Authorise
            manager: BroadcastManager = application.make("broadcasting")
            allowed = await manager.channel_registry.authorize(channel_name, user)

            if not allowed:
                return JSONResponse({"error": "Forbidden"}, status_code=403)

            return JSONResponse({"auth": True, "channel_data": {}})
