import traceback
import warnings

from fastapi_startkit.application import app
from fastapi_startkit.logging.channels import BaseChannel


class Log:
    instance = None

    def __init__(self):
        self.app = app()
        self.logger: BaseChannel = self.app.make("logger")

    @classmethod
    def logger_info(cls) -> str:
        frame = None
        for current_frame in reversed(traceback.extract_stack()):
            if "logger.py" not in current_frame.filename:
                frame = current_frame
                break
        if not frame:
            return ""
        filename = frame.filename
        lineno = frame.lineno
        return f"{filename}:{str(lineno)} - "

    @classmethod
    def init(cls) -> BaseChannel:
        if cls.instance:
            return cls.instance.logger
        cls.instance = Log()
        return cls.instance.logger

    @classmethod
    def emergency(cls, message: str, *args, **kwargs):
        Log.init().emergency(cls.logger_info() + message, *args, **kwargs)

    @classmethod
    def alert(cls, message: str, *args, **kwargs):
        Log.init().alert(cls.logger_info() + message, *args, **kwargs)

    @classmethod
    def critical(cls, message: str, *args, **kwargs):
        Log.init().critical(cls.logger_info() + message, *args, **kwargs)

    @classmethod
    def error(cls, message: str, *args, **kwargs):
        Log.init().error(cls.logger_info() + message, *args, **kwargs)

    @classmethod
    def warning(cls, message: str, *args, **kwargs):
        Log.init().warning(cls.logger_info() + message, *args, **kwargs)

    @classmethod
    def notice(cls, message: str, *args, **kwargs):
        Log.init().notice(cls.logger_info() + message, *args, **kwargs)

    @classmethod
    def info(cls, message: str, *args, **kwargs):
        Log.init().info(cls.logger_info() + message, *args, **kwargs)

    @classmethod
    def debug(cls, message: str, *args, **kwargs):
        Log.init().debug(cls.logger_info() + message, *args, **kwargs)

    @classmethod
    def log(cls, level: str, message: str, *args, **kwargs):
        log = getattr(Log, level.lower(), Log.error)
        log(message, *args, **kwargs)


def __getattr__(name: str):
    if name == "Logger":
        warnings.warn("Logger is deprecated; use Log instead", DeprecationWarning, stacklevel=2)
        return Log
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
