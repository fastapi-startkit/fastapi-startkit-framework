"""Reverb broadcasting module.

Provides a Laravel-style broadcasting API for FastAPI applications:

- :class:`.Channel` / :class:`.PrivateChannel` / :class:`.PresenceChannel` —
  channel type declarations.
- :class:`.BroadcastEvent` — base class for broadcastable events.
- :class:`.ChannelAuthRegistry` — pattern-based authorization registry.
- :class:`.Broadcaster` — core dispatcher (bound as ``"broadcast"`` in the
  service container).
- :class:`.ReverbProvider` — service provider that auto-wires everything.

Typical usage
-------------
1. Register ``ReverbProvider`` in your application providers.
2. Create ``routes/channels.py`` with ``@Broadcast.channel(...)`` callbacks.
3. Create event classes that extend ``BroadcastEvent`` and implement
   ``broadcast_on()``.
4. Call ``await event.emit()`` or ``await Broadcast.dispatch(event)`` to
   send events to connected clients.
"""

from .broadcaster import Broadcaster
from .channels import Channel, PresenceChannel, PrivateChannel
from .event import BroadcastEvent
from .provider import ReverbProvider
from .registry import ChannelAuthRegistry

__all__ = [
    "Channel",
    "PrivateChannel",
    "PresenceChannel",
    "BroadcastEvent",
    "ChannelAuthRegistry",
    "Broadcaster",
    "ReverbProvider",
]
