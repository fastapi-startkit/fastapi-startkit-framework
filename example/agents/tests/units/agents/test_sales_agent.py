from langgraph.checkpoint.memory import InMemorySaver

from app.agents.graph_agent import SalesAgent
from tests.test_case import TestCase


class AwaitableSaver:
    def __init__(self, saver):
        self._saver = saver

    def __await__(self):
        async def resolve():
            return self._saver

        return resolve().__await__()


class TestSalesAgent(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        from fastapi_startkit.application import app

        app().bind("checkpointer", AwaitableSaver(InMemorySaver()))

    async def test_sales_agent_replies(self):
        config = {"configurable": {"thread_id": "sales-1"}}
        with SalesAgent.record("record_sales.json") as agent:
            await agent.prompt("What plans do you offer?", config=config)

            agent.assert_prompt("plans")
            agent.assert_text_response()

    async def test_sales_agent_calls_the_job_search_tool(self):
        config = {"configurable": {"thread_id": "sales-2"}}
        with SalesAgent.record("basic_job_search.json") as agent:
            await agent.prompt("Suggest python developer jobs", config=config)

            agent.assert_prompt("python developer")
            agent.assert_tool_call("job_search_tool")

    async def test_sales_agent_streams_and_calls_the_tool(self):
        config = {"configurable": {"thread_id": "sales-3"}}
        with SalesAgent.record("stream_job_search.json") as agent:
            async for _ in agent.stream("Suggest python developer jobs", config=config):
                pass

            # Streaming now exposes the same structured response as prompt(),
            # so the fluent tool-call assertion works on the streamed run.
            agent.assert_prompt("python developer")
            agent.assert_tool_call("job_search_tool")
            agent.assert_text_response()
