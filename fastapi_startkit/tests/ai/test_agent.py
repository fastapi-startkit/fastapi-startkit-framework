import unittest
from unittest import mock

import langchain.chat_models as chat_models
from langchain_core.messages import AIMessage, ToolCall
from langchain_core.tools import tool

from fastapi_startkit.ai import AIConfig, Document, fake_chat_model
from fastapi_startkit.ai.agent import Agent
from fastapi_startkit.ai.ai import Ai
from fastapi_startkit.ai.response import AgentResponse
from fastapi_startkit.application import app


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

    def setup_agent(self, turns: list[AIMessage]):
        model = fake_chat_model(turns)
        patcher = mock.patch.object(chat_models, "init_chat_model", lambda *a, **k: model)
        patcher.start()
        self.addCleanup(patcher.stop)
        return model

    async def test_prompt_returns_agent_response(self):
        self.setup_agent([AIMessage(content="hello back")])

        agent = Agent()
        result = await agent.prompt("hi there")

        self.assertIsInstance(result, AgentResponse)
        self.assertEqual(result.content, "hello back")
        agent.assert_prompted()

    async def test_search_jobs_tool_returns_listing(self):
        self.setup_agent(
            [
                AIMessage(
                    content="",
                    tool_calls=[ToolCall(name="search_jobs", args={"query": "python"}, id="c1", type="tool_call")],
                ),
            ]
        )

        result = await JobAssistant().prompt("find me a python job")

        self.assertEqual(result.content, "Python Developer at Shopify")
        self.assertEqual(result.tool_calls, [])

    async def test_prompt_maps_usage_metadata(self):
        self.setup_agent(
            [AIMessage(content="done", usage_metadata={"input_tokens": 11, "output_tokens": 7, "total_tokens": 18})]
        )

        result = await Agent().prompt("anything")

        self.assertEqual(result.usage, {"input": 11, "output": 7})

    async def test_build_model_passes_langchain_provider_key(self):
        captured = {}

        def fake_init(model, **kwargs):
            captured["model"] = model
            captured["provider"] = kwargs.get("model_provider")
            return fake_chat_model([AIMessage(content="ok")])

        patcher = mock.patch.object(chat_models, "init_chat_model", fake_init)
        patcher.start()
        self.addCleanup(patcher.stop)

        class GoogleAgent(Agent):
            provider = "google"

        await GoogleAgent().prompt("hi")

        self.assertEqual(captured["provider"], "google_genai")
        self.assertEqual(captured["model"], "gemini-2.5-flash-lite")

    async def test_stream_yields_tokens_from_the_model(self):
        self.setup_agent([AIMessage(content="streamed reply")])

        chunks = [chunk async for chunk in Agent().stream("hello")]

        self.assertEqual("".join(chunks), "streamed reply")

    async def test_middleware_streams_token_by_token_and_runs_after_hook(self):
        self.setup_agent([AIMessage(content="one two three")])

        events: list = []

        class Logger:
            def handle(self, model, handler):
                events.append("before")
                return handler(model).then(lambda final: events.append("after"))

        class LoggedAgent(Agent):
            def middleware(self):
                return [Logger()]

        chunks = [chunk async for chunk in LoggedAgent().stream("hi")]

        # Middleware must not buffer: the model's tokens arrive as separate chunks...
        self.assertEqual("".join(chunks), "one two three")
        self.assertGreater(len(chunks), 1)
        # ...and the after-hook fires exactly once, after the stream is drained.
        self.assertEqual(events, ["before", "after"])

    async def test_middleware_after_hook_runs_on_prompt(self):
        self.setup_agent([AIMessage(content="done")])

        events: list = []

        class Logger:
            async def handle(self, model, handler):
                events.append("before")
                return handler(model).then(lambda final: events.append("after"))

        class LoggedAgent(Agent):
            def middleware(self):
                return [Logger()]

        result = await LoggedAgent().prompt("hi")

        self.assertEqual(result.content, "done")
        self.assertEqual(events, ["before", "after"])

    async def test_stream_yields_tool_result_without_calling_model_again(self):
        self.setup_agent(
            [
                AIMessage(
                    content="",
                    tool_calls=[ToolCall(name="search_jobs", args={"query": "python"}, id="c1", type="tool_call")],
                ),
            ]
        )

        chunks = [chunk async for chunk in JobAssistant().stream("find me a python job")]

        self.assertEqual(chunks, ["Python Developer at Shopify"])

    def test_resolve_model_falls_back_to_lab_default(self):
        self.assertEqual(Ai()._resolve_model(Agent()), "gemini-2.5-flash-lite")

        class AnthropicAgent(Agent):
            provider = "anthropic"

        self.assertEqual(Ai()._resolve_model(AnthropicAgent()), "claude-sonnet-4-6")

    def test_resolve_model_prefers_explicit_override(self):
        self.assertEqual(Ai()._resolve_model(Agent(), "my-model"), "my-model")

    def test_instructions_lead_the_message_list(self):
        messages = JobAssistant()._build_messages("find me a job")

        self.assertEqual(messages[0], {"role": "system", "content": "You help users find jobs."})
        self.assertEqual(sum(m.get("role") == "system" for m in messages), 1)

    def test_instructions_can_be_a_method_override(self):
        class DynamicAgent(Agent):
            def instructions(self) -> str:
                return "Computed identity."

        messages = DynamicAgent()._build_messages("hi")

        self.assertEqual(messages[0], {"role": "system", "content": "Computed identity."})

    def test_no_instructions_prepends_no_system_message(self):
        messages = Agent()._build_messages("hi")

        self.assertTrue(all(m.get("role") != "system" for m in messages))

    def test_build_messages_inlines_text_attachment(self):
        doc = Document(content="Q3 revenue was $1.2M.", name="q3-report.txt")

        messages = Agent()._build_messages("Summarise this report.", attachments=[doc])

        user_content = messages[-1]["content"]
        self.assertEqual(user_content[0], {"type": "text", "text": "Summarise this report."})
        self.assertEqual(user_content[1]["type"], "text")
        self.assertIn("q3-report.txt", user_content[1]["text"])

    def test_build_messages_encodes_binary_attachment_as_file_block(self):
        doc = Document(content=b"%PDF-1.7 ...", name="q3.pdf", media_type="application/pdf")

        messages = Agent()._build_messages("Summarise", attachments=[doc])

        block = messages[-1]["content"][1]
        self.assertEqual(block["type"], "file")
        self.assertEqual(block["mime_type"], "application/pdf")
        self.assertEqual(block["base64"], doc.to_base64())
