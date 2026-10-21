import time

import pytest


class Clock:
    def __init__(self, now: float):
        self.now = now

    def __call__(self) -> float:
        return self.now

    def travel(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock(monkeypatch):
    clock = Clock(1_000_000.0)
    monkeypatch.setattr(time, "time", clock)
    return clock
