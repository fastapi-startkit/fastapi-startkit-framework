from typing import Any

NotificationObject = Any

class Notification:
    """Notification handler facade, which handle sending/queuing notifications anonymously
    or to notifiables through different channels."""

    @staticmethod
    def add_driver(name: str, driver: str): ...
    @staticmethod
    def get_driver(name: str) -> Any: ...
    @staticmethod
    def set_configuration(config: dict) -> "Notification": ...
    @staticmethod
    def get_config_options(driver: str) -> dict: ...
    @staticmethod
    def send(
        notifiables: list,
        notification: "NotificationObject",
        drivers: list = [],
        dry: bool = False,
        fail_silently: bool = False,
    ) -> Any:
        """Send the given notification to the given notifiables."""
        ...
    @staticmethod
    def route(driver: str, route: str) -> Any:
        """Specify how to send a notification to an anonymous notifiable."""
        ...
