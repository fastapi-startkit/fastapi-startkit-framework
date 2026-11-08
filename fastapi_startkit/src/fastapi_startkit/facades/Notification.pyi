from typing import Any

from fastapi_startkit.notifications import AnonymousNotifiable, ChannelManager
from fastapi_startkit.notifications import Notification as NotificationObject
from fastapi_startkit.notifications.manager import ChannelFactory

class Notification:
    @staticmethod
    async def send(notifiables: Any, notification: NotificationObject) -> None: ...
    @staticmethod
    def route(channel: str, route: Any) -> AnonymousNotifiable: ...
    @staticmethod
    def channel(name: str) -> Any: ...
    @staticmethod
    def extend(name: str, factory: ChannelFactory) -> ChannelManager: ...
