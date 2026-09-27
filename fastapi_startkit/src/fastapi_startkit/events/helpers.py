"""Global ``event()`` helper mirroring Laravel's event helper."""

from typing import cast

from .dispatcher import Dispatcher


def event(event, payload=None, halt: bool = False):
    """Dispatch an event through the container's dispatcher.

    Returns the awaitable produced by ``Dispatcher.dispatch`` — callers should
    ``await`` it::

        await event(OrderShipped(order))
    """
    from ..application import app

    dispatcher = cast(Dispatcher, app().make("events"))
    return dispatcher.dispatch(event, payload, halt)
