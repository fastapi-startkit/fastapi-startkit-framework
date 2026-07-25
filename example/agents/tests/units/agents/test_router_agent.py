from fastapi_startkit.ai import AssertToolCall
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.chat import ChatAgent
from tests.test_case import TestCase


class TestRouterAgent(TestCase):
    async def test_the_router_agent(self):
        with ChatAgent.record("record_stream.json") as agent:
            await agent.prompt("hello")
            agent.assert_text_response()
            agent.assert_tool_not_called(["job_search_tool"])

            agent.assert_response_time_lt(5)

            def assert_tool_calls(tool: AssertToolCall):
                return tool.name == "job_search_tool"

            await agent.prompt("suggest python developer jobs")
            agent.assert_tool_called("job_search_tool", assert_tool_calls)

            # Tokens accumulate across both turns of the session.
            agent.assert_tokens(lambda x: x.where("input", "<=", 5000).where("output", "<=", 5000))

    async def test_the_router_with_initial_messages(self):
        with ChatAgent.record(
            "record_stream.json",
            messages=[
                HumanMessage(content="Hi"),
                AIMessage(content="Hello, How can I help you?"),
            ],
        ) as agent:
            await agent.prompt("suggest python developer jobs")
            agent.assert_tool_called("job_search_tool", lambda tool: tool.name == "job_search_tool")
