from pydantic.dataclasses import dataclass
from pydantic.fields import Field


@dataclass
class SingleChannel:
    driver: str = "single"
    level: str = "debug"
    path: str = "storage/logs/single.log"


@dataclass
class StackChannel:
    driver: str = "stack"
    channels: list = Field(default_factory=lambda: ["daily", "terminal"])


@dataclass
class DailyChannel:
    driver: str = "daily"
    level: str = "debug"
    path: str = "storage/logs"


@dataclass
class TerminalChannel:
    driver: str = "terminal"
    level: str = "info"


@dataclass
class SlackChannel:
    driver: str = "slack"
    channel: str = "#bot"
    emoji: str = ":warning:"
    username: str = "Logging Bot"
    token: str | None = None
    level: str = "debug"


@dataclass
class SyslogChannel:
    driver: str = "syslog"
    path: str = "/var/run/syslog"
    level: str = "debug"
