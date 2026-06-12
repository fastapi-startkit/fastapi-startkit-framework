from collections.abc import Callable

from ..application import app


async def broadcast(event) -> None:
    """Broadcast an event using the default driver."""
    manager = app().make("broadcasting")
    await manager.event(event)


def channel(pattern: str) -> Callable:
    """Register a channel authorization callback.

    A decorator factory that registers the decorated function with the
    ``ChannelAuthRegistry`` on the booted ``BroadcastManager``.

    Usage::

        from fastapi_startkit.broadcasting import channel

        @channel("orders.{order_id}")
        async def authorize_orders(user, order_id: int) -> bool:
            return user is not None and user.id == order_id

        @channel("private-notifications")
        async def authorize_notifications(user) -> bool:
            return user is not None

    Pattern supports ``{wildcard}`` placeholders; wildcard values are cast to
    the type-hints of the matching callback parameters before calling.
    """

    def decorator(func: Callable) -> Callable:
        manager = app().make("broadcasting")
        manager.channel_registry.register(pattern, func)
        return func

    return decorator
