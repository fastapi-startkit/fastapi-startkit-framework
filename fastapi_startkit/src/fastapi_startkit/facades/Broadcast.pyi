from collections.abc import Callable, Coroutine
from typing import Any

from fastapi_startkit.broadcasting.event import BroadcastEvent


class Broadcast:
    """Facade for broadcasting events over WebSocket channels.

    All methods proxy to the ``BroadcastManager`` instance registered in the
    service container under the key ``"broadcasting"``.
    """

    # ------------------------------------------------------------------
    # Dispatch helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def dispatch(event: BroadcastEvent) -> None:
        """Primary dispatch path.

        Sends *event* to every channel returned by its ``broadcast_on()``
        method via the configured broadcast driver.
        """
        ...

    @staticmethod
    async def emit(channel: str, event_name: str, payload: dict) -> None:
        """Escape-hatch for dynamic / ad-hoc broadcasts.

        Sends *payload* as *event_name* directly to *channel* without
        requiring a ``BroadcastEvent`` subclass.
        """
        ...

    @staticmethod
    async def event(event: BroadcastEvent) -> None:
        """Broadcast *event* using the default driver.

        .. deprecated::
            Prefer :meth:`dispatch` for new code.
        """
        ...

    # ------------------------------------------------------------------
    # Channel authorization registry
    # ------------------------------------------------------------------

    @staticmethod
    def channel(pattern: str) -> Callable[[Callable], Callable]:
        """Decorator factory — register a channel authorization callback.

        Pattern supports ``{wildcard}`` placeholders::

            @Broadcast.channel("orders.{order_id}")
            async def authorize(user, order_id: int) -> bool:
                return user.id == order_id

        * The ``user`` argument is the currently-authenticated user, injected
          automatically by the ``/broadcasting/auth`` endpoint.
        * Additional arguments correspond to wildcards in *pattern* and are
          cast to the declared type hints before the callback is called.
        * Async callbacks are supported.
        * Default (no registered callback): **denied** for private/presence
          channels; **allowed** for public channels.
        """
        ...
