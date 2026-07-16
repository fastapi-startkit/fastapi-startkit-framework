"""Tests for ModelBuilder's fake-model registry.

ModelBuilder.fake() swaps the chat model a given agent (by class name or
instance) resolves to for a deterministic GenericFakeChatModel that replays
a fixed list of message turns — no live LLM call, no network access.
ModelBuilder(agent=...).get_model_for() is what Agent._build_model() calls:
it returns the registered fake when one exists, otherwise it builds a real
provider model exactly as ModelBuilder.build() always has.
"""

import unittest
from unittest import mock

import langchain.chat_models as chat_models
from langchain_core.messages import AIMessage, ToolCall
from langchain_core.tools import tool

from fastapi_startkit.ai.agent import Agent
from fastapi_startkit.ai.model_builder import ModelBuilder
from fastapi_startkit.application import app


@tool
def search_jobs(query: str) -> str:
    """Search the job board for roles matching the query."""
    return "Python Developer at Shopify"


class JobAssistant(Agent):
    def tools(self):
        return [search_jobs]


class SimpleAgent(Agent):
    pass


class TestModelBuilderFakeBase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from fastapi_startkit.ai import AIConfig

        container = app()
        container.bind("ai", AIConfig())
        container.make("config").set("ai", AIConfig())
        self.addCleanup(ModelBuilder.reset_fakes)


class TestModelBuilderFakeRegistration(TestModelBuilderFakeBase):
    def test_fake_registers_a_model_for_an_agent_class_name(self):
        ModelBuilder.fake("SimpleAgent", [AIMessage(content="hi")])

        self.assertTrue(ModelBuilder.has_fake_model_for("SimpleAgent"))

    def test_fake_accepts_an_agent_instance_keyed_by_its_class_name(self):
        ModelBuilder.fake(SimpleAgent(), [AIMessage(content="hi")])

        self.assertTrue(ModelBuilder.has_fake_model_for(SimpleAgent()))
        self.assertTrue(ModelBuilder.has_fake_model_for("SimpleAgent"))

    def test_has_fake_model_for_is_false_when_nothing_registered(self):
        self.assertFalse(ModelBuilder.has_fake_model_for("SimpleAgent"))

    def test_fake_coerces_plain_strings_into_ai_messages(self):
        model = ModelBuilder.fake("SimpleAgent", ["plain text reply"])

        result = model.invoke([])

        self.assertEqual(result.content, "plain text reply")

    def test_fake_returns_the_registered_chat_model(self):
        model = ModelBuilder.fake("SimpleAgent", [AIMessage(content="hi")])

        self.assertIs(ModelBuilder.get_fake_model_for("SimpleAgent"), model)


class TestModelBuilderGetModelFor(TestModelBuilderFakeBase):
    def test_returns_registered_fake_without_building_a_real_model(self):
        fake_model = ModelBuilder.fake("SimpleAgent", [AIMessage(content="faked")])

        def fail_if_called(*args, **kwargs):
            raise AssertionError("init_chat_model must not be called when a fake is registered")

        patcher = mock.patch.object(chat_models, "init_chat_model", fail_if_called)
        patcher.start()
        self.addCleanup(patcher.stop)

        resolved = ModelBuilder(agent=SimpleAgent()).get_model_for()

        self.assertIs(resolved, fake_model)

    def test_falls_back_to_build_when_no_fake_is_registered(self):
        sentinel = object()
        patcher = mock.patch.object(chat_models, "init_chat_model", lambda *a, **k: sentinel)
        patcher.start()
        self.addCleanup(patcher.stop)

        resolved = ModelBuilder(agent=SimpleAgent()).get_model_for()

        self.assertIs(resolved, sentinel)


class TestAgentPromptUsesFakeModelEndToEnd(TestModelBuilderFakeBase):
    async def test_prompt_replays_the_registered_fake_model_reply(self):
        ModelBuilder.fake("SimpleAgent", [AIMessage(content="faked via model builder")])

        result = await SimpleAgent().prompt("hi there")

        self.assertEqual(result.content, "faked via model builder")

    async def test_prompt_runs_a_faked_tool_call_end_to_end(self):
        ModelBuilder.fake(
            "JobAssistant",
            [
                AIMessage(
                    content="",
                    tool_calls=[ToolCall(name="search_jobs", args={"query": "python"}, id="c1", type="tool_call")],
                )
            ],
        )

        result = await JobAssistant().prompt("find me a python job")

        self.assertEqual(result.content, "Python Developer at Shopify")

    async def test_registering_a_fake_does_not_affect_other_agent_classes(self):
        ModelBuilder.fake("SimpleAgent", [AIMessage(content="only for SimpleAgent")])

        self.assertFalse(ModelBuilder.has_fake_model_for("JobAssistant"))
