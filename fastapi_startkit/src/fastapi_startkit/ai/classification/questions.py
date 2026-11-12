from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import StrictBool

MAX_OPTIONS = 255


class ClassificationError(ValueError):
    pass


@dataclass(frozen=True)
class Answer:
    value: Any
    label: str
    confidence: float | None = None
    probabilities: dict[Any, float] | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class Question(ABC):
    decision_type: str

    def __init__(self, instructions: str) -> None:
        if not isinstance(instructions, str) or not instructions.strip():
            raise ValueError(f"{type(self).__name__} needs non-empty instructions.")
        self.instructions = instructions

    def decision(self) -> dict[str, Any]:
        question: dict[str, Any] = {"type": self.decision_type, "instructions": self.instructions}
        criteria = self.criteria()
        if criteria:
            question["criteria"] = criteria
        return question

    def from_decision(self, name: str, answer: Mapping[str, Any]) -> Answer:
        if answer.get("type") != self.decision_type:
            raise ClassificationError(
                f"Question {name!r} expects a {self.decision_type!r} answer, got {answer.get('type')!r}."
            )
        return self.parse_decision(name, answer)

    @abstractmethod
    def criteria(self) -> Any: ...

    @abstractmethod
    def annotation(self) -> Any: ...

    @abstractmethod
    def describe(self) -> str: ...

    @abstractmethod
    def parse_decision(self, name: str, answer: Mapping[str, Any]) -> Answer: ...

    @abstractmethod
    def from_structured(self, name: str, value: Any) -> Answer: ...


class Boolean(Question):
    decision_type = "noul"

    def __init__(self, instructions: str, descriptions: Mapping[str, str] | None = None) -> None:
        super().__init__(instructions)
        unknown = sorted(set(descriptions or {}) - {"true", "false"})
        if unknown:
            raise ValueError(f"Boolean descriptions accept only 'true' and 'false', got {unknown}.")
        self.descriptions = dict(descriptions or {})

    def criteria(self) -> dict[str, str]:
        return {f"{key}_description": description for key, description in self.descriptions.items()}

    def annotation(self) -> Any:
        return StrictBool

    def describe(self) -> str:
        lines = [self.instructions, "Answer true or false."]
        lines += [f"{key}: {description}" for key, description in self.descriptions.items()]
        return "\n".join(lines)

    def parse_decision(self, name: str, answer: Mapping[str, Any]) -> Answer:
        noul = _number(name, answer.get("noul"), 0.0, 1.0)
        return self._answer(
            noul >= 0.5,
            confidence=answer.get("confidence"),
            probabilities={True: noul, False: 1 - noul},
            raw=dict(answer),
        )

    def from_structured(self, name: str, value: Any) -> Answer:
        if not isinstance(value, bool):
            raise ClassificationError(f"Question {name!r} expects true or false, got {value!r}.")
        return self._answer(value)

    def _answer(self, value: bool, **details: Any) -> Answer:
        key = "true" if value else "false"
        return Answer(value=value, label=self.descriptions.get(key, key), **details)


class Choice(Question):
    decision_type = "choice"

    def __init__(self, instructions: str, options: Mapping[str, str] | Sequence[str]) -> None:
        super().__init__(instructions)
        choices = dict(options) if isinstance(options, Mapping) else dict.fromkeys(options, "")
        if not 2 <= len(choices) <= MAX_OPTIONS:
            raise ValueError(f"Choice needs 2 to {MAX_OPTIONS} options, got {len(choices)}.")
        if not all(isinstance(key, str) and key for key in choices):
            raise ValueError("Choice option keys must be non-empty strings.")
        self.options = choices

    def criteria(self) -> dict[str, str]:
        return dict(self.options)

    def annotation(self) -> Any:
        return Literal[tuple(self.options)]  # pyrefly: ignore[invalid-literal]

    def describe(self) -> str:
        lines = [self.instructions, "Answer with exactly one of these keys:"]
        lines += [f"{key}: {description}" if description else key for key, description in self.options.items()]
        return "\n".join(lines)

    def parse_decision(self, name: str, answer: Mapping[str, Any]) -> Answer:
        return self._answer(
            name,
            answer.get("choice"),
            confidence=answer.get("confidence"),
            probabilities=answer.get("probabilities"),
            raw=dict(answer),
        )

    def from_structured(self, name: str, value: Any) -> Answer:
        return self._answer(name, value)

    def _answer(self, name: str, value: Any, **details: Any) -> Answer:
        if not isinstance(value, str) or value not in self.options:
            raise ClassificationError(f"Question {name!r} expects one of {list(self.options)}, got {value!r}.")
        return Answer(value=value, label=self.options[value] or value, **details)


class Score(Question):
    decision_type = "score"

    def __init__(self, instructions: str, levels: Sequence[str]) -> None:
        super().__init__(instructions)
        if isinstance(levels, str) or not 2 <= len(levels) <= MAX_OPTIONS:
            raise ValueError(f"Score needs 2 to {MAX_OPTIONS} levels, ordered lowest first.")
        if not all(isinstance(level, str) and level.strip() for level in levels):
            raise ValueError("Score levels must be non-empty strings.")
        self.levels = list(levels)

    def criteria(self) -> list[str]:
        return list(self.levels)

    def annotation(self) -> Any:
        return Literal[tuple(range(len(self.levels)))]  # pyrefly: ignore[invalid-literal]

    def describe(self) -> str:
        lines = [self.instructions, "Answer with the index of one level, from lowest to highest:"]
        lines += [f"{index}: {level}" for index, level in enumerate(self.levels)]
        return "\n".join(lines)

    def parse_decision(self, name: str, answer: Mapping[str, Any]) -> Answer:
        score = _number(name, answer.get("score"), 0, len(self.levels) - 1)
        probabilities = answer.get("probabilities")
        return self._answer(
            math.floor(score + 0.5),
            confidence=answer.get("confidence"),
            probabilities={int(level): p for level, p in probabilities.items()} if probabilities else None,
            raw=dict(answer),
        )

    def from_structured(self, name: str, value: Any) -> Answer:
        if type(value) is not int or not 0 <= value < len(self.levels):
            raise ClassificationError(
                f"Question {name!r} expects a level index from 0 to {len(self.levels) - 1}, got {value!r}."
            )
        return self._answer(value)

    def _answer(self, index: int, **details: Any) -> Answer:
        return Answer(value=index, label=self.levels[index], **details)


def _number(name: str, value: Any, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not low <= value <= high:
        raise ClassificationError(f"Question {name!r} expects a number from {low} to {high}, got {value!r}.")
    return float(value)
