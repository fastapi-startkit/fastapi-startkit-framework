@dataclass
class LoggingConfig(Config):
    default: str = env("LOG_CHANNEL", "stack")
    channels: dict = field(default_factory=lambda: {
        "stack": StackChannel(channels=["daily", "terminal", "slack"]),
        "daily": DailyChannel(path="storage/logs"),
        "terminal": TerminalChannel(level="info"),
        "slack": SlackChannel(
            channel="#alerts", token=env("SLACK_TOKEN"), level="error"),
    })
