import os
import tempfile
import unittest
from unittest import mock

from pydantic import BaseModel

from fastapi_startkit.ai.agent import Agent
from fastapi_startkit.ai.response import AgentResponse


class User(BaseModel):
    id: str
    name: str = ""


class UserAgent(Agent):
    def schema(self):
        return User


class TestAgentSchema(unittest.IsolatedAsyncioTestCase):
    async def test_fake_json_is_built_into_the_schema(self):
        agent = UserAgent()
        with UserAgent.fake({"*": '{"id": "u-1", "name": "Alex"}'}):
            response = await agent.prompt("get the user")

        self.assertIsInstance(response.parsed, User)
        self.assertEqual(response.parsed.id, "u-1")
        self.assertEqual(response.parsed.name, "Alex")
        self.assertEqual(response.content, '{"id": "u-1", "name": "Alex"}')

    async def test_no_schema_leaves_parsed_none(self):
        agent = Agent()
        with Agent.fake({"*": '{"id": "u-1"}'}):
            response = await agent.prompt("anything")

        self.assertIsNone(response.parsed)

    async def test_invalid_json_for_schema_raises(self):
        agent = UserAgent()
        with UserAgent.fake({"*": '{"name": "no id here"}'}):
            with self.assertRaises(Exception):
                await agent.prompt("get the user")

    async def test_record_stores_json_and_rebuilds_schema_on_replay(self):
        async def fake_run(self, message, **kwargs):
            return AgentResponse(content='{"id": "u-9", "name": "Sam"}')

        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "user.json")
            with mock.patch.object(UserAgent, "_run", fake_run):
                with UserAgent.record(cassette):
                    recorded = await UserAgent().prompt("get the user")
                with UserAgent.record(cassette):
                    replayed = await UserAgent().prompt("get the user")

        self.assertEqual(recorded.parsed, User(id="u-9", name="Sam"))
        self.assertEqual(replayed.parsed, User(id="u-9", name="Sam"))
