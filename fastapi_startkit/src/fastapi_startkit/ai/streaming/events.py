from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StreamStarted:
    message_id: str


@dataclass(frozen=True)
class StepStarted:
    pass


@dataclass(frozen=True)
class TextStarted:
    id: str


@dataclass(frozen=True)
class TextDelta:
    id: str
    delta: str


@dataclass(frozen=True)
class TextEnded:
    id: str


@dataclass(frozen=True)
class ReasoningStarted:
    id: str


@dataclass(frozen=True)
class ReasoningDelta:
    id: str
    delta: str


@dataclass(frozen=True)
class ReasoningEnded:
    id: str


@dataclass(frozen=True)
class ToolInputStarted:
    id: str
    name: str


@dataclass(frozen=True)
class ToolInputDelta:
    id: str
    delta: str


@dataclass(frozen=True)
class ToolInputAvailable:
    id: str
    name: str
    input: Any


@dataclass(frozen=True)
class ToolOutputAvailable:
    id: str
    name: str
    output: Any


@dataclass(frozen=True)
class StepFinished:
    pass


@dataclass(frozen=True)
class StreamFinished:
    pass


@dataclass(frozen=True)
class StreamFailed:
    error: Exception


StreamEvent = (
    StreamStarted
    | StepStarted
    | TextStarted
    | TextDelta
    | TextEnded
    | ReasoningStarted
    | ReasoningDelta
    | ReasoningEnded
    | ToolInputStarted
    | ToolInputDelta
    | ToolInputAvailable
    | ToolOutputAvailable
    | StepFinished
    | StreamFinished
    | StreamFailed
)
