"""Structured output.

An Agent's schema() is appended to its tools() and the whole set is bound to
the model in a single payload via bind_tools([*tools, schema]). The model picks
per turn: a real tool call (which the Runner executes) or the schema as its
structured answer (which the Runner parses into response.parsed). If a
schema-only agent replies with plain JSON text instead of the tool call,
_apply_schema still parses it, so the structured result comes through either
way.

The fake/record paths bypass build(), so they keep parsing the JSON-string
content via schema() for deterministic replay.
"""

import unittest
from unittest import mock

import langchain.chat_models as chat_models
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from pydantic import BaseModel

from fastapi_startkit.ai import AIConfig
from fastapi_startkit.ai.agent import Agent
from fastapi_startkit.ai.ai import Ai
from fastapi_startkit.ai.runner import Runner
from fastapi_startkit.application import app


class Movie(BaseModel):
    title: str
    year: int


class MovieAgent(Agent):
    def schema(self):
        return Movie


@tool
def noop(query: str) -> str:
    """A no-op tool that echoes its query."""
    return query


class ToolMovieAgent(Agent):
    def schema(self):
        return Movie

    def tools(self):
        return [noop]


def _schema_tool_call(**args) -> dict:
    return {"name": "Movie", "args": args, "id": "1", "type": "tool_call"}


def _real_tool_call(**args) -> dict:
    return {"name": "noop", "args": args, "id": "2", "type": "tool_call"}


class TestBuild(unittest.TestCase):
    def setUp(self):
        container = app()
        container.bind("ai", AIConfig())
        container.make("config").set("ai", AIConfig())

    def tearDown(self):
        Ai.reset_fakes()

    def _patch_init(self, fake):
        patcher = mock.patch.object(chat_models, "init_chat_model", lambda *a, **k: fake)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _fake_model(self):
        class FakeModel:
            bound = None

            def bind_tools(self, tools, **kwargs):
                self.bound = list(tools)
                return "BOUND"

        fake = FakeModel()
        self._patch_init(fake)
        return fake

    def test_schema_and_tools_are_bound_together_in_one_payload(self):
        fake = self._fake_model()

        result = Ai().build(ToolMovieAgent())

        self.assertEqual(result, "BOUND")
        self.assertEqual(fake.bound, [noop, Movie])

    def test_schema_only_binds_the_schema_as_a_tool(self):
        fake = self._fake_model()

        result = Ai().build(MovieAgent())

        self.assertEqual(result, "BOUND")
        self.assertEqual(fake.bound, [Movie])

    def test_tools_only_binds_just_the_tools(self):
        fake = self._fake_model()

        class ToolAgent(Agent):
            def tools(self):
                return [noop]

        result = Ai().build(ToolAgent())

        self.assertEqual(result, "BOUND")
        self.assertEqual(fake.bound, [noop])

    def test_streaming_drops_the_schema_from_the_payload(self):
        fake = self._fake_model()

        result = Ai().build(ToolMovieAgent(), structured=False)

        self.assertEqual(result, "BOUND")
        self.assertEqual(fake.bound, [noop])

    def test_no_schema_no_tools_returns_the_plain_model(self):
        fake = self._fake_model()

        self.assertIs(Ai().build(Agent()), fake)


class TestRunner(unittest.IsolatedAsyncioTestCase):
    async def test_returns_structured_when_model_calls_the_schema(self):
        class Model:
            async def ainvoke(self, messages):
                return AIMessage(content="", tool_calls=[_schema_tool_call(title="Inception", year=2010)])

        result = await Runner(ToolMovieAgent(), Model()).run(["hi"])

        self.assertEqual(result["parsed"], Movie(title="Inception", year=2010))

    async def test_runs_the_tool_when_model_calls_a_real_tool(self):
        class Model:
            async def ainvoke(self, messages):
                return AIMessage(content="", tool_calls=[_real_tool_call(query="hello")])

        result = await Runner(ToolMovieAgent(), Model()).run(["hi"])

        self.assertEqual(result.content, "hello")


class TestResponseMapping(unittest.TestCase):
    def test_unwraps_include_raw_into_parsed_and_content(self):
        parsed = Movie(title="Inception", year=2010)
        raw = AIMessage(content="", tool_calls=[_schema_tool_call(title="Inception", year=2010)])

        response = MovieAgent()._to_agent_response({"raw": raw, "parsed": parsed, "parsing_error": None})

        self.assertIs(response.parsed, parsed)
        self.assertEqual(response.content, parsed.model_dump_json())
        self.assertEqual(response.tool_calls, [])


class TestPromptEndToEnd(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        container = app()
        container.bind("ai", AIConfig())
        container.make("config").set("ai", AIConfig())

    def tearDown(self):
        Ai.reset_fakes()

    def _patch(self, model):
        patcher = mock.patch.object(chat_models, "init_chat_model", lambda *a, **k: model)
        patcher.start()
        self.addCleanup(patcher.stop)

    async def test_schema_only_populates_parsed_from_the_schema_tool_call(self):
        class FakeModel:
            def bind_tools(self, tools, **kwargs):
                return self

            async def ainvoke(self, messages):
                return AIMessage(content="", tool_calls=[_schema_tool_call(title="Inception", year=2010)])

        self._patch(FakeModel())

        response = await MovieAgent().prompt("best nolan movie")

        self.assertEqual(response.parsed, Movie(title="Inception", year=2010))

    async def test_schema_only_parses_plain_json_text_when_model_skips_the_tool(self):
        class FakeModel:
            def bind_tools(self, tools, **kwargs):
                return self

            async def ainvoke(self, messages):
                return AIMessage(content='{"title": "Inception", "year": 2010}')

        self._patch(FakeModel())

        response = await MovieAgent().prompt("best nolan movie")

        self.assertEqual(response.parsed, Movie(title="Inception", year=2010))

    async def test_schema_plus_tools_returns_structured_when_model_chooses_it(self):
        class FakeModel:
            def bind_tools(self, tools, **kwargs):
                return self

            async def ainvoke(self, messages):
                return AIMessage(content="", tool_calls=[_schema_tool_call(title="Inception", year=2010)])

        self._patch(FakeModel())

        response = await ToolMovieAgent().prompt("best nolan movie")

        self.assertEqual(response.parsed, Movie(title="Inception", year=2010))
        self.assertEqual(response.tool_calls, [])

    async def test_schema_plus_tools_runs_the_tool_when_model_chooses_it(self):
        class FakeModel:
            def bind_tools(self, tools, **kwargs):
                return self

            async def ainvoke(self, messages):
                return AIMessage(content="", tool_calls=[_real_tool_call(query="hello")])

        self._patch(FakeModel())

        response = await ToolMovieAgent().prompt("run the tool")

        self.assertIsNone(response.parsed)
        self.assertEqual(response.content, "hello")
