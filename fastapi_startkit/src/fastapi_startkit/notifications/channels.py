import json
from collections.abc import Callable, Iterable
from typing import Any, Protocol

import pendulum

from fastapi_startkit.exceptions import NotificationException
from fastapi_startkit.mail import Mailable

from .notification import Notification


class Channel(Protocol):
    async def send(self, notifiable: Any, notification: Notification) -> Any: ...


def render(notification: Notification, channel: str, notifiable: Any) -> Any:
    method = getattr(notification, f"to_{channel}", None)
    if method is None:
        raise NotificationException(f"Notification [{type(notification).__name__}] has no to_{channel}() method.")
    return method(notifiable)


class MailChannel:
    def __init__(self, mail: Callable[[], Any]):
        self.mail = mail

    async def send(self, notifiable: Any, notification: Notification) -> Any:
        mailable = render(notification, "mail", notifiable)
        if not isinstance(mailable, Mailable):
            raise NotificationException(f"{type(notification).__name__}.to_mail() must return a Mailable.")
        if not mailable.has_to():
            route = notifiable.route_notification_for("mail", notification)
            if not route:
                return None
            mailable.to(route)
        return await self.mail().mailer(notification.mailer).send(mailable)


class DatabaseChannel:
    def __init__(self, connection: Callable[[], Any], table: str = "notifications"):
        self.connection = connection
        self.table = table

    def query(self) -> Any:
        return self.connection().query().table(self.table)

    def query_for(self, notifiable: Any, ids: list[str] | None = None) -> Any:
        builder = (
            self.query()
            .where("notifiable_type", notifiable.notifiable_type())
            .where("notifiable_id", notifiable.notifiable_key())
        )
        return builder if ids is None else builder.where_in("id", ids)

    async def notifications_for(self, notifiable: Any, read: bool | None = None) -> list[dict[str, Any]]:
        builder = self.query_for(notifiable).order_by("created_at", "desc")
        if read is True:
            builder.where_not_null("read_at")
        elif read is False:
            builder.where_null("read_at")
        return list(await builder.connection.select(builder.to_qmark(), list(builder.get_bindings())))

    async def mark_as_read(self, notifiable: Any, ids: Iterable[str] | None = None) -> int:
        now = pendulum.now("UTC").to_datetime_string()
        return await self.update_for(notifiable, ids, {"read_at": now, "updated_at": now}, unread_only=True)

    async def mark_as_unread(self, notifiable: Any, ids: Iterable[str] | None = None) -> int:
        now = pendulum.now("UTC").to_datetime_string()
        return await self.update_for(notifiable, ids, {"read_at": None, "updated_at": now})

    async def update_for(
        self, notifiable: Any, ids: Iterable[str] | None, values: dict[str, Any], unread_only: bool = False
    ) -> int:
        selected = None if ids is None else list(ids)
        if selected == []:
            return 0
        builder = self.query_for(notifiable, selected)
        if unread_only:
            builder.where_null("read_at")
        return await builder.update(values)

    async def send(self, notifiable: Any, notification: Notification) -> dict[str, Any]:
        if not hasattr(notifiable, "notifiable_type"):
            raise NotificationException("The database channel requires a Notifiable model.")
        method = getattr(notification, "to_database", None) or notification.to_array
        now = pendulum.now("UTC").to_datetime_string()
        record = {
            "id": notification.id,
            "type": type(notification).__name__,
            "notifiable_type": notifiable.notifiable_type(),
            "notifiable_id": notifiable.notifiable_key(),
            "data": json.dumps(method(notifiable)),
            "read_at": None,
            "created_at": now,
            "updated_at": now,
        }
        await self.query().insert(record)
        return record


class BroadcastChannel:
    def __init__(self, broadcasting: Callable[[], Any]):
        self.broadcasting = broadcasting

    async def send(self, notifiable: Any, notification: Notification) -> dict[str, Any] | None:
        names = self.channel_names(notifiable, notification)
        if not names:
            return None
        method = getattr(notification, "to_broadcast", None) or notification.to_array
        payload = {**method(notifiable), "id": notification.id, "type": notification.broadcast_type()}
        manager = self.broadcasting()
        for name in names:
            await manager.emit(name, notification.broadcast_as(), payload)
        return payload

    def channel_names(self, notifiable: Any, notification: Notification) -> list[str]:
        route = notifiable.route_notification_for("broadcast", notification)
        if route is notifiable:
            if not hasattr(notifiable, "receives_broadcast_notifications_on"):
                raise NotificationException("The broadcast channel requires a Notifiable model or a broadcast route.")
            route = notifiable.receives_broadcast_notifications_on()
        if not route:
            return []
        routes = route if isinstance(route, (list, tuple)) else [route]
        return [f"private-{item}" if isinstance(item, str) else item.name for item in routes]
