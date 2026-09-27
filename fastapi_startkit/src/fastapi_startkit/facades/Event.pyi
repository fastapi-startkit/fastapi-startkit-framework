from typing import Any, Callable

from fastapi_startkit.events.fake import EventFake

class Event:
    """Facade for the event dispatcher registered under the 'events' key."""

    @staticmethod
    def listen(events: Any, listener: Callable | None = None) -> Callable | None:
        """Register a listener for one or more events (or use as a decorator)."""
        ...

    @staticmethod
    async def dispatch(event: Any, payload: Any = None, halt: bool = False) -> Any:
        """Fire an event and invoke its listeners; returns their responses."""
        ...

    @staticmethod
    async def until(event: Any, payload: Any = None) -> Any:
        """Dispatch an event, returning the first non-None listener response."""
        ...

    @staticmethod
    def has_listeners(event: Any) -> bool:
        """Return whether any listener is registered for the event."""
        ...

    @staticmethod
    def forget(event: Any) -> None:
        """Remove all listeners registered for the event."""
        ...

    @staticmethod
    def flush() -> None:
        """Remove every registered listener."""
        ...

    @staticmethod
    def fake(events_to_fake: Any = None) -> EventFake:
        """Swap the dispatcher for a recording fake and return it."""
        ...
