"""Core Broadcaster — dispatches events to the Reverb WebSocket server.

The ``Broadcaster`` is bound into the container under both ``"broadcast"`` and
``"reverb"`` by :class:`~fastapi_startkit.reverb.provider.ReverbProvider`.
Access it via the ``Broadcast`` facade or resolve it directly from the
container.

Typical usage::

    # Via facade
    await Broadcast.dispatch(OrderShipped(order_id=42))
    await Broadcast.emit("orders.42", "OrderShipped", {"order_id": 42})

    # Via decorator
    @Broadcast.channel("orders.{order_id}")
    async def authorize_orders(user, order_id: int) -> bool:
        return user.id == order_id
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .event import BroadcastEvent
    from .registry import ChannelAuthRegistry
    from ..broadcasting.reverb.server import ReverbServer


class Broadcaster:
    """Dispatches broadcast events and manages channel authorization.

    Args:
        server:   The Reverb WebSocket server that delivers messages to
                  connected clients.
        registry: The :class:`~fastapi_startkit.reverb.registry.ChannelAuthRegistry`
                  that holds ``@Broadcast.channel`` callbacks.
        config:   Raw broadcasting config dict (from ``BroadcastingConfig``).
    """

    def __init__(
        self,
        server: "ReverbServer | None" = None,
        registry: "ChannelAuthRegistry | None" = None,
        config: dict | None = None,
    ) -> None:
        self._server = server
        self._registry = registry
        self._config = config or {}

    # ------------------------------------------------------------------
    # Primary dispatch path
    # ------------------------------------------------------------------

    async def dispatch(self, event: "BroadcastEvent") -> None:
        """Broadcast a :class:`~fastapi_startkit.reverb.event.BroadcastEvent`
        to every channel returned by its ``broadcast_on()`` method.

        Args:
            event: A ``BroadcastEvent`` instance.  The event name defaults to
                   ``event.__class__.__name__`` when ``event.name`` is ``None``.
        """
        if self._server is None:
            return

        channels = event.broadcast_on()
        event_name = event.name if event.name is not None else event.__class__.__name__
        payload = event.payload if isinstance(event.payload, dict) else {}

        for channel in channels:
            await self._server.broadcast_to_channel(channel.name, event_name, payload)

    # ------------------------------------------------------------------
    # Escape hatch
    # ------------------------------------------------------------------

    async def emit(self, channel: str, event_name: str, payload: dict) -> None:
        """Broadcast a raw event without wrapping it in a ``BroadcastEvent``.

        Useful for quick one-off broadcasts or dynamic channel names that
        don't warrant a dedicated event class.

        Args:
            channel:    Full channel name (e.g. ``"orders.42"``).
            event_name: Event name sent to subscribers.
            payload:    Arbitrary JSON-serializable dict.
        """
        if self._server is None:
            return
        await self._server.broadcast_to_channel(channel, event_name, payload)

    # ------------------------------------------------------------------
    # Channel authorization decorator
    # ------------------------------------------------------------------

    def channel(self, pattern: str) -> Callable:
        """Register a channel authorization callback.

        Use as a decorator in ``routes/channels.py``::

            from fastapi_startkit.facades.Broadcast import Broadcast

            @Broadcast.channel("orders.{order_id}")
            async def authorize_orders(user, order_id: int) -> bool:
                return user.id == order_id

        Args:
            pattern: Channel pattern with ``{name}`` placeholders.

        Returns:
            A decorator that registers the wrapped callable and returns it
            unchanged so it remains importable.
        """

        def decorator(callback: Callable) -> Callable:
            if self._registry is not None:
                self._registry.register(pattern, callback)
            return callback

        return decorator
