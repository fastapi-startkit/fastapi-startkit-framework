from dataclasses import field
from fastapi_startkit.configuration import Config
import dataclasses

from fastapi_startkit.environment import env, value
from fastapi_startkit.logging.config import StackChannel, DailyChannel, TerminalChannel


@dataclasses.dataclass
class LoggingConfig(Config):
    default: str = env("LOG_CHANNEL", "stack")

    channels: dict = field(
        default_factory=lambda: {
            "stack": StackChannel(driver="stack", channels=["daily", "terminal"]),
            "daily": DailyChannel(
                level=value(env("LOG_DAILY_LEVEL", "debug")),
                path=value(env("LOG_DAILY_PATH", "storage/logs")),
            ),
            "terminal": TerminalChannel(
                level=value(env("LOG_TERMINAL_LEVEL", "info")),
            ),
        }
    )
