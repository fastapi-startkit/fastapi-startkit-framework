from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any, override

from pydantic import BaseModel, Field, ValidationError, create_model

from .. import state as agent_state
from ..agent import Agent
from ..lab import Lab, ModelType
from .decisions import DECISIONS_MODEL, Decisions
from .questions import Answer, ClassificationError, Question

QUESTION_KEY = re.compile(r"[A-Za-z0-9_-]{1,64}")
MAX_QUESTIONS = 1000


@dataclass(frozen=True)
class ClassificationResult(Mapping[str, Any]):
    answers: dict[str, Answer]
    provider: str
    model: str
    usage: dict[str, int]
    state: dict[str, Any] | None = None

    def __getitem__(self, name: str) -> Any:
        return self.answers[name].value

    def __iter__(self) -> Iterator[str]:
        return iter(self.answers)

    def __len__(self) -> int:
        return len(self.answers)

    def __getattr__(self, name: str) -> Any:
        answers = self.__dict__.get("answers") or {}
        if name in answers:
            return answers[name].value
        raise AttributeError(f"{type(self).__name__!r} has no question {name!r}.")

    def answer(self, name: str) -> Answer:
        return self.answers[name]

    def to_dict(self) -> dict[str, Any]:
        return {name: answer.value for name, answer in self.answers.items()}


class ClassificationAgent(Agent):
    def __init__(self, questions: Mapping[str, Question] | None = None) -> None:
        self.questions = dict(questions or {})

    @override
    def instructions(self) -> str:
        return (
            "You classify the user's input. Answer every question in the response schema, "
            "using only the values each question allows."
        )

    @override
    def schema(self) -> type[BaseModel] | None:
        if not self.questions:
            return None
        fields: dict[str, Any] = {
            f"q{index}": (question.annotation(), Field(alias=name, description=question.describe()))
            for index, (name, question) in enumerate(self.questions.items())
        }
        return create_model("Classification", **fields)


class Classification:
    def __init__(self, input: str) -> None:
        self._input = input
        self._questions: dict[str, Question] = {}

    @classmethod
    def of(cls, input: str) -> Classification:
        return cls(input)

    def questions(self, questions: Mapping[str, Question]) -> Classification:
        if not questions:
            raise ValueError("Classification needs at least one question.")
        if len(questions) > MAX_QUESTIONS:
            raise ValueError(f"Classification accepts at most {MAX_QUESTIONS} questions.")
        for name, question in questions.items():
            if not isinstance(name, str) or not QUESTION_KEY.fullmatch(name):
                raise ValueError(f"Question key {name!r} must match [A-Za-z0-9_-] and be 1 to 64 characters.")
            if not isinstance(question, Question):
                raise ValueError(f"Question {name!r} must be a Boolean, Choice or Score, got {question!r}.")
        self._questions = dict(questions)
        return self

    async def classify(self, provider: str | None = None, model: str | None = None) -> ClassificationResult:
        if not isinstance(self._input, str) or not self._input.strip():
            raise ValueError("Classification needs a non-empty input.")
        if not self._questions:
            raise ValueError("Classification needs at least one question.")
        lab = Lab.get_provider(provider)
        if lab is Lab.GOOGLE:
            return await self._decide(lab, model)
        return await self._structured(lab, model)

    async def _decide(self, lab: Lab, model: str | None) -> ClassificationResult:
        model = lab.get_model(model, ModelType.DECISIONS) or DECISIONS_MODEL
        body = await Decisions(lab.get_api_key()).create(
            {
                "model": model,
                "input": self._input,
                "questions": {name: question.decision() for name, question in self._questions.items()},
            }
        )
        replies = body.get("answers") or {}
        answers: dict[str, Answer] = {}
        for name, question in self._questions.items():
            reply = replies.get(name)
            if not isinstance(reply, Mapping):
                raise ClassificationError(f"The Decisions API returned no answer for question {name!r}.")
            answers[name] = question.from_decision(name, reply)
        usage = body.get("usage") or {}
        return ClassificationResult(
            answers=answers,
            provider=lab.value,
            model=model,
            usage={"input": usage.get("total_input_tokens", 0), "output": usage.get("total_output_tokens", 0)},
        )

    async def _structured(self, lab: Lab, model: str | None) -> ClassificationResult:
        agent = ClassificationAgent(self._questions)
        agent.provider = lab.value
        agent.model = model
        try:
            turn = await agent.prompt(self._input)
        except ValidationError as exc:
            raise ClassificationError(f"The model returned an invalid classification: {exc}") from exc
        parsed = agent_state.structured(turn)
        if parsed is None:
            raise ClassificationError("The model returned no classification.")
        values = parsed.model_dump(by_alias=True) if isinstance(parsed, BaseModel) else dict(parsed)
        return ClassificationResult(
            answers={
                name: question.from_structured(name, values.get(name)) for name, question in self._questions.items()
            },
            provider=lab.value,
            model=lab.get_model(model),
            usage=agent_state.usage(turn),
            state=turn,
        )
