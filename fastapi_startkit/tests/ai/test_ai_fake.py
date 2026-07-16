"""Tests for Ai's fake-model registry.

Ai.fake() swaps the chat model a given agent (by class name or instance)
resolves to for a deterministic GenericFakeChatModel that replays a fixed
list of message turns — no live LLM call, no network access.
Ai().get_model_for(agent) is what Agent._build_model() calls: it returns
the registered fake when one exists, otherwise it builds a real provider
model exactly as Ai.build() always has.
"""

import unittest
from unittest import mock

import langchain.chat_models as chat_models
from langchain_core.messages import AIMessage, ToolCall
from langchain_core.tools import tool

from fastapi_startkit.ai.agent import Agent
from fastapi_startkit.ai.model_builder import Ai
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


class TestAiFakeBase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from fastapi_startkit.ai import AIConfig

        container = app()
        container.bind("ai", AIConfig())
        container.make("config").set("ai", AIConfig())
        self.addCleanup(Ai.reset_fakes)


class TestAiFakeRegistration(TestAiFakeBase):
    def test_fake_registers_a_model_for_an_agent_class_name(self):
        Ai.fake("SimpleAgent", [AIMessage(content="hi")])

        self.assertTrue(Ai.has_fake_model_for("SimpleAgent"))

    def test_fake_accepts_an_agent_instance_keyed_by_its_class_name(self):
        Ai.fake(SimpleAgent(), [AIMessage(content="hi")])

        self.assertTrue(Ai.has_fake_model_for(SimpleAgent()))
        self.assertTrue(Ai.has_fake_model_for("SimpleAgent"))

    def test_has_fake_model_for_is_false_when_nothing_registered(self):
        self.assertFalse(Ai.has_fake_model_for("SimpleAgent"))

    def test_fake_coerces_plain_strings_into_ai_messages(self):
        model = Ai.fake("SimpleAgent", ["plain text reply"])

        result = model.invoke([])

        self.assertEqual(result.content, "plain text reply")

    def test_fake_returns_the_registered_chat_model(self):
        model = Ai.fake("SimpleAgent", [AIMessage(content="hi")])

        self.assertIs(Ai.get_fake_model_for("SimpleAgent"), model)

    def test_forget_removes_a_single_registration(self):
        Ai.fake("SimpleAgent", [AIMessage(content="hi")])
        Ai.fake("JobAssistant", [AIMessage(content="hi")])

        Ai.forget("SimpleAgent")

        self.assertFalse(Ai.has_fake_model_for("SimpleAgent"))
        self.assertTrue(Ai.has_fake_model_for("JobAssistant"))

    def test_forget_is_a_no_op_when_nothing_registered(self):
        Ai.forget("SimpleAgent")

        self.assertFalse(Ai.has_fake_model_for("SimpleAgent"))


class TestAiGetModelFor(TestAiFakeBase):
    def test_returns_registered_fake_without_building_a_real_model(self):
        fake_model = Ai.fake("SimpleAgent", [AIMessage(content="faked")])

        def fail_if_called(*args, **kwargs):
            raise AssertionError("init_chat_model must not be called when a fake is registered")

        patcher = mock.patch.object(chat_models, "init_chat_model", fail_if_called)
        patcher.start()
        self.addCleanup(patcher.stop)

        resolved = Ai().get_model_for(SimpleAgent())

        self.assertIs(resolved, fake_model)

    def test_falls_back_to_build_when_no_fake_is_registered(self):
        sentinel = object()
        patcher = mock.patch.object(chat_models, "init_chat_model", lambda *a, **k: sentinel)
        patcher.start()
        self.addCleanup(patcher.stop)

        resolved = Ai().get_model_for(SimpleAgent())

        self.assertIs(resolved, sentinel)


class TestAgentPromptUsesFakeModelEndToEnd(TestAiFakeBase):
    async def test_prompt_replays_the_registered_fake_model_reply(self):
        Ai.fake("SimpleAgent", [AIMessage(content="faked via ai")])

        result = await SimpleAgent().prompt("hi there")

        self.assertEqual(result.content, "faked via ai")

    async def test_prompt_runs_a_faked_tool_call_end_to_end(self):
        Ai.fake(
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
        Ai.fake("SimpleAgent", [AIMessage(content="only for SimpleAgent")])

        self.assertFalse(Ai.has_fake_model_for("JobAssistant"))
