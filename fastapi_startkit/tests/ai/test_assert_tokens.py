"""Tests for agent.assert_tokens() — assert on accumulated token usage (task #1251).

    agent.assert_tokens(lambda x: x.where("input", "<=", 5000).where("output", "<=", 5000))

Tokens accumulate across every recorded turn (and every ai message within a
turn); the predicate builds where-clauses that must all hold.
"""

import os
import tempfile
import unittest
from unittest import mock

from fastapi_startkit.ai import recording
from fastapi_startkit.ai.agent import Agent
from fastapi_startkit.ai.response import AgentResponse


class TokenAgent(Agent):
    pass


def _ai(input_tokens: int, output_tokens: int) -> dict:
    return recording.ai(
        content="reply",
        uses={
            "input_token": input_tokens,
            "output_token": output_tokens,
            "cache_token": 0,
            "total_token": input_tokens + output_tokens,
        },
        response_time=1.0,
    )


def _fake_prompt(responses: list):
    queue = list(responses)

    async def prompt(agent_self, message, **kwargs):
        return queue.pop(0)

    return mock.patch.object(TokenAgent, "prompt", prompt)


class TestAssertTokens(unittest.IsolatedAsyncioTestCase):
    async def test_passes_when_accumulated_tokens_are_within_limits(self):
        responses = [
            AgentResponse(content="a", usage={"input": 100, "output": 20}, transcript=[_ai(100, 20)]),
            AgentResponse(content="b", usage={"input": 200, "output": 30}, transcript=[_ai(200, 30)]),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            with _fake_prompt(responses):
                with TokenAgent.record(os.path.join(tmp, "c.json")) as agent:
                    await agent.prompt("a")
                    await agent.prompt("b")
                    # accumulated: input=300, output=50
                    agent.assert_tokens(lambda x: x.where("input", "<=", 5000).where("output", "<=", 5000))

    async def test_fails_when_a_limit_is_exceeded(self):
        responses = [AgentResponse(content="a", usage={"input": 400, "output": 20}, transcript=[_ai(400, 20)])]
        with tempfile.TemporaryDirectory() as tmp:
            with _fake_prompt(responses):
                with TokenAgent.record(os.path.join(tmp, "c.json")) as agent:
                    await agent.prompt("a")
                    with self.assertRaises(AssertionError):
                        agent.assert_tokens(lambda x: x.where("input", "<=", 300))

    async def test_supports_cache_and_total_fields(self):
        transcript = [
            recording.ai(
                content="a",
                uses={"input_token": 100, "output_token": 20, "cache_token": 40, "total_token": 160},
                response_time=1.0,
            )
        ]
        with tempfile.TemporaryDirectory() as tmp:
            with _fake_prompt([AgentResponse(content="a", usage={"input": 100, "output": 20}, transcript=transcript)]):
                with TokenAgent.record(os.path.join(tmp, "c.json")) as agent:
                    await agent.prompt("a")
                    agent.assert_tokens(lambda x: x.where("cache", "<=", 40).where("total", ">=", 160))

    async def test_accumulates_from_the_cassette_on_replay(self):
        responses = [AgentResponse(content="a", usage={"input": 100, "output": 20}, transcript=[_ai(100, 20)])]
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "c.json")
            with _fake_prompt(responses):
                with TokenAgent.record(cassette) as agent:
                    await agent.prompt("a")

            # Replay: no live prompt available; tokens must come from the cassette.
            with TokenAgent.record(cassette) as agent:
                await agent.prompt("a")
                agent.assert_tokens(lambda x: x.where("input", "==", 100).where("output", "==", 20))
