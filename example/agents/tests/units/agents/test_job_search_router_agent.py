"""Unit tests for JobSearchRouterAgent — classifies a query into a RouterOutput.

The model is faked, so these pin the agent's contract (structured-output schema,
its ROUTER_PROMPT instructions, and how the JSON is parsed into a RouterOutput)
and its remember() rule — a chat reply is conversation and is persisted, a
routing decision is not. They do not exercise the live model's judgement; the
model's own classification quality is covered by the recorded integration tests.
"""

import json
import unittest
from unittest import mock

from fastapi_startkit.ai import state as ai_state

from app.agents.agent import ROUTER_PROMPT, JobSearchRouterAgent
from app.agents.state import Context, RouterOutput


def _decision(intent: str, contexts: list[str] | None = None, reply: str = "") -> str:
    return json.dumps({"intent": intent, "contexts": contexts or [], "reply": reply})


class TestJobSearchRouterAgent(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # The AgentLogger middleware logs through the framework Logger, which needs
        # a booted container. These tests exercise classification, not logging, so
        # run the agent without middleware.
        patcher = mock.patch.object(JobSearchRouterAgent, "middleware", lambda self: [])
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_uses_the_router_prompt_and_router_output_schema(self):
        agent = JobSearchRouterAgent()
        self.assertIs(agent.schema(), RouterOutput)
        self.assertEqual(agent.instructions(), ROUTER_PROMPT)

    async def test_a_vague_job_ask_parses_into_a_job_search_decision(self):
        with JobSearchRouterAgent.fake([_decision("job_search", ["include_user_profile"])]) as agent:
            response = await agent.prompt("any jobs")

        decision = ai_state.structured(response)
        self.assertEqual(decision.intent, "job_search")
        self.assertIn(Context.INCLUDE_USER_PROFILE, decision.contexts)
        self.assertEqual(decision.reply, "")

    async def test_a_greeting_parses_into_a_chat_decision_with_an_inline_reply(self):
        with JobSearchRouterAgent.fake([_decision("chat", reply="Hi! How can I help with your job search?")]) as agent:
            response = await agent.prompt("hi")

        decision = ai_state.structured(response)
        self.assertEqual(decision.intent, "chat")
        self.assertTrue(decision.reply)

    async def test_remembers_a_chat_reply_but_not_a_routing_decision(self):
        agent = JobSearchRouterAgent(config={"configurable": {"thread_id": "router-test"}})
        with mock.patch.object(agent, "remember_row", new=mock.AsyncMock()) as row:
            with JobSearchRouterAgent.fake([_decision("chat", reply="Hello!")]):
                await agent.prompt("hi")
            row.assert_awaited_once()  # a chat reply is conversation -> persisted

            row.reset_mock()
            with JobSearchRouterAgent.fake([_decision("job_search", ["include_user_profile"])]):
                await agent.prompt("any jobs")
            row.assert_not_awaited()  # a routing decision is state, not conversation
