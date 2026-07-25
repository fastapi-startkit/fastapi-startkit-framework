"""Cassette on-disk format for Agent.record() (task #1251).

Recording persists each turn as an ordered message list keyed by the hash of the
user input; replay reconstructs the response from that list. Old flat-shape
cassettes must still replay (backward compatibility).
"""

import json
import os
import tempfile
import unittest
from unittest import mock

from fastapi_startkit.ai.agent import Agent
from fastapi_startkit.ai.response import AgentResponse


class RecordAgent(Agent):
    pass


def _fake_prompt(response: AgentResponse):
    async def prompt(agent_self, message, **kwargs):
        return response

    return mock.patch.object(RecordAgent, "prompt", prompt)


class TestNewCassetteFormat(unittest.IsolatedAsyncioTestCase):
    async def test_recording_persists_an_ordered_transcript_keyed_by_input(self):
        response = AgentResponse(
            transcript=[
                {"type": "ai", "tool_calls": [{"name": "job_search_tool", "args": {"query": "python"}, "id": "c1"}],
                 "uses": {"input_token": 117, "output_token": 22, "cache_token": 0, "total_token": 139},
                 "response_time": 12.0},
                {"type": "tool_response", "content_type": "json", "content": "[{\"id\": 2}]", "response_time": 5.0},
            ],
            content="[{\"id\": 2}]",
            tool_calls=[{"name": "job_search_tool", "args": {"query": "python"}, "id": "c1"}],
        )
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "c.json")
            with _fake_prompt(response):
                with RecordAgent.record(cassette) as agent:
                    await agent.prompt("suggest me jobs")

            store = json.loads(open(cassette).read())
            (turn,) = store.values()

        self.assertIsInstance(turn, list)
        self.assertEqual(turn[0], {"type": "human", "content": "suggest me jobs"})
        self.assertEqual(turn[1]["type"], "ai")
        self.assertEqual(turn[1]["tool_calls"][0]["name"], "job_search_tool")
        self.assertEqual(turn[2]["type"], "tool_response")
        self.assertEqual(turn[2]["content"], '[{"id": 2}]')

    async def test_replaying_a_new_format_cassette_reconstructs_tool_calls(self):
        response = AgentResponse(
            transcript=[
                {"type": "ai", "tool_calls": [{"name": "job_search_tool", "args": {"query": "python"}, "id": "c1"}],
                 "uses": {"input_token": 117, "output_token": 22}, "response_time": 12.0},
                {"type": "tool_response", "content_type": "json", "content": "[{\"id\": 2}]", "response_time": 5.0},
            ],
            content="[{\"id\": 2}]",
            tool_calls=[{"name": "job_search_tool", "args": {"query": "python"}, "id": "c1"}],
        )
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "c.json")
            with _fake_prompt(response):
                with RecordAgent.record(cassette) as agent:
                    await agent.prompt("suggest me jobs")

            # No live prompt available on replay — must read the cassette.
            with RecordAgent.record(cassette) as agent:
                replayed = await agent.prompt("suggest me jobs")
                agent.assert_tool_called("job_search_tool")

        self.assertEqual([tc["name"] for tc in replayed.tool_calls], ["job_search_tool"])
        self.assertEqual(replayed.content, '[{"id": 2}]')

    async def test_synthesizes_a_transcript_for_a_plain_response(self):
        response = AgentResponse(content="Hi there!", usage={"input": 3, "output": 2})
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "c.json")
            with _fake_prompt(response):
                with RecordAgent.record(cassette) as agent:
                    await agent.prompt("hello")

            store = json.loads(open(cassette).read())
            (turn,) = store.values()

        self.assertEqual(turn[0], {"type": "human", "content": "hello"})
        self.assertEqual(turn[1]["type"], "ai")
        self.assertEqual(turn[1]["content"], "Hi there!")
        self.assertEqual(turn[1]["uses"], {"input_token": 3, "output_token": 2, "cache_token": 0, "total_token": 5})


class TestBackwardCompatibleReplay(unittest.IsolatedAsyncioTestCase):
    async def test_old_flat_cassette_still_replays(self):
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "legacy.json")
            with RecordAgent.record(cassette) as agent:
                key = agent._key("suggest me jobs", None)
            legacy = {
                key: {
                    "content": "I found a job.",
                    "tool_calls": [{"name": "job_search_tool", "args": {"query": "python"}, "id": "c1"}],
                    "usage": {"input": 117, "output": 22},
                }
            }
            with open(cassette, "w") as f:
                json.dump(legacy, f)

            with RecordAgent.record(cassette) as agent:
                replayed = await agent.prompt("suggest me jobs")
                agent.assert_tool_called("job_search_tool")

        self.assertEqual(replayed.content, "I found a job.")
        self.assertEqual([tc["name"] for tc in replayed.tool_calls], ["job_search_tool"])
