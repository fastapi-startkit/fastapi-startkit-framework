import os
import tempfile
import unittest
from unittest import mock

from pydantic import BaseModel

from langchain_core.messages import AIMessage

from fastapi_startkit.ai import state as ai_state
from fastapi_startkit.ai.agent import Agent
from fastapi_startkit.ai.ai import Ai


class User(BaseModel):
    id: str
    name: str = ""


class UserAgent(Agent):
    def schema(self):
        return User


class TestAgentSchema(unittest.IsolatedAsyncioTestCase):
    def tearDown(self):
        Ai.reset_fakes()

    async def test_fake_json_is_built_into_the_schema(self):
        agent = UserAgent()
        with UserAgent.fake(['{"id": "u-1", "name": "Alex"}']):
            response = await agent.prompt("get the user")

        parsed = response["structured_response"]
        self.assertIsInstance(parsed, User)
        self.assertEqual(parsed.id, "u-1")
        self.assertEqual(parsed.name, "Alex")
        self.assertEqual(ai_state.text(response), '{"id": "u-1", "name": "Alex"}')

    async def test_no_schema_leaves_parsed_none(self):
        agent = Agent()
        with Agent.fake(['{"id": "u-1"}']):
            response = await agent.prompt("anything")

        self.assertNotIn("structured_response", response)

    async def test_invalid_json_for_schema_raises(self):
        agent = UserAgent()
        with UserAgent.fake(['{"name": "no id here"}']):
            with self.assertRaises(Exception):
                await agent.prompt("get the user")

    async def test_record_stores_json_and_rebuilds_schema_on_replay(self):
        async def fake_run(self, message, **kwargs):
            return {"messages": [AIMessage(content='{"id": "u-9", "name": "Sam"}')]}

        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "user.json")
            with mock.patch.object(UserAgent, "prompt", fake_run):
                with UserAgent.record(cassette) as agent:
                    recorded = await agent.prompt("get the user")
                with UserAgent.record(cassette) as agent:
                    replayed = await agent.prompt("get the user")

        self.assertEqual(recorded["structured_response"], User(id="u-9", name="Sam"))
        self.assertEqual(replayed["structured_response"], User(id="u-9", name="Sam"))
