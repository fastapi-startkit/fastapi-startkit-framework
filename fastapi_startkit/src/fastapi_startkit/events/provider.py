"""Service provider that registers the event dispatcher.

Subclass and define ``listen`` to map events to their listeners, mirroring
Laravel's ``EventServiceProvider``::

    class AppEventServiceProvider(EventServiceProvider):
        listen = {
            UserRegistered: [SendWelcomeEmail, LogRegistration],
        }
"""

from typing import cast

from fastapi_startkit.support import Provider

from .dispatcher import Dispatcher


class EventServiceProvider(Provider):
    provider_key = "events"

    listen: dict = {}

    def register(self) -> None:
        self.app.bind("events", Dispatcher(self.app))

    def boot(self) -> None:
        dispatcher = cast(Dispatcher, self.app.make("events"))
        for event, listeners in self.listen.items():
            for listener in listeners:
                dispatcher.listen(event, listener)
