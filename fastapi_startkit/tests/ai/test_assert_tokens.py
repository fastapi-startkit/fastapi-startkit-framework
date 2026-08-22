"""Tests for agent.assert_tokens() — assert on accumulated token usage (task #1251).

    agent.assert_tokens(lambda x: x.where("input", "<=", 5000).where("output", "<=", 5000))

Tokens accumulate across every recorded turn (and every ai message within a
turn); the predicate builds where-clauses that must all hold.
"""

import os
import tempfile
import unittest
from unittest import mock

from langchain_core.messages import AIMessage

from fastapi_startkit.ai.agent import Agent


class TokenAgent(Agent):
    pass


def _ai(input_tokens: int, output_tokens: int, cache_tokens: int = 0) -> AIMessage:
    return AIMessage(
        content="reply",
        additional_kwargs={"response_time": 1.0},
        usage_metadata={
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens + cache_tokens,
            "input_token_details": {"cache_read": cache_tokens},
        },
    )


def _fake_prompt(responses: list):
    queue = list(responses)

    async def prompt(agent_self, message, **kwargs):
        return queue.pop(0)

    return mock.patch.object(TokenAgent, "prompt", prompt)


class TestAssertTokens(unittest.IsolatedAsyncioTestCase):
    async def test_passes_when_accumulated_tokens_are_within_limits(self):
        responses = [
            {"messages": [_ai(100, 20)]},
            {"messages": [_ai(200, 30)]},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            with _fake_prompt(responses):
                with TokenAgent.record(os.path.join(tmp, "c.json")) as agent:
                    await agent.prompt("a")
                    await agent.prompt("b")
                    # accumulated: input=300, output=50
                    agent.assert_tokens(lambda x: x.where("input", "<=", 5000).where("output", "<=", 5000))

    async def test_fails_when_a_limit_is_exceeded(self):
        responses = [{"messages": [_ai(400, 20)]}]
        with tempfile.TemporaryDirectory() as tmp:
            with _fake_prompt(responses):
                with TokenAgent.record(os.path.join(tmp, "c.json")) as agent:
                    await agent.prompt("a")
                    with self.assertRaises(AssertionError):
                        agent.assert_tokens(lambda x: x.where("input", "<=", 300))

    async def test_supports_cache_and_total_fields(self):
        messages = [_ai(100, 20, cache_tokens=40)]
        with tempfile.TemporaryDirectory() as tmp:
            with _fake_prompt([{"messages": messages}]):
                with TokenAgent.record(os.path.join(tmp, "c.json")) as agent:
                    await agent.prompt("a")
                    agent.assert_tokens(lambda x: x.where("cache", "<=", 40).where("total", ">=", 160))

    async def test_accumulates_from_the_cassette_on_replay(self):
        responses = [{"messages": [_ai(100, 20)]}]
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "c.json")
            with _fake_prompt(responses):
                with TokenAgent.record(cassette) as agent:
                    await agent.prompt("a")

            # Replay: no live prompt available; tokens must come from the cassette.
            with TokenAgent.record(cassette) as agent:
                await agent.prompt("a")
                agent.assert_tokens(lambda x: x.where("input", "==", 100).where("output", "==", 20))
