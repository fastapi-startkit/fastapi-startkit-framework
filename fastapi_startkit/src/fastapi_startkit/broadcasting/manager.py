from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .auth import ChannelAuthRegistry

if TYPE_CHECKING:
    from .event import BroadcastEvent


class BroadcastManager:
    """Central broadcast manager.

    Holds the active driver, the Reverb server instance (if any), and the
    :class:`~.auth.ChannelAuthRegistry` used by the ``/broadcasting/auth``
    endpoint.

    This is the service that the :class:`~fastapi_startkit.facades.Broadcast`
    facade proxies to (container key: ``"broadcasting"``).
    """

    def __init__(self, config: dict, server: Any = None) -> None:
        self._config = config
        self._server = server
        self.channel_registry = ChannelAuthRegistry()

    # ------------------------------------------------------------------
    # Driver resolution
    # ------------------------------------------------------------------

    def driver(self, name: str | None = None):
        name = name or self._config.get("default", "log")
        if name == "log":
            from .drivers.log_driver import LogDriver

            return LogDriver()
        elif name == "reverb":
            from .drivers.reverb_driver import ReverbDriver

            return ReverbDriver(self._server)
        raise ValueError(f"Unknown broadcast driver: {name}")

    # ------------------------------------------------------------------
    # Dispatch helpers
    # ------------------------------------------------------------------

    async def event(self, broadcast_event: "BroadcastEvent") -> None:
        """Broadcast *broadcast_event* using the default driver.

        .. deprecated::
            Prefer :meth:`dispatch` for new code.
        """
        await self.driver().broadcast(broadcast_event)

    async def dispatch(self, broadcast_event: "BroadcastEvent") -> None:
        """Primary dispatch path.

        Sends *broadcast_event* to all channels returned by its
        ``broadcast_on()`` method via the configured driver.
        """
        await self.driver().broadcast(broadcast_event)

    async def emit(self, channel: str, event_name: str, payload: dict) -> None:
        """Escape-hatch for direct / dynamic broadcasts.

        Sends *payload* as *event_name* to *channel* without needing a
        ``BroadcastEvent`` subclass.
        """
        driver_name = self._config.get("default", "log")
        if driver_name == "reverb" and self._server is not None:
            await self._server.broadcast_to_channel(channel, event_name, payload)
        else:
            # Log driver fallback
            from .drivers.log_driver import LogDriver

            driver = LogDriver()
            await driver.broadcast_raw(channel, event_name, payload)

    # ------------------------------------------------------------------
    # Channel authorization registry proxy
    # ------------------------------------------------------------------

    def channel(self, pattern: str):
        """Decorator factory — register a channel authorization callback.

        Example::

            Broadcast.channel("orders.{order_id}")
            async def authorize(user, order_id: int):
                return user.id == order_id

        Delegates to :attr:`channel_registry`.
        """
        return self.channel_registry.channel(pattern)
