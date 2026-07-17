from __future__ import annotations

import json
import re

from .agent import Agent


class JudgeAgent(Agent):
    """Grades a response against a natural-language expectation.

    Just an ``Agent`` — set ``.model``/``.provider`` like any other agent
    and the verdict call goes through the same model resolution, provider
    handling, and pipeline as any other agent, so it's fakeable via
    ``JudgeAgent.fake()`` and replayable via ``JudgeAgent.record()`` instead
    of hand-rolling a separate langchain call.
    """

    async def judge(self, expectation: str, content: str) -> dict:
        response = await self.prompt(self._build_prompt(expectation, content))
        return self._parse_verdict(response.content)

    @staticmethod
    def _build_prompt(expectation: str, content: str) -> str:
        return (
            "You are grading whether an AI agent's response satisfies an expectation.\n"
            f"Expectation: {expectation}\n"
            f"Response: {content}\n\n"
            'Reply with strict JSON only, no prose: {"passed": true|false, "reasoning": "<one sentence>"}'
        )

    @staticmethod
    def _parse_verdict(raw: str) -> dict:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        data = json.loads(match.group(0) if match else raw)
        return {"passed": bool(data.get("passed")), "reasoning": data.get("reasoning", "")}
