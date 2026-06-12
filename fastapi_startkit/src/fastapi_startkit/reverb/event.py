"""BroadcastEvent base class.

Subclass ``BroadcastEvent`` to create broadcastable events::

    class OrderShipped(BroadcastEvent):
        def __init__(self, order_id: int) -> None:
            self.payload = {"order_id": order_id}

        def broadcast_on(self):
            return [PrivateChannel(f"orders.{self.order_id}")]

    # Broadcast synchronously from a FastAPI endpoint:
    await OrderShipped(order_id=42).emit()

    # Or dispatch via the facade:
    await Broadcast.dispatch(OrderShipped(order_id=42))
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Union

from .channels import Channel, PresenceChannel, PrivateChannel


class BroadcastEvent(ABC):
    """Abstract base for all broadcastable events.

    Subclasses **must** implement :meth:`broadcast_on`.  ``payload`` and
    ``name`` are intentionally class-level defaults so users can override
    them either as class attributes *or* in ``__init__``.
    """

    #: Data payload forwarded to subscribers.  Override per-instance in
    #: ``__init__`` or as a class attribute.
    payload: dict = {}

    #: Event name sent over the wire.  Defaults to the class name when
    #: ``None`` so that renaming the Python class also renames the event.
    name: str | None = None

    @abstractmethod
    def broadcast_on(self) -> list[Union[Channel, PrivateChannel, PresenceChannel]]:
        """Return the channels this event should be broadcast on.

        Must be overridden by every concrete subclass.
        """
        ...

    async def emit(self) -> None:
        """Convenience shortcut — delegates to ``Broadcast.dispatch(self)``.

        Because ``dispatch`` is a coroutine, ``emit`` must be awaited::

            await OrderShipped(order_id=42).emit()
        """
        from fastapi_startkit.facades.Broadcast import Broadcast

        await Broadcast.dispatch(self)
