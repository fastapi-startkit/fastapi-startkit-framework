from typing import Any, Callable, Protocol

import pendulum
from fastapi_startkit.facades import Config

from ..factory import DriverFactory


class LogDriver(Protocol):
    emergency: Callable[..., Any]
    alert: Callable[..., Any]
    critical: Callable[..., Any]
    error: Callable[..., Any]
    warning: Callable[..., Any]
    notice: Callable[..., Any]
    info: Callable[..., Any]
    debug: Callable[..., Any]

    def should_run(self, level: str, max_level: str | None) -> bool: ...


class BaseChannel:
    driver: LogDriver
    max_level: str | None

    @staticmethod
    def driver_class(driver: str | None) -> Callable[..., LogDriver]:
        driver_class = DriverFactory.make(driver)
        if driver_class is None:
            raise ValueError(f"Unknown log driver: {driver!r}")
        return driver_class

    def get_time(self):
        return pendulum.now().in_tz(Config.get("logging.channels.timezone", "UTC"))

    def log(self, level, message, *args, **kwargs):
        return self.driver.should_run(level, self.max_level)

    def emergency(self, message, *args, **kwargs):
        if not self.driver.should_run("emergency", self.max_level):
            return

        return self.driver.emergency(message, *args, **kwargs)

    def alert(self, message, *args, **kwargs):
        if not self.driver.should_run("alert", self.max_level):
            return

        return self.driver.alert(message, *args, **kwargs)

    def critical(self, message, *args, **kwargs):
        if not self.driver.should_run("critical", self.max_level):
            return

        return self.driver.critical(message, *args, **kwargs)

    def error(self, message, *args, **kwargs):
        if not self.driver.should_run("error", self.max_level):
            return

        return self.driver.error(message, *args, **kwargs)

    def warning(self, message, *args, **kwargs):
        if not self.driver.should_run("warning", self.max_level):
            return

        return self.driver.warning(message, *args, **kwargs)

    def notice(self, message, *args, **kwargs):
        if not self.driver.should_run("notice", self.max_level):
            return

        return self.driver.notice(message, *args, **kwargs)

    def info(self, message, *args, **kwargs):
        if not self.driver.should_run("info", self.max_level):
            return

        return self.driver.info(message, *args, **kwargs)

    def debug(self, message, *args, **kwargs):
        if not self.driver.should_run("debug", self.max_level):
            return

        return self.driver.debug(message, *args, **kwargs)

    def channel(self, channel):
        from ..ChannelFactory import ChannelFactory

        channel_class = ChannelFactory.make(channel)
        if channel_class is None:
            raise ValueError(f"Unknown log channel: {channel!r}")
        return channel_class()
