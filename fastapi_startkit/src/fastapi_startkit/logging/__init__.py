import warnings

from .logger import Log
from .providers import LogProvider

__all__ = ["Log", "LogProvider"]


def __getattr__(name: str):
    if name == "Logger":
        warnings.warn("Logger is deprecated; use Log instead", DeprecationWarning, stacklevel=2)
        return Log
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
