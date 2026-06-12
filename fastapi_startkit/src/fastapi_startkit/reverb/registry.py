"""Channel authorization registry.

The registry maps channel *patterns* (e.g. ``orders.{order_id}``) to async
(or sync) authorization callbacks.  At subscription time the framework:

1. Strips the ``private-``/``presence-`` prefix from the inbound channel name.
2. Iterates registered patterns and tries to match the stripped name against
   each compiled regex.
3. On a match, extracts wildcard values, casts them to the callback's
   declared type hints, then calls the callback with the authenticated user
   and the extracted wildcards.
4. Returns ``True`` (authorized) or ``False`` (denied).

Default behaviour when *no* pattern matches:

- ``private-*`` / ``presence-*`` channels → **denied**.
- Public channels → **allowed**.
"""

from __future__ import annotations

import inspect
import re
from typing import Any, Callable, get_type_hints


class ChannelAuthRegistry:
    """Registry for ``@Broadcast.channel`` authorization callbacks."""

    def __init__(self) -> None:
        # Each entry: (raw_pattern, compiled_regex, callback)
        self._callbacks: list[tuple[str, re.Pattern[str], Callable[..., Any]]] = []

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, pattern: str, callback: Callable[..., Any]) -> None:
        """Register *callback* for *pattern*.

        Args:
            pattern:  Channel pattern with ``{name}`` placeholders, e.g.
                      ``"orders.{order_id}"`` or ``"chat.{room}.{topic}"``.
            callback: Sync or async callable.  Its first positional parameter
                      receives the authenticated user; subsequent keyword
                      arguments receive the wildcard values cast to their
                      declared type hints.
        """
        compiled = self._compile_pattern(pattern)
        self._callbacks.append((pattern, compiled, callback))

    # ------------------------------------------------------------------
    # Authorization
    # ------------------------------------------------------------------

    async def authorize(self, channel_name: str, user: Any) -> bool:
        """Authorize *user* for *channel_name*.

        Args:
            channel_name: Full channel name as sent by the client, e.g.
                          ``"private-orders.42"`` or ``"orders.42"``.
            user:         Authenticated user object (may be ``None`` for
                          unauthenticated requests).

        Returns:
            ``True`` if authorized, ``False`` otherwise.
        """
        raw_name = self._strip_prefix(channel_name)

        for _pattern, compiled, callback in self._callbacks:
            # Try stripped name first, fall back to full name
            match = compiled.match(raw_name) or compiled.match(channel_name)
            if match is None:
                continue

            wildcards = match.groupdict()
            kwargs = self._cast_wildcards(callback, wildcards)

            if inspect.iscoroutinefunction(callback):
                result = await callback(user, **kwargs)
            else:
                result = callback(user, **kwargs)

            return bool(result)

        # Default policy
        if channel_name.startswith(("private-", "presence-")):
            return False
        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_prefix(channel_name: str) -> str:
        """Remove ``private-`` or ``presence-`` prefix for pattern matching."""
        for prefix in ("private-", "presence-"):
            if channel_name.startswith(prefix):
                return channel_name[len(prefix):]
        return channel_name

    @staticmethod
    def _compile_pattern(pattern: str) -> re.Pattern[str]:
        """Convert ``orders.{order_id}`` to a named-group regex.

        Dots outside wildcards are treated as literal dots (not regex ``.``).
        Each ``{name}`` wildcard matches one or more characters that are not
        a literal dot, giving fine-grained segment-level matching.
        """
        # Split on {name} tokens preserving the delimiters
        parts = re.split(r"(\{[^}]+\})", pattern)
        regex_parts: list[str] = []
        for part in parts:
            if part.startswith("{") and part.endswith("}"):
                wildcard_name = part[1:-1]
                regex_parts.append(f"(?P<{wildcard_name}>[^.]+)")
            else:
                regex_parts.append(re.escape(part))
        return re.compile(f'^{"".join(regex_parts)}$')

    @staticmethod
    def _cast_wildcards(
        callback: Callable[..., Any],
        wildcards: dict[str, str],
    ) -> dict[str, Any]:
        """Cast wildcard strings to the types declared in *callback*'s hints."""
        try:
            hints = get_type_hints(callback)
        except Exception:
            hints = {}

        casted: dict[str, Any] = {}
        for key, raw_val in wildcards.items():
            if key in hints:
                target_type = hints[key]
                try:
                    casted[key] = target_type(raw_val)
                except (ValueError, TypeError):
                    casted[key] = raw_val
            else:
                casted[key] = raw_val
        return casted
