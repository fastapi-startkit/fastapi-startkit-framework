import logging
import os

from .BaseDriver import BaseDriver


class LogSingleDriver(BaseDriver):
    def __init__(self, *args, path: str, max_level: str | None = None, **kwargs):
        self.max_level = max_level
        self.path = path
        # A dedicated, non-propagating logger per file keeps records away from the root
        # logger (and its LoggingHandler bridge, which would feed them back into Logger).
        self.log = logging.getLogger(f"fastapi_startkit.logging.single.{os.path.abspath(path)}")
        self.log.setLevel(logging.DEBUG)
        self.log.propagate = False
        self.handler = self._file_handler()
        self.handler.setFormatter(
            logging.Formatter("{} - %(levelname)s - %(message)s".format(self.get_time().to_datetime_string()))
        )

    def _file_handler(self) -> logging.FileHandler:
        # Drivers are rebuilt per channel instance; reuse the handler so each file holds one descriptor.
        for handler in self.log.handlers:
            if isinstance(handler, logging.FileHandler):
                return handler

        handler = logging.FileHandler(self.path, "a")
        self.log.addHandler(handler)
        return handler

    def change_format(self, changed_format):
        self.handler.setFormatter(logging.Formatter(changed_format))

    def close(self):
        self.log.removeHandler(self.handler)
        self.handler.close()

    def _write(self, level: int, label: str, message):
        self.change_format("{} - {} - %(message)s".format(self.get_time().to_datetime_string(), label))
        return self.log.log(level, message)

    def emergency(self, message, *args, **kwargs):
        return self._write(logging.CRITICAL, "EMERGENCY", message)

    def alert(self, message, *args, **kwargs):
        return self._write(logging.CRITICAL, "ALERT", message)

    def critical(self, message, *args, **kwargs):
        return self._write(logging.CRITICAL, "CRITICAL", message)

    def error(self, message, *args, **kwargs):
        return self._write(logging.ERROR, "ERROR", message)

    def warning(self, message, *args, **kwargs):
        return self._write(logging.WARNING, "WARNING", message)

    def notice(self, message, *args, **kwargs):
        return self._write(logging.INFO, "NOTICE", message)

    def info(self, message, *args, **kwargs):
        return self._write(logging.INFO, "INFO", message)

    def debug(self, message, *args, **kwargs):
        return self._write(logging.DEBUG, "DEBUG", message)
