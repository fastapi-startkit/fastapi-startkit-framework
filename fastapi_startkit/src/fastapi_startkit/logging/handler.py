import logging

# Framework-only severities have no stdlib equivalent; map them to the nearest one.
_STDLIB_LEVELS = {"notice": "INFO", "alert": "CRITICAL", "emergency": "CRITICAL"}


class LoggingHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        from fastapi_startkit.logging.logger import Logger

        Logger.log(record.levelname, self.format(record))

    @staticmethod
    def install(level: str | None = None):
        root_logger = logging.getLogger()
        if not any(isinstance(h, LoggingHandler) for h in root_logger.handlers):
            root_logger.addHandler(LoggingHandler())
        if level:
            root_logger.setLevel(_STDLIB_LEVELS.get(level.lower(), level.upper()))
