"""Application event dispatcher.

An async-aware, Laravel-style event dispatcher. Events are plain classes;
listeners are callables or classes exposing a ``handle`` method. Both sync and
coroutine listeners are supported — coroutine results are awaited transparently.
"""

import inspect
from fnmatch import fnmatchcase
from typing import TYPE_CHECKING, Any, Callable, cast, overload

if TYPE_CHECKING:
    from ..container import Container
    from .fake import EventFake


class Dispatcher:
    def __init__(self, container: "Container | None" = None):
        self._container = container
        self._listeners: dict[str, list] = {}

    @overload
    def listen(self, events, listener: None = None) -> Callable: ...

    @overload
    def listen(self, events, listener: Callable) -> None: ...

    def listen(self, events, listener: Callable | None = None):
        """Register a listener for one or more events.

        ``events`` may be an event class, a string name, or a list of either.
        String names may contain ``*`` wildcards (e.g. ``"user.*"``) — the
        listener then fires for any matching event name. Used as a decorator
        when ``listener`` is omitted.
        """
        if listener is None:

            def decorator(func: Callable) -> Callable:
                self.listen(events, func)
                return func

            return decorator

        for name in self._event_names(events):
            self._listeners.setdefault(name, []).append(listener)
        return None

    def has_listeners(self, event) -> bool:
        return bool(self._get_listeners(self._event_key(event)))

    def forget(self, event) -> None:
        """Remove all listeners registered for a given event."""
        self._listeners.pop(self._event_key(event), None)

    def flush(self) -> None:
        """Remove every registered listener."""
        self._listeners.clear()

    async def dispatch(self, event, payload=None, halt: bool = False):
        """Fire an event and call its listeners in registration order.

        Returns the list of listener responses. When ``halt`` is true, the first
        non-``None`` response is returned immediately. A listener returning
        ``False`` stops propagation to later listeners.
        """
        name, args = self._parse_event_payload(event, payload)

        responses: list[Any] = []
        for listener in self._get_listeners(name):
            response = await self._call_listener(listener, args)

            if halt and response is not None:
                return response

            if response is False:
                break

            responses.append(response)

        return None if halt else responses

    async def until(self, event, payload=None):
        """Dispatch an event, returning the first non-``None`` listener response."""
        return await self.dispatch(event, payload, halt=True)

    def fake(self, events_to_fake=None) -> "EventFake":
        """Swap the container's dispatcher for a recording fake (testing helper)."""
        from .fake import EventFake

        fake = EventFake(cast("Dispatcher", self), events_to_fake)
        if self._container is not None:
            self._container.bind("events", fake)
        return fake

    def _event_names(self, events) -> list[str]:
        items = events if isinstance(events, (list, tuple)) else [events]
        return [self._event_key(event) for event in items]

    def _get_listeners(self, name: str) -> list:
        """All listeners for an event name: exact matches first, then any
        wildcard-pattern listeners whose pattern matches the name."""
        listeners = list(self._listeners.get(name, []))
        for pattern, pattern_listeners in self._listeners.items():
            if pattern != name and "*" in pattern and fnmatchcase(name, pattern):
                listeners.extend(pattern_listeners)
        return listeners

    def _event_key(self, event) -> str:
        if isinstance(event, str):
            return event
        cls = event if inspect.isclass(event) else type(event)
        return f"{cls.__module__}.{cls.__qualname__}"

    def _parse_event_payload(self, event, payload) -> tuple[str, list]:
        if isinstance(event, str):
            if payload is None:
                args: list = []
            elif isinstance(payload, (list, tuple)):
                args = list(payload)
            else:
                args = [payload]
            return event, args

        return self._event_key(event), [event]

    async def _call_listener(self, listener: Callable, args: list):
        handler = self._resolve_listener(listener)
        result = handler(*args)
        if inspect.isawaitable(result):
            result = await result
        return result

    def _resolve_listener(self, listener: Callable) -> Callable:
        if inspect.isclass(listener):
            return self._make(listener).handle
        return listener

    def _make(self, cls):
        if self._container is not None:
            return self._container.resolve(cls)
        return cls()
