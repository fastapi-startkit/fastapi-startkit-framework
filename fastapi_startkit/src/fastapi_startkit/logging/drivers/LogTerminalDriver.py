from .BaseDriver import BaseDriver


class HasColoredOutput:
    # flush=True so terminal logs appear in real time even when stdout is a pipe
    # (e.g. under `npm run dev`/concurrently), where Python uses block buffering.
    def success(self, message):
        print("\033[92m {0} \033[0m".format(message), flush=True)

    def warning(self, message):
        print("\033[93m {0} \033[0m".format(message), flush=True)

    def danger(self, message):
        print("\033[91m {0} \033[0m".format(message), flush=True)

    def info(self, message):
        return self.success(message)


class LogTerminalDriver(BaseDriver, HasColoredOutput):
    def __init__(self, *args, **kwargs):
        pass

    def emergency(self, message):
        super().warning(self.get_format(message, "EMERGENCY"))

    def alert(self, message):
        super().warning(self.get_format(message, "ALERT"))

    def critical(self, message):
        super().warning(self.get_format(message, "CRITICAL"))

    def error(self, message):
        super().warning(self.get_format(message, "ERROR"))

    def warning(self, message):
        super().warning(self.get_format(message, "WARNING"))

    def notice(self, message):
        super().warning(self.get_format(message, "NOTICE"))

    def info(self, message):
        super().warning(self.get_format(message, "INFO"))

    def debug(self, message):
        super().warning(self.get_format(message, "DEBUG"))

    def get_format(self, message, level):
        return "{time} - {level} - {message}".format(
            time=self.get_time().to_datetime_string(), level=level, message=message
        )
