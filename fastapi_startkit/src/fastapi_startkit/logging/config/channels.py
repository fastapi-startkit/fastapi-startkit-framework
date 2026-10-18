from fastapi_startkit.configuration import Config
from dataclasses import dataclass, field


@dataclass
class SingleChannel(Config):
    driver: str = "single"
    level: str = "debug"
    path: str = "storage/logs/single.log"


@dataclass
class StackChannel(Config):
    driver: str = "stack"
    channels: list[str] = field(default_factory=lambda: ["daily", "terminal"])


@dataclass
class DailyChannel(Config):
    driver: str = "daily"
    level: str = "debug"
    path: str = "storage/logs"


@dataclass
class TerminalChannel(Config):
    driver: str = "terminal"
    level: str = "info"


@dataclass
class SlackChannel(Config):
    driver: str = "slack"
    channel: str = "#bot"
    emoji: str = ":warning:"
    username: str = "Logging Bot"
    token: str | None = None
    level: str = "debug"


@dataclass
class SyslogChannel(Config):
    driver: str = "syslog"
    path: str = "/var/run/syslog"
    level: str = "debug"
