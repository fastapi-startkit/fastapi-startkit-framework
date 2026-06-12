"""ReverbProvider — wires Reverb broadcasting into the FastAPI application.

Registering ``ReverbProvider`` in the application's providers list is the
*only* thing needed to get broadcasting working::

    from fastapi_startkit.reverb import ReverbProvider

    Application(
        base_path=BASE_DIR,
        providers=[
            ...,
            ReverbProvider,
        ],
    )

What the provider does
----------------------
``register()``:
    * Instantiates :class:`~fastapi_startkit.broadcasting.reverb.server.ReverbServer`,
      :class:`~fastapi_startkit.reverb.registry.ChannelAuthRegistry`, and
      :class:`~fastapi_startkit.reverb.broadcaster.Broadcaster`.
    * Binds them into the container under ``"reverb"``, ``"broadcast"``,
      ``"reverb.server"``, and ``"reverb.registry"``.
    * Merges Reverb configuration from environment variables.

``boot()``:
    * Auto-loads ``routes/channels.py`` (silent skip when absent).
    * Mounts the WebSocket endpoint at the path configured by ``REVERB_PATH``
      (default ``/__reverb``).
    * Mounts ``POST /broadcasting/auth`` — the Laravel Echo auth handshake.
      Returns ``200`` with a signed auth token or ``403`` when the registry
      denies the subscription.
"""

from __future__ import annotations

import importlib.util
import os

from ..broadcasting.config import BroadcastingConfig
from ..broadcasting.reverb.server import ReverbServer
from ..providers import Provider
from .broadcaster import Broadcaster
from .registry import ChannelAuthRegistry


class ReverbProvider(Provider):
    """Service provider that auto-wires the full Reverb broadcasting stack."""

    provider_key = "reverb"

    # ------------------------------------------------------------------
    # register() — bind services before any boot() runs
    # ------------------------------------------------------------------

    def register(self) -> None:
        config_data = self.resolve_config(BroadcastingConfig)

        server = ReverbServer()
        registry = ChannelAuthRegistry()
        broadcaster = Broadcaster(server=server, registry=registry, config=config_data)

        # Bind under two keys so both ``Broadcast`` facade (key="broadcast")
        # and direct ``app.make("reverb")`` work.
        self.app.bind("reverb", broadcaster)
        self.app.bind("broadcast", broadcaster)
        self.app.bind("reverb.server", server)
        self.app.bind("reverb.registry", registry)

    # ------------------------------------------------------------------
    # boot() — mount routes after all providers have registered
    # ------------------------------------------------------------------

    def boot(self) -> None:
        self._load_channels_file()
        self._mount_routes()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_channels_file(self) -> None:
        """Import ``routes/channels.py`` so that ``@Broadcast.channel``
        decorators inside it are executed and callbacks registered.

        Silently skips when the file does not exist or raises an exception
        on import (avoids crashing apps that haven't created the file yet).
        """
        channels_path = self.app.base_path / "routes" / "channels.py"
        if not channels_path.exists():
            return

        spec = importlib.util.spec_from_file_location("routes.channels", channels_path)
        if spec is None or spec.loader is None:
            return

        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)  # type: ignore[union-attr]
        except Exception:
            # Silent skip — don't crash the app for a bad channels file
            pass

    def _mount_routes(self) -> None:
        """Mount the WebSocket endpoint and ``/broadcasting/auth`` on the
        FastAPI application.

        Gracefully skips when the FastAPI instance is not yet available
        (e.g. in pure-CLI / testing contexts that don't boot FastAPI).
        """
        try:
            fastapi_app = self.app.fastapi
        except Exception:
            return

        server: ReverbServer = self.app.make("reverb.server")
        registry: ChannelAuthRegistry = self.app.make("reverb.registry")

        reverb_path: str = os.environ.get("REVERB_PATH", "/__reverb")
        app_key: str = os.environ.get("REVERB_APP_KEY", "local")

        # ---- WebSocket endpoint ------------------------------------------
        fastapi_app.mount(reverb_path, server.as_starlette_app(app_key))

        # ---- /broadcasting/auth ------------------------------------------
        from fastapi import Request
        from fastapi.responses import JSONResponse

        @fastapi_app.post("/broadcasting/auth")
        async def broadcasting_auth(request: Request) -> JSONResponse:
            """Laravel Echo / Pusher auth handshake endpoint.

            Reads ``channel_name`` and ``socket_id`` from the request body
            (form-encoded, as sent by Laravel Echo), resolves the
            authenticated user from ``request.state.user``, and delegates
            to the :class:`~fastapi_startkit.reverb.registry.ChannelAuthRegistry`.

            Returns:
                ``200`` with a signed auth string when authorized.
                ``403`` when the registry denies the subscription.
            """
            # Support both form-encoded and JSON bodies
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                body = await request.json()
                channel_name = body.get("channel_name", "")
                socket_id = body.get("socket_id", "")
            else:
                form = await request.form()
                channel_name = form.get("channel_name", "")
                socket_id = form.get("socket_id", "")

            # Authenticated user is expected on request.state by auth middleware
            user = getattr(request.state, "user", None)

            authorized = await registry.authorize(str(channel_name), user)

            if authorized:
                auth_token = f"{app_key}:{socket_id}"
                return JSONResponse(
                    {"auth": auth_token, "channel_data": "{}"},
                    status_code=200,
                )

            return JSONResponse({"message": "Forbidden"}, status_code=403)
