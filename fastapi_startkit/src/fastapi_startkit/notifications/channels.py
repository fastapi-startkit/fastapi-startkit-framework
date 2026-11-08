import json
from collections.abc import Callable
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

    async def notifications_for(self, notifiable: Any) -> list[dict[str, Any]]:
        builder = (
            self.query()
            .where("notifiable_type", notifiable.notifiable_type())
            .where("notifiable_id", notifiable.notifiable_key())
            .order_by("created_at", "desc")
        )
        return list(await builder.connection.select(builder.to_qmark(), list(builder.get_bindings())))

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
