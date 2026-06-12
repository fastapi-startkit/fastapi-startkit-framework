from .Facade import Facade


class Broadcast(metaclass=Facade):
    """Facade for the BroadcastManager (container key: ``"broadcasting"``).

    Proxies attribute access to the ``BroadcastManager`` instance registered
    in the service container.

    Public API (type-hinted in ``Broadcast.pyi``)::

        # Dispatch a BroadcastEvent
        await Broadcast.dispatch(event)

        # Fire-and-forget helper
        await Broadcast.emit("orders.1", "OrderShipped", {"order_id": 1})

        # Register a channel authorization callback (decorator)
        @Broadcast.channel("orders.{order_id}")
        async def authorize(user, order_id: int):
            return user.id == order_id
    """

    key = "broadcasting"
