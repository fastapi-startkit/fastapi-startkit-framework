"""Structured output.

When an Agent declares a schema(), the built model is wrapped with
model.with_structured_output(schema, include_raw=True) so the provider returns
the parsed object. Tools are bound as usual and left untouched. The wrapped
model yields {"raw", "parsed", "parsing_error"}; the Runner passes that through
and _to_agent_response unwraps it into response.parsed.

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


def _real_tool_call(**args) -> dict:
    return {"name": "noop", "args": args, "id": "1", "type": "tool_call"}


class _FakeModel:
    """Records the build calls made against it."""

    def __init__(self):
        self.calls = []

    def bind_tools(self, tools, **kwargs):
        self.calls.append(("bind_tools", list(tools)))
        return self

    def with_structured_output(self, schema, **kwargs):
        self.calls.append(("with_structured_output", schema, kwargs))
        return "STRUCTURED"


class TestBuild(unittest.TestCase):
    def setUp(self):
        container = app()
        container.bind("ai", AIConfig())
        container.make("config").set("ai", AIConfig())

    def tearDown(self):
        Ai.reset_fakes()

    def _patch(self, fake):
        patcher = mock.patch.object(chat_models, "init_chat_model", lambda *a, **k: fake)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_schema_wraps_model_with_structured_output(self):
        fake = _FakeModel()
        self._patch(fake)

        result = Ai().build(MovieAgent())

        self.assertEqual(result, "STRUCTURED")
        self.assertEqual(fake.calls, [("with_structured_output", Movie, {"include_raw": True})])

    def test_tools_are_bound_then_structured_output_is_applied(self):
        fake = _FakeModel()
        self._patch(fake)

        result = Ai().build(ToolMovieAgent())

        self.assertEqual(result, "STRUCTURED")
        self.assertEqual(
            fake.calls,
            [("bind_tools", [noop]), ("with_structured_output", Movie, {"include_raw": True})],
        )

    def test_tools_only_binds_tools_without_structured_output(self):
        fake = _FakeModel()
        self._patch(fake)

        class ToolAgent(Agent):
            def tools(self):
                return [noop]

        result = Ai().build(ToolAgent())

        self.assertIs(result, fake)
        self.assertEqual(fake.calls, [("bind_tools", [noop])])

    def test_streaming_skips_structured_output(self):
        fake = _FakeModel()
        self._patch(fake)

        result = Ai().build(ToolMovieAgent(), structured=False)

        self.assertIs(result, fake)
        self.assertEqual(fake.calls, [("bind_tools", [noop])])

    def test_no_schema_no_tools_returns_the_plain_model(self):
        fake = _FakeModel()
        self._patch(fake)

        self.assertIs(Ai().build(Agent()), fake)
        self.assertEqual(fake.calls, [])


class TestRunner(unittest.IsolatedAsyncioTestCase):
    async def test_passes_structured_output_dict_through(self):
        parsed = Movie(title="Inception", year=2010)
        payload = {"raw": AIMessage(content=""), "parsed": parsed, "parsing_error": None}

        class Model:
            async def ainvoke(self, messages):
                return payload

        result = await Runner(MovieAgent(), Model()).run(["hi"])

        self.assertEqual(result, payload)

    async def test_runs_the_tool_when_model_calls_a_real_tool(self):
        class Model:
            async def ainvoke(self, messages):
                return AIMessage(content="", tool_calls=[_real_tool_call(query="hello")])

        result = await Runner(ToolMovieAgent(), Model()).run(["hi"])

        self.assertEqual(result.content, "hello")


class TestResponseMapping(unittest.TestCase):
    def test_unwraps_include_raw_into_parsed_and_content(self):
        parsed = Movie(title="Inception", year=2010)

        response = MovieAgent()._to_agent_response(
            {"raw": AIMessage(content=""), "parsed": parsed, "parsing_error": None}
        )

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

    async def test_prompt_populates_parsed_via_structured_output(self):
        parsed = Movie(title="Inception", year=2010)

        class Structured:
            async def ainvoke(self, messages):
                return {"raw": AIMessage(content=""), "parsed": parsed, "parsing_error": None}

        class FakeModel:
            def with_structured_output(self, schema, **kwargs):
                return Structured()

        patcher = mock.patch.object(chat_models, "init_chat_model", lambda *a, **k: FakeModel())
        patcher.start()
        self.addCleanup(patcher.stop)

        response = await MovieAgent().prompt("best nolan movie")

        self.assertEqual(response.parsed, parsed)
        self.assertEqual(response.content, parsed.model_dump_json())
