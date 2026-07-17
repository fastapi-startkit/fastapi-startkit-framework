"""Structured output: when an Agent declares a schema() and has no tools, the
model is built with with_structured_output() so the provider enforces the
shape, rather than relying on prompt instructions + post-hoc JSON parsing.
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
    """A no-op tool."""
    return query


class ToolMovieAgent(Agent):
    def schema(self):
        return Movie

    def tools(self):
        return [noop]


def _structured_payload(parsed: Movie) -> dict:
    raw = AIMessage(content="", tool_calls=[{"name": "Movie", "args": {}, "id": "1", "type": "tool_call"}])
    return {"raw": raw, "parsed": parsed, "parsing_error": None}


class TestBuildStructuredOutput(unittest.TestCase):
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

    def test_wraps_with_structured_output_when_schema_and_no_tools(self):
        captured = {}

        class FakeModel:
            def with_structured_output(self, schema, **kwargs):
                captured["schema"] = schema
                captured["kwargs"] = kwargs
                return "STRUCTURED"

            def bind_tools(self, tools, **kwargs):
                return "BOUND"

        self._patch_init(FakeModel())

        result = Ai().build(MovieAgent())

        self.assertEqual(result, "STRUCTURED")
        self.assertIs(captured["schema"], Movie)
        self.assertEqual(captured["kwargs"], {"include_raw": True})

    def test_tools_take_precedence_over_structured_output(self):
        class FakeModel:
            def with_structured_output(self, schema, **kwargs):
                return "STRUCTURED"

            def bind_tools(self, tools, **kwargs):
                return "BOUND"

        self._patch_init(FakeModel())

        self.assertEqual(Ai().build(ToolMovieAgent()), "BOUND")

    def test_structured_false_returns_the_plain_model(self):
        class FakeModel:
            def with_structured_output(self, schema, **kwargs):
                return "STRUCTURED"

            def bind_tools(self, tools, **kwargs):
                return "BOUND"

        fake = FakeModel()
        self._patch_init(fake)

        self.assertIs(Ai().build(MovieAgent(), structured=False), fake)

    def test_no_schema_no_tools_returns_the_plain_model(self):
        class FakeModel:
            def with_structured_output(self, schema, **kwargs):
                return "STRUCTURED"

            def bind_tools(self, tools, **kwargs):
                return "BOUND"

        fake = FakeModel()
        self._patch_init(fake)

        self.assertIs(Ai().build(Agent()), fake)


class TestStructuredResponseMapping(unittest.TestCase):
    def test_unwraps_include_raw_and_sets_parsed(self):
        parsed = Movie(title="Inception", year=2010)

        response = MovieAgent()._to_agent_response(_structured_payload(parsed))

        self.assertIs(response.parsed, parsed)
        self.assertEqual(response.content, parsed.model_dump_json())

    def test_suppresses_the_synthetic_structured_output_tool_call(self):
        parsed = Movie(title="Inception", year=2010)

        response = MovieAgent()._to_agent_response(_structured_payload(parsed))

        self.assertEqual(response.tool_calls, [])


class TestRunnerStructuredOutput(unittest.IsolatedAsyncioTestCase):
    async def test_runner_passes_structured_dict_through_without_running_tools(self):
        parsed = Movie(title="Inception", year=2010)
        payload = _structured_payload(parsed)

        class Model:
            async def ainvoke(self, messages):
                return payload

        result = await Runner(MovieAgent(), Model()).run(["hi"])

        self.assertEqual(result, payload)


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

            def bind_tools(self, tools, **kwargs):
                return self

        patcher = mock.patch.object(chat_models, "init_chat_model", lambda *a, **k: FakeModel())
        patcher.start()
        self.addCleanup(patcher.stop)

        response = await MovieAgent().prompt("best nolan movie")

        self.assertEqual(response.parsed, parsed)
        self.assertEqual(response.content, parsed.model_dump_json())
