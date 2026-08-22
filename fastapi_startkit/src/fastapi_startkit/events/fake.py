"""A recording fake dispatcher used by ``Event.fake()`` in tests.

Faked events are captured instead of dispatched to their listeners; any event
not in the fake list is forwarded to the real dispatcher. The recorded events
can then be asserted against.
"""

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .dispatcher import Dispatcher


class EventFake:
    def __init__(self, dispatcher: "Dispatcher", events_to_fake=None):
        self._dispatcher = dispatcher
        self._events_to_fake = self._normalize(events_to_fake)
        self._dispatched: dict[str, list] = {}

    async def dispatch(self, event, payload=None, halt: bool = False):
        name, args = self._dispatcher._parse_event_payload(event, payload)

        if self._should_fake(name):
            recorded = args if isinstance(event, str) else event
            self._dispatched.setdefault(name, []).append(recorded)
            return None if halt else []

        return await self._dispatcher.dispatch(event, payload, halt)

    async def until(self, event, payload=None):
        return await self.dispatch(event, payload, halt=True)

    def listen(self, events, listener: Callable | None = None):
        return self._dispatcher.listen(events, listener)

    def has_listeners(self, event) -> bool:
        return self._dispatcher.has_listeners(event)

    def forget(self, event) -> None:
        self._dispatcher.forget(event)

    def flush(self) -> None:
        self._dispatcher.flush()

    def dispatched(self, event, callback: Callable | None = None) -> list:
        """Return recorded dispatches for an event, optionally filtered."""
        records = self._dispatched.get(self._dispatcher._event_key(event), [])
        if callback is None:
            return list(records)
        return [record for record in records if callback(record)]

    def assert_dispatched(self, event, callback: Callable | None = None) -> list:
        records = self.dispatched(event, callback)
        assert records, f"The expected event [{self._dispatcher._event_key(event)}] was not dispatched."
        return records

    def assert_dispatched_times(self, event, times: int = 1) -> None:
        count = len(self.dispatched(event))
        assert count == times, (
            f"The expected event [{self._dispatcher._event_key(event)}] was dispatched {count} "
            f"time(s) instead of {times} time(s)."
        )

    def assert_not_dispatched(self, event, callback: Callable | None = None) -> None:
        count = len(self.dispatched(event, callback))
        assert count == 0, f"The unexpected event [{self._dispatcher._event_key(event)}] was dispatched."

    def assert_nothing_dispatched(self) -> None:
        total = sum(len(records) for records in self._dispatched.values())
        assert total == 0, f"{total} unexpected event(s) were dispatched."

    def _normalize(self, events) -> list[str]:
        if events is None:
            return []
        items = events if isinstance(events, (list, tuple)) else [events]
        return [self._dispatcher._event_key(event) for event in items]

    def _should_fake(self, name: str) -> bool:
        return not self._events_to_fake or name in self._events_to_fake
