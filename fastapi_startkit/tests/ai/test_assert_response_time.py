"""Tests for agent.assert_response_time_lt() — assert on recorded response time (task #1271).

    agent.assert_response_time_lt(0.1)

The assertion must read the ``response_time`` recorded on the cassette transcript
(summed across every ai/tool step of every turn), NOT the wall-clock duration of
the replay. On cassette replay the cache read is near-instant, so a slow recorded
turn must still be seen as slow — otherwise a replayed call always looks fast and
the assertion silently passes regardless of what was recorded.
"""

import os
import tempfile
import unittest
from unittest import mock

from fastapi_startkit.ai import recording
from fastapi_startkit.ai.agent import Agent


class TimingAgent(Agent):
    pass


def _slow_turn_transcript() -> list[dict]:
    """Mirror the reported repro: a slow ai turn (~660ms) plus a tool response
    (~1.5ms). Total recorded time ~= 0.6616s."""
    return [
        recording.ai(
            content="",
            tool_calls=[
                {"args": {"query": "python developer"}, "id": "x", "name": "job_search_tool", "type": "tool_call"}
            ],
            uses={"input_token": 68, "output_token": 18, "cache_token": 0, "total_token": 86},
            response_time=660.0997089408338,
        ),
        recording.tool_response(content='[{"id": 2, "title": "Frontend Developer"}]', response_time=1.4820829965174198),
    ]


def _fake_prompt(responses: list):
    queue = list(responses)

    async def prompt(agent_self, message, **kwargs):
        return queue.pop(0)

    return mock.patch.object(TimingAgent, "prompt", prompt)


def _record(cassette: str, responses: list, prompts: list[str]) -> None:
    """Record a cassette by driving fake live prompts once."""

    async def _drive():
        with _fake_prompt(responses):
            with TimingAgent.record(cassette) as agent:
                for message in prompts:
                    await agent.prompt(message)

    return _drive()


def _slow_response() -> dict:
    return recording.to_state(_slow_turn_transcript())


class TestAssertResponseTime(unittest.IsolatedAsyncioTestCase):
    async def test_fails_when_recorded_time_exceeds_threshold_on_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "c.json")
            await _record(cassette, [_slow_response()], ["suggest python developer jobs"])

            # Replay: cache read is near-instant, but the recorded ~0.66s must win.
            with TimingAgent.record(cassette) as agent:
                await agent.prompt("suggest python developer jobs")
                with self.assertRaises(AssertionError):
                    agent.assert_response_time_lt(0.1)

    async def test_passes_when_recorded_time_under_threshold_on_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "c.json")
            await _record(cassette, [_slow_response()], ["suggest python developer jobs"])

            with TimingAgent.record(cassette) as agent:
                await agent.prompt("suggest python developer jobs")
                agent.assert_response_time_lt(2.0)  # 0.6616 < 2.0

    async def test_accumulates_recorded_time_across_turns(self):
        responses = [_slow_response(), _slow_response()]
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "c.json")
            await _record(cassette, responses, ["first", "second"])

            with TimingAgent.record(cassette) as agent:
                await agent.prompt("first")
                await agent.prompt("second")
                # Two turns ~0.6616s each -> ~1.32s total.
                agent.assert_response_time_lt(2.0)
                with self.assertRaises(AssertionError):
                    agent.assert_response_time_lt(1.0)


if __name__ == "__main__":
    unittest.main()
