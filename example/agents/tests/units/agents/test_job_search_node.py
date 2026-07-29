import uuid

from fastapi_startkit.ai import Ai
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import END

from app.agents.agent import JobSearchAgent
from app.agents.job_search_graph import after_ask, ask_or_finish, build, job_search_node, route
from app.agents.state import Context, RouterOutput
from app.models.message import Message
from app.models.thread import Thread
from tests.support.fakes import tool_call_message
from tests.test_case import TestCase


def router_decision(**kwargs) -> AIMessage:
    """A faked structured-output turn: the runner parses the JSON content back
    into RouterOutput via the agent's schema()."""
    return AIMessage(content=RouterOutput(**kwargs).model_dump_json())


class TestJobSearchGraph(TestCase):
    """The whole graph, every LLM faked at the agent seam, real tool + real edges."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.addCleanup(Ai.reset_fakes)

    async def test_it_responds_to_greetings(self):
        Ai.fake("JobSearchRouterAgent", [router_decision(intent="chat", reply="hi, how are you doing")])

        graph = build().compile()
        out = await graph.ainvoke({"query": "hello"})

        assert out == {"type": "text", "data": "hi, how are you doing", "data_type": "string"}

    async def test_it_searches_and_summarizes(self):
        # A fake holds one scripted turn per graph run, consumed in order.
        Ai.fake(
            "JobSearchRouterAgent",
            [
                router_decision(intent="job_search"),
                router_decision(intent="chat", reply="Hello again! Ready for more roles?"),
            ],
        )
        Ai.fake("JobSearchAgent", [tool_call_message("python developer")])
        Ai.fake("JobSummarizerAgent", [AIMessage(content="One Python role, fully remote.")])

        graph = build().compile()

        response = await graph.ainvoke({"query": "find python jobs"})
        assert response == {"type": "text", "data": "One Python role, fully remote.", "data_type": "string"}

        response = await graph.ainvoke({"query": "Hello"})
        assert response == {"type": "text", "data": "Hello again! Ready for more roles?", "data_type": "string"}




class TestJobSearchNode(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.thread_id = f"test-{uuid.uuid4()}"
        self.config = {"configurable": {"thread_id": self.thread_id}}
        self.addCleanup(Ai.reset_fakes)

    async def asyncTearDown(self):
        await Message.where("thread_id", self.thread_id).delete()
        await Thread.where("id", self.thread_id).delete()
        await super().asyncTearDown()

    async def test_returns_matching_jobs_and_the_calls_it_made(self):
        Ai.fake("JobSearchAgent", [tool_call_message("python developer")])

        out = await job_search_node({"query": "find python jobs", "contexts": []}, self.config)

        assert out["type"] == "tool_response"
        assert out["data_type"] == "json"
        assert [job["title"] for job in out["data"]] == ["Python Developer"]
        assert out["tool_calls"] == [{"name": "job_search_tool", "args": {"query": "python developer"}}]

    async def test_returns_empty_data_when_nothing_matches(self):
        Ai.fake("JobSearchAgent", [tool_call_message("cobol mainframe antarctica")])

        out = await job_search_node({"query": "cobol roles?", "contexts": []}, self.config)

        assert out["data"] == []
        assert out["tool_calls"] == [{"name": "job_search_tool", "args": {"query": "cobol mainframe antarctica"}}]


class TestGraphRouting(TestCase):
    def test_route_sends_job_search_to_the_search_branch(self):
        assert route({"intent": "job_search"}) == "job_search"

    def test_route_ends_for_chat_and_unbuilt_branches(self):
        assert route({"intent": "chat"}) == END
        assert route({"intent": "company_research"}) == END

    def test_ask_or_finish_asks_only_when_empty_with_a_query(self):
        assert ask_or_finish({"data": [], "query": "python"}) == "ask_user"
        assert ask_or_finish({"data": [{"id": 1}], "query": "python"}) == END
        assert ask_or_finish({"data": [], "query": ""}) == END

    def test_after_ask_retries_with_a_reply_and_gives_up_on_blank(self):
        assert after_ask({"query": "python developer"}) == "job_search"
        assert after_ask({"query": ""}) == "job_summarizer"


class TestJobSearchAgentContext(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.thread_id = f"test-{uuid.uuid4()}"
        await Thread.first_or_create({"id": self.thread_id}, {"id": self.thread_id})

    async def asyncTearDown(self):
        await Message.where("thread_id", self.thread_id).delete()
        await Thread.where("id", self.thread_id).delete()
        await super().asyncTearDown()

    def agent(self, contexts: list[Context]) -> JobSearchAgent:
        return JobSearchAgent({"contexts": contexts}, {"configurable": {"thread_id": self.thread_id}})

    async def seed(self, role: str, type_: str, data: dict | list, data_type: str) -> None:
        await Message.create(
            {
                "thread_id": self.thread_id,
                "role": role,
                "type": type_,
                "data": data,
                "data_type": data_type,
                "run_id": None,
            }
        )

    async def test_loads_only_user_messages_as_history(self):
        await self.seed("user", "text", {"text": "remote only please"}, "string")
        await self.seed("ai", "text", {"text": "Got it."}, "string")

        messages = await self.agent([]).messages()

        assert [m.content for m in messages] == ["remote only please"]

    async def test_injects_the_profile_only_when_asked(self):
        assert await self.agent([]).messages() == []

        messages = await self.agent([Context.INCLUDE_USER_PROFILE]).messages()

        assert isinstance(messages[0], SystemMessage)
        assert "Alice" in messages[0].content

    async def test_injects_the_last_tool_response_only_when_asked(self):
        await self.seed("ai", "tool_response", [{"id": 2, "title": "Python Developer"}], "json")

        assert await self.agent([]).messages() == []

        messages = await self.agent([Context.INCLUDE_LAST_JOB_SEARCH_RESPONSE]).messages()

        assert len(messages) == 1
        assert "Python Developer" in messages[0].content
