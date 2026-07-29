"""Integration tests: real prompt assembly, real tool execution, and real model
behaviour captured with the record/replay harness. The first run hits the live
API and writes the cassettes next to this file; every run after replays them.
"""

import json

from fastapi_startkit.ai import AssertToolCall
from fastapi_startkit.ai import state as ai_state
from fastapi_startkit.ai.testing import AgentRecordFake

from app.agents.agent import JobSearchAgent, JobSummarizerAgent
from app.agents.state import Context
from app.models.message import Message
from app.models.thread import Thread
from tests.test_case import TestCase

THREAD_ID = "integration-job-search"

JOBS = [
    {"id": 2, "title": "Python Developer", "location": "Remote", "company": "Startup Inc", "type": "Full-time"},
    {"id": 5, "title": "Product Manager", "location": "Remote", "company": "ProductHQ", "type": "Full-time"},
]


class TestJobSearchAgentIntegration(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        # The same seed every run: on the recording run it shapes the real prompt;
        # on replay runs the cassette answers and the rows are simply unused.
        await Thread.first_or_create({"id": THREAD_ID}, {"id": THREAD_ID})
        await Message.where("thread_id", THREAD_ID).delete()
        await Message.create(
            {
                "thread_id": THREAD_ID,
                "role": "user",
                "type": "text",
                "data": {"text": "I prefer fully remote roles."},
                "data_type": "string",
                "run_id": None,
            }
        )

    async def asyncTearDown(self):
        await Message.where("thread_id", THREAD_ID).delete()
        await Thread.where("id", THREAD_ID).delete()
        await super().asyncTearDown()

    def recorded_agent(self, contexts: list[Context]) -> AgentRecordFake:
        real = JobSearchAgent({"contexts": contexts}, {"configurable": {"thread_id": THREAD_ID}})
        return AgentRecordFake(real, "job_search_agent.json")

    async def test_searches_and_finds_roles_for_a_natural_query(self):
        with self.recorded_agent([Context.INCLUDE_USER_PROFILE]) as agent:
            response = await agent.prompt("find roles that fit me")

            def called_with_a_real_query(tool: AssertToolCall) -> bool:
                return tool.args.get("query", "").strip() != ""

            agent.assert_tool_called("job_search_tool", called_with_a_real_query)
            assert json.loads(ai_state.text(response)) != []
            agent.assert_tokens(lambda x: x.where("input", "<=", 20_000).where("output", "<=", 2_000))
            agent.assert_response_time_lt(30)

    async def test_always_searches_even_for_a_vague_query(self):
        with self.recorded_agent([Context.INCLUDE_USER_PROFILE]) as agent:
            response = await agent.prompt("suggest me jobs")

            # tool_choice="any": a text-only reply here would be a regression. The
            # recording run showed the model may send a blank query for vague asks,
            # which the tool now treats as "show the whole board".
            agent.assert_tool_called("job_search_tool")
            assert json.loads(ai_state.text(response)) != []


class TestJobSummarizerAgentIntegration(TestCase):
    async def test_summarizes_only_what_it_is_given(self):
        with JobSummarizerAgent.record("job_summarizer_agent.json") as agent:
            response = await agent.prompt(json.dumps(JOBS))

            agent.assert_text_response()
            assert "Python Developer" in ai_state.text(response)
            assert "Product Manager" in ai_state.text(response)
            await agent.assert_response_judged(
                provider="google",
                model="gemini-3.5-flash",
                expectation="A friendly summary of exactly two roles - Python Developer at Startup Inc and "
                "Product Manager at ProductHQ, both remote - inventing no other jobs.",
            )

    async def test_says_so_plainly_when_there_are_no_jobs(self):
        with JobSummarizerAgent.record("job_summarizer_agent.json") as agent:
            response = await agent.prompt(json.dumps([]))

            agent.assert_text_response()
            assert "Python Developer" not in ai_state.text(response)
