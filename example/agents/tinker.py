import asyncio
import operator
from collections.abc import Callable
from typing import Annotated, TypedDict

from dumpdie import dump
from langchain.agents import create_agent
from langchain_core.messages import AnyMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.tools.job_search_tool import job_search_tool
from bootstrap.application import app  # NOQA


class ChatState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    llm_calls: int


agent = create_agent(
    model="google_genai:gemini-3.1-flash-lite",
    checkpointer=InMemorySaver(),
    tools=[job_search_tool],
)


async def prompt(message: str):
    config = {"configurable": {"thread_id": "1"}}
    return await agent.ainvoke(input={"messages": [{"role": "user", "content": message}]}, config=config)


class Agent:
    def __init__(self, prompt_handler=Callable):
        self.prompt_handler = prompt_handler

    async def prompt(self, message):
        pass

    async def ainvoke(self):
        await prompt(message="suggest me frontend developer jobs")


async def main():
    response = await prompt(message="Hello, world!")
    dump(response["messages"])
    response = await prompt(message="suggest me frontend developer jobs")
    dump(response["messages"])


asyncio.run(main())


# def test_it_can_prompt():
#     with Agent(prompt_handler=prompt) as agent:
#         agent.prompt("hi")  # hit the real end point for the first time, records the responses
#         agent.assert_prompted("hi")
#         agent.assert_prompt_judged(model="", expectation="")
#
#         agent.prompt("suggest me python developer jobs")  # hit for the first time and second records will be recorded
#         agent.assert_tool_called(
#             lambda tool: tool.name == "job_search_tool" and tool.args == {"query": "python developer jobs"}
#         )
