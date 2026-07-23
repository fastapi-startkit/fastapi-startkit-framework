"""Channel authorization registry for the Reverb broadcasting module.

Usage::

    from fastapi_startkit.broadcasting import channel

    @channel("orders.{order_id}")
    async def authorize_orders_channel(user, order_id: int):
        return user.id == order_id  # True = authorized, False = denied

The registry is held on the ``BroadcastManager`` instance that lives in the
container.  ``ReverbProvider`` mounts the ``/broadcasting/auth`` endpoint
which calls :meth:`ChannelAuthRegistry.authorize` to verify subscriptions.
"""

from __future__ import annotations

import inspect
import re
from collections.abc import Callable
from typing import Any


def _pattern_to_regex(pattern: str) -> re.Pattern:
    """Convert a ``{wildcard}``-style pattern to a compiled regex.

    Example: ``"orders.{order_id}"`` -> ``^orders\\.(?P<order_id>[^.]+)$``
    """
    # Escape everything except our placeholder tokens
    parts = re.split(r"(\{[^}]+\})", pattern)
    regex_parts: list[str] = []
    for part in parts:
        if part.startswith("{") and part.endswith("}"):
            name = part[1:-1]
            regex_parts.append(f"(?P<{name}>[^.]+)")
        else:
            regex_parts.append(re.escape(part))
    return re.compile("^" + "".join(regex_parts) + "$")


class ChannelAuthRegistry:
    """Stores and evaluates channel authorization callbacks."""

    def __init__(self) -> None:
        # List of (compiled_pattern, original_pattern, callback)
        self._rules: list[tuple[re.Pattern, str, Callable]] = []

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, pattern: str, callback: Callable) -> None:
        """Register *callback* as the authorizer for channels matching *pattern*."""
        self._rules.append((_pattern_to_regex(pattern), pattern, callback))

    def channel(self, pattern: str) -> Callable:
        """Decorator factory — registers the decorated function for *pattern*.

        Example::

            @registry.channel("orders.{order_id}")
            async def authorize(user, order_id: int):
                return user.id == order_id
        """

        def decorator(func: Callable) -> Callable:
            self.register(pattern, func)
            return func

        return decorator

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def _find(self, channel_name: str) -> tuple[Callable, dict[str, str]] | None:
        """Return ``(callback, wildcard_kwargs)`` for *channel_name*, or ``None``."""
        for compiled, _pattern, callback in self._rules:
            m = compiled.match(channel_name)
            if m:
                return callback, m.groupdict()
        return None

    # ------------------------------------------------------------------
    # Authorization
    # ------------------------------------------------------------------

    async def authorize(self, channel_name: str, user: Any) -> bool:
        """Evaluate the authorization callback for *channel_name*.

        * Public channels (no ``private-`` / ``presence-`` prefix): always
          allowed, no callback needed.
        * Private / presence channels without a registered callback: **denied**
          by default (fail-safe).
        * Private / presence channels with a registered callback: the return
          value of the callback determines access.

        Wildcard values extracted from the pattern are cast to the type hints
        of the matching parameters before the callback is called.
        """

        is_private = channel_name.startswith("private-") or channel_name.startswith("presence-")

        result = self._find(channel_name)

        # Public channel with no rule → allow
        if result is None and not is_private:
            return True

        # Private/presence channel with no rule → deny
        if result is None:
            return False

        callback, raw_kwargs = result

        # Cast wildcard values to the declared type hints of the callback
        hints = {}
        try:
            sig = inspect.signature(callback)
            hints = {
                k: p.annotation
                for k, p in sig.parameters.items()
                if p.annotation is not inspect.Parameter.empty and k != "user"
            }
        except (ValueError, TypeError):
            pass

        cast_kwargs: dict[str, Any] = {}
        for k, v in raw_kwargs.items():
            try:
                cast_kwargs[k] = hints[k](v) if k in hints else v
            except (ValueError, TypeError):
                cast_kwargs[k] = v

        # Call the callback (sync or async)
        result_value = callback(user, **cast_kwargs)
        if inspect.isawaitable(result_value):
            result_value = await result_value

        return bool(result_value)
