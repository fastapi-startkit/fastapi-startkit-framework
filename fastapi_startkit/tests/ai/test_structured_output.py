"""Structured output.

An Agent's schema() and tools() are passed to the model in a single payload:

- schema + tools -> bind_tools([*tools, schema]); the model picks a real tool
  call OR the schema as its structured answer. If it picks the schema, we parse
  and return the structured result; otherwise we run the tool it asked for.
- schema only -> with_structured_output(); the shape is enforced.
- tools only / neither -> unchanged.

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
            structured = None

            def bind_tools(self, tools, **kwargs):
                self.bound = list(tools)
                return "BOUND"

            def with_structured_output(self, schema, **kwargs):
                self.structured = (schema, kwargs)
                return "STRUCTURED"

        fake = FakeModel()
        self._patch_init(fake)
        return fake

    def test_schema_and_tools_are_bound_together_in_one_payload(self):
        fake = self._fake_model()

        result = Ai().build(ToolMovieAgent())

        self.assertEqual(result, "BOUND")
        self.assertIn(noop, fake.bound)
        self.assertIn(Movie, fake.bound)

    def test_schema_only_uses_enforced_structured_output(self):
        fake = self._fake_model()

        result = Ai().build(MovieAgent())

        self.assertEqual(result, "STRUCTURED")
        self.assertEqual(fake.structured, (Movie, {"include_raw": True}))

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

    async def test_passes_structured_output_dict_through(self):
        parsed = Movie(title="Inception", year=2010)
        payload = {"raw": AIMessage(content=""), "parsed": parsed, "parsing_error": None}

        class Model:
            async def ainvoke(self, messages):
                return payload

        result = await Runner(MovieAgent(), Model()).run(["hi"])

        self.assertEqual(result, payload)


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

    async def test_schema_only_populates_parsed(self):
        parsed = Movie(title="Inception", year=2010)

        class Structured:
            async def ainvoke(self, messages):
                return {"raw": AIMessage(content=""), "parsed": parsed, "parsing_error": None}

        class FakeModel:
            def with_structured_output(self, schema, **kwargs):
                return Structured()

        self._patch(FakeModel())

        response = await MovieAgent().prompt("best nolan movie")

        self.assertEqual(response.parsed, parsed)
        self.assertEqual(response.content, parsed.model_dump_json())

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
