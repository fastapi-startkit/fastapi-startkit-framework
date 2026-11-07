from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .notification import Notification


def notification_manager() -> Any:
    from fastapi_startkit.application import app

    return app().make("notification")


class RoutesNotifications:
    async def notify(self, notification: "Notification") -> None:
        await notification_manager().send(self, notification)

    def route_notification_for(self, channel: str, notification: "Notification") -> Any:
        method = getattr(self, f"route_notification_for_{channel}", None)
        if method is not None:
            return method(notification)
        if channel == "mail":
            return getattr(self, "email", None)
        return self


class Notifiable(RoutesNotifications):
    def notifiable_type(self) -> str:
        from fastapi_startkit.masoniteorm.models.registry import Registry

        return Registry.get_morph_name(type(self))

    def notifiable_key(self) -> str:
        return str(getattr(self, getattr(type(self), "__primary_key__", "id")))

    async def notifications(self) -> list[dict[str, Any]]:
        return await notification_manager().channel("database").notifications_for(self)


class AnonymousNotifiable(RoutesNotifications):
    def __init__(self) -> None:
        self.routes: dict[str, Any] = {}

    def route(self, channel: str, route: Any) -> "AnonymousNotifiable":
        self.routes[channel] = route
        return self

    def route_notification_for(self, channel: str, notification: "Notification") -> Any:
        return self.routes.get(channel)
