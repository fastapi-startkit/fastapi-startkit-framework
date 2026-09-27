from __future__ import annotations

from pydantic import BaseModel

from .agent import Agent


class Verdict(BaseModel):
    passed: bool
    reasoning: str = ""


class JudgeAgent(Agent):
    """Grades a response against a natural-language expectation.

    A plain ``Agent`` whose ``schema()`` is a ``Verdict`` model, so the JSON
    reply is parsed into a typed result through the standard structured-output
    path — no hand-rolled verdict parsing. Set ``.model``/``.provider`` like
    any other agent; it's fakeable via ``fake()`` and replayable via
    ``record()`` for free.
    """

    def instructions(self) -> str:
        return (
            "You are grading whether an AI agent's response satisfies an expectation. "
            'Reply with strict JSON only, no prose: {"passed": true|false, "reasoning": "<one sentence>"}'
        )

    def schema(self):
        return Verdict

    async def judge(self, expectation: str, content: str) -> dict:
        state = await self.prompt(f"Expectation: {expectation}\n\nResponse to grade:\n{content}")
        return state["structured_response"].model_dump()
