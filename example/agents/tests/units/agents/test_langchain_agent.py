from dumpdie import dd
from langchain.agents import create_agent
from langchain_core.language_models import GenericFakeChatModel

from tests.test_case import TestCase


class Agent:
    async def prompt(self, input):
        from fastapi_startkit.application import app

        agent = create_agent(
            model=GenericFakeChatModel(messages=iter(["hello"])),
            system_prompt="You are a helpful assistant",
            checkpointer=await app().make("checkpointer"),
        )

        return await agent.ainvoke(
            {"messages": [{"role": "user", "content": "hello"}]}, {"configurable": {"thread_id": "1"}}
        )


class TestLangchainAgent(TestCase):
    async def test_the_router_agent(self):
        response = await Agent().prompt("hello")
        dd(response)
