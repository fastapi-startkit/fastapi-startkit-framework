from dataclasses import field
from fastapi_startkit.configuration import Config
import dataclasses

from fastapi_startkit.environment import env
from fastapi_startkit.logging.config import DailyChannel, StackChannel, TerminalChannel


@dataclasses.dataclass
class LoggingConfig(Config):
    default: str = env("LOG_CHANNEL", "stack")

    channels: dict[str, Config] = field(
        default_factory=lambda: {
            "stack": StackChannel(driver="stack", channels=["daily", "terminal"]),
            "daily": DailyChannel(
                level=env("LOG_DAILY_LEVEL", "debug"),
                path=env("LOG_DAILY_PATH", "storage/logs"),
            ),
            "terminal": TerminalChannel(
                level=env("LOG_TERMINAL_LEVEL", "info"),
            ),
        }
    )
