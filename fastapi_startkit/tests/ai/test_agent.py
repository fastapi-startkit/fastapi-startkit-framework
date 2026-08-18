import json
import re
import unittest
from typing import cast
from unittest import mock

import langchain.chat_models as chat_models
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, ToolCall
from langchain_core.outputs import ChatGenerationChunk
from langchain_core.tools import tool

from fastapi_startkit.ai import AIConfig, Document
from fastapi_startkit.ai import state as ai_state
from fastapi_startkit.ai.agent import Agent
from fastapi_startkit.ai.runner import Runner
from fastapi_startkit.ai.ai import Ai
from fastapi_startkit.application import app


class StreamingToolFake(GenericFakeChatModel):
    # GenericFakeChatModel can't stream tool calls; this emits tool-call chunks
    # so streamed-tool-result behaviour stays testable without a shared fakes module.
    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        message = cast(AIMessage, next(self.messages))
        content = message.content if isinstance(message.content, str) else str(message.content)
        for token in re.split(r"(\s)", content):
            if token:
                yield ChatGenerationChunk(message=AIMessageChunk(content=token, id=message.id))
        if message.tool_calls:
            chunks = [
                {"name": c["name"], "args": json.dumps(c.get("args", {})), "id": c.get("id"), "index": i}
                for i, c in enumerate(message.tool_calls)
            ]
            yield ChatGenerationChunk(message=AIMessageChunk(content="", tool_call_chunks=chunks, id=message.id))


@tool
def search_jobs(query: str) -> str:
    """Search the job board for roles matching the query."""
    return "Python Developer at Shopify"


class JobAssistant(Agent):
    def instructions(self):
        return "You help users find jobs."

    def tools(self):
        return [search_jobs]


class TestAgent(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        container = app()
        container.bind("ai", AIConfig())
        container.make("config").set("ai", AIConfig())

    def setup_agent(self, turns: list, agent_cls: type[Agent] = Agent):
        Ai.fake(agent_cls.__name__, turns)
        self.addCleanup(Ai.reset_fakes)

    async def test_prompt_returns_a_messages_state(self):
        self.setup_agent([AIMessage(content="hello back")])

        agent = Agent()
        result = await agent.prompt("hi there")

        self.assertIsInstance(result, dict)
        self.assertEqual([m.type for m in result["messages"]], ["human", "ai"])
        self.assertEqual(ai_state.text(result), "hello back")

    async def test_search_jobs_tool_returns_listing(self):
        self.setup_agent(
            [
                AIMessage(
                    content="",
                    tool_calls=[ToolCall(name="search_jobs", args={"query": "python"}, id="c1", type="tool_call")],
                ),
            ],
            JobAssistant,
        )

        result = await JobAssistant().prompt("find me a python job")

        self.assertEqual(ai_state.text(result), "Python Developer at Shopify")
        self.assertEqual([tc["name"] for tc in ai_state.tool_calls(result)], ["search_jobs"])

    async def test_prompt_maps_usage_metadata(self):
        self.setup_agent(
            [AIMessage(content="done", usage_metadata={"input_tokens": 11, "output_tokens": 7, "total_tokens": 18})]
        )

        result = await Agent().prompt("anything")

        self.assertEqual(ai_state.usage(result), {"input": 11, "output": 7})

    async def test_build_model_passes_langchain_provider_key(self):
        captured = {}

        def fake_init(model, **kwargs):
            captured["model"] = model
            captured["provider"] = kwargs.get("model_provider")
            return GenericFakeChatModel(messages=iter([AIMessage(content="ok")]))

        patcher = mock.patch.object(chat_models, "init_chat_model", fake_init)
        patcher.start()
        self.addCleanup(patcher.stop)

        class GoogleAgent(Agent):
            provider = "google"

        await GoogleAgent().prompt("hi")

        self.assertEqual(captured["provider"], "google_genai")
        self.assertEqual(captured["model"], "gemini-2.5-flash-lite")

    async def test_stream_yields_astream_events_shaped_events(self):
        self.setup_agent([AIMessage(content="streamed reply")])

        events = [event async for event in Agent().stream("hello")]

        kinds = [event["event"] for event in events]
        self.assertEqual(kinds[0], "on_chat_model_start")
        self.assertEqual(kinds[-1], "on_chat_model_end")
        self.assertTrue(all({"event", "name", "run_id", "data", "parent_ids"} <= set(e) for e in events))
        text = "".join(e["data"]["chunk"].text for e in events if e["event"] == "on_chat_model_stream")
        self.assertEqual(text, "streamed reply")

    async def test_middleware_streams_token_by_token_and_runs_after_hook(self):
        events: list = []

        class Logger:
            def handle(self, model, handler):
                events.append("before")
                return handler(model).then(lambda final: events.append("after"))

        class LoggedAgent(Agent):
            def middleware(self):
                return [Logger()]

        self.setup_agent([AIMessage(content="one two three")], LoggedAgent)

        stream = [event async for event in LoggedAgent().stream("hi")]
        chunks = [
            e["data"]["chunk"].text for e in stream if e["event"] == "on_chat_model_stream" and e["data"]["chunk"].text
        ]

        # Middleware must not buffer: the model's tokens arrive as separate chunks...
        self.assertEqual("".join(chunks), "one two three")
        self.assertGreater(len(chunks), 1)
        # ...and the after-hook fires exactly once, after the stream is drained.
        self.assertEqual(events, ["before", "after"])

    async def test_middleware_after_hook_runs_on_prompt(self):
        events: list = []

        class Logger:
            async def handle(self, model, handler):
                events.append("before")
                return handler(model).then(lambda final: events.append("after"))

        class LoggedAgent(Agent):
            def middleware(self):
                return [Logger()]

        self.setup_agent([AIMessage(content="done")], LoggedAgent)

        result = await LoggedAgent().prompt("hi")

        self.assertEqual(ai_state.text(result), "done")
        self.assertEqual(events, ["before", "after"])

    async def test_stream_yields_tool_result_without_calling_model_again(self):
        Ai._fakes["JobAssistant"] = StreamingToolFake(
            messages=iter(
                [
                    AIMessage(
                        content="",
                        tool_calls=[ToolCall(name="search_jobs", args={"query": "python"}, id="c1", type="tool_call")],
                    ),
                ]
            )
        )
        self.addCleanup(Ai.reset_fakes)

        events = [event async for event in JobAssistant().stream("find me a python job")]

        kinds = [event["event"] for event in events]
        # One model turn only — the tool result is not fed back for a second call.
        self.assertEqual(kinds.count("on_chat_model_start"), 1)
        self.assertEqual(kinds[-2:], ["on_tool_start", "on_tool_end"])
        tool_end = events[-1]
        self.assertEqual(tool_end["name"], "search_jobs")
        self.assertEqual(tool_end["data"]["output"].content, "Python Developer at Shopify")

    def test_resolve_model_falls_back_to_lab_default(self):
        self.assertEqual(Ai()._resolve_model(Agent()), "gemini-2.5-flash-lite")

        class AnthropicAgent(Agent):
            provider = "anthropic"

        self.assertEqual(Ai()._resolve_model(AnthropicAgent()), "claude-sonnet-4-6")

    def test_resolve_model_prefers_explicit_override(self):
        self.assertEqual(Ai()._resolve_model(Agent(), "my-model"), "my-model")

    async def test_instructions_lead_the_message_list(self):
        messages = await Runner(JobAssistant())._build_messages("find me a job")

        self.assertEqual(messages[0], {"role": "system", "content": "You help users find jobs."})
        self.assertEqual(sum(m.get("role") == "system" for m in messages), 1)

    async def test_instructions_can_be_a_method_override(self):
        class DynamicAgent(Agent):
            def instructions(self) -> str:
                return "Computed identity."

        messages = await Runner(DynamicAgent())._build_messages("hi")

        self.assertEqual(messages[0], {"role": "system", "content": "Computed identity."})

    async def test_no_instructions_prepends_no_system_message(self):
        messages = await Runner(Agent())._build_messages("hi")

        self.assertTrue(all(m.get("role") != "system" for m in messages))

    async def test_build_messages_inlines_text_attachment(self):
        doc = Document(content="Q3 revenue was $1.2M.", name="q3-report.txt")

        messages = await Runner(Agent())._build_messages("Summarise this report.", attachments=[doc])

        user_content = messages[-1]["content"]
        self.assertEqual(user_content[0], {"type": "text", "text": "Summarise this report."})
        self.assertEqual(user_content[1]["type"], "text")
        self.assertIn("q3-report.txt", user_content[1]["text"])

    async def test_build_messages_encodes_binary_attachment_as_file_block(self):
        doc = Document(content=b"%PDF-1.7 ...", name="q3.pdf", media_type="application/pdf")

        messages = await Runner(Agent())._build_messages("Summarise", attachments=[doc])

        block = messages[-1]["content"][1]
        self.assertEqual(block["type"], "file")
        self.assertEqual(block["mime_type"], "application/pdf")
        self.assertEqual(block["base64"], doc.to_base64())
