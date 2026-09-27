from .BaseDriver import BaseDriver
import logging
import logging.handlers


class LogSyslogDriver(BaseDriver):
    def __init__(self, *args, path: str | tuple[str, int], **kwargs):
        # A dedicated, non-propagating logger per address keeps records away from the root
        # logger (and its LoggingHandler bridge, which would feed them back into Logger).
        self.log = logging.getLogger(f"fastapi_startkit.logging.syslog.{path}")
        self.log.propagate = False
        self.handler = self._syslog_handler(path)
        self.handler.setFormatter(
            logging.Formatter("{} - %(levelname)s - %(message)s".format(self.get_time().to_datetime_string()))
        )

    def _syslog_handler(self, address: str | tuple[str, int]) -> logging.Handler:
        # Drivers are rebuilt per channel instance; reuse the handler so each address holds one socket.
        if self.log.handlers:
            return self.log.handlers[0]

        handler = logging.handlers.SysLogHandler(address=address)
        self.log.addHandler(handler)
        return handler

    def close(self):
        self.log.removeHandler(self.handler)
        self.handler.close()

    def emergency(self, message):
        self.log.setLevel(logging.CRITICAL)
        return self.log.critical(message)

    def alert(self, message):
        self.log.setLevel(logging.CRITICAL)
        return self.log.critical(message)

    def critical(self, message):
        self.log.setLevel(logging.CRITICAL)
        return self.log.critical(message)

    def error(self, message):
        self.log.setLevel(logging.ERROR)
        return self.log.error(message)

    def warning(self, message):
        self.log.setLevel(logging.WARNING)
        return self.log.warning(message)

    def notice(self, message):
        self.log.setLevel(logging.INFO)
        return self.log.info(message)

    def info(self, message):
        self.log.setLevel(logging.INFO)
        return self.log.info(message)

    def debug(self, message):
        self.log.setLevel(logging.DEBUG)
        return self.log.debug(message)
