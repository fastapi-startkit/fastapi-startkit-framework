"""Channel types for Reverb broadcasting.

Three channel types control authorization behaviour:

- ``Channel``        — public, no authorization check required.
- ``PrivateChannel`` — authorization is checked via a ``@Broadcast.channel``
                        callback before a subscription is accepted.
- ``PresenceChannel``— authorization is checked *and* member tracking is
                        available (tracking is a v2 concern, but the class
                        must exist for the API to be forward-compatible).
"""

from __future__ import annotations


class Channel:
    """Public channel — subscriptions accepted without any auth check."""

    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.name!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Channel) and self.name == other.name

    def __hash__(self) -> int:
        return hash((self.__class__.__name__, self.name))


class PrivateChannel(Channel):
    """Private channel — authorization checked via ``@Broadcast.channel``
    callback before any subscription is accepted.

    The channel name is automatically prefixed with ``private-`` to match
    the Pusher/Laravel Echo protocol convention.
    """

    def __init__(self, name: str) -> None:
        self._raw_name = name
        super().__init__(f"private-{name}")


class PresenceChannel(Channel):
    """Presence channel — authorization checked, member tracking available.

    The channel name is automatically prefixed with ``presence-`` to match
    the Pusher/Laravel Echo protocol convention.  Full member-tracking is a
    v2 feature; the class exists now so the public API is stable.
    """

    def __init__(self, name: str) -> None:
        self._raw_name = name
        super().__init__(f"presence-{name}")
