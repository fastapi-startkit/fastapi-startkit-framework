"""Type stub for the Broadcast facade.

Provides IDE auto-complete and static-analysis support.  At runtime the
``Broadcast`` class uses the :class:`~fastapi_startkit.facades.Facade` metaclass
to proxy every attribute access to the ``Broadcaster`` instance bound under
the ``"broadcast"`` key in the service container.
"""

from __future__ import annotations

from typing import Callable

from fastapi_startkit.reverb.channels import Channel, PresenceChannel, PrivateChannel
from fastapi_startkit.reverb.event import BroadcastEvent


class Broadcast:
    """Facade for broadcasting events over WebSocket channels via Reverb."""

    @staticmethod
    async def dispatch(event: BroadcastEvent) -> None:
        """Primary dispatch path — broadcast a ``BroadcastEvent`` to every
        channel returned by its ``broadcast_on()`` method.

        Args:
            event: A ``BroadcastEvent`` instance.  ``event.name`` defaults to
                   the class name when not set explicitly.
        """
        ...

    @staticmethod
    async def emit(channel: str, event_name: str, payload: dict) -> None:
        """Escape hatch for broadcasting without a ``BroadcastEvent`` class.

        Args:
            channel:    Full channel name (e.g. ``"orders.42"``).
            event_name: Name of the event sent to subscribers.
            payload:    Arbitrary JSON-serializable dict.
        """
        ...

    @staticmethod
    def channel(pattern: str) -> Callable:
        """Decorator factory — register a channel authorization callback.

        Usage in ``routes/channels.py``::

            @Broadcast.channel("orders.{order_id}")
            async def authorize_orders(user, order_id: int) -> bool:
                return user.id == order_id

        Args:
            pattern: Channel pattern with ``{name}`` wildcards.

        Returns:
            A decorator that registers the wrapped function with the
            :class:`~fastapi_startkit.reverb.registry.ChannelAuthRegistry`.
        """
        ...
