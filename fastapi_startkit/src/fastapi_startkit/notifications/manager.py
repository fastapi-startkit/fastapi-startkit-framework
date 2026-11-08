import uuid
from collections.abc import Callable
from typing import Any, Self

from fastapi_startkit.exceptions import NotificationException

from .channels import Channel
from .notifiable import AnonymousNotifiable
from .notification import Notification

ChannelFactory = Callable[[], Channel]


class ChannelManager:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._channels: dict[str, Channel] = {}
        self._creators: dict[str, ChannelFactory] = {}

    def extend(self, name: str, factory: ChannelFactory) -> Self:
        self._creators[name] = factory
        self._channels.pop(name, None)
        return self

    def channel(self, name: str) -> Any:
        if name not in self._channels:
            if name not in self._creators:
                raise NotificationException(f"Notification channel [{name}] is not supported.")
            self._channels[name] = self._creators[name]()
        return self._channels[name]

    async def send(self, notifiables: Any, notification: Notification) -> None:
        for notifiable in notifiables if isinstance(notifiables, (list, tuple)) else [notifiables]:
            notification.id = uuid.uuid4().hex
            for name in notification.via(notifiable):
                await self.channel(name).send(notifiable, notification)

    def route(self, channel: str, route: Any) -> AnonymousNotifiable:
        return AnonymousNotifiable().route(channel, route)
