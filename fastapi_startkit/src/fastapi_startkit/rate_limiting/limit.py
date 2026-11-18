import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Self


@dataclass
class Limit:
    max_attempts: int
    decay_seconds: int = 60
    key: str = ""
    response_callback: Callable[..., Any] | None = None

    @classmethod
    def per_second(cls, max_attempts: int, decay_seconds: int = 1) -> Self:
        return cls(max_attempts, decay_seconds)

    @classmethod
    def per_minute(cls, max_attempts: int, decay_minutes: int = 1) -> Self:
        return cls(max_attempts, decay_minutes * 60)

    @classmethod
    def per_minutes(cls, decay_minutes: int, max_attempts: int) -> Self:
        return cls(max_attempts, decay_minutes * 60)

    @classmethod
    def per_hour(cls, max_attempts: int, decay_hours: int = 1) -> Self:
        return cls(max_attempts, decay_hours * 3600)

    @classmethod
    def per_day(cls, max_attempts: int, decay_days: int = 1) -> Self:
        return cls(max_attempts, decay_days * 86400)

    @staticmethod
    def none() -> "Unlimited":
        return Unlimited()

    def by(self, key: Any) -> Self:
        self.key = str(key)
        return self

    def response(self, callback: Callable[..., Any]) -> Self:
        self.response_callback = callback
        return self


class Unlimited(Limit):
    def __init__(self) -> None:
        super().__init__(sys.maxsize)
