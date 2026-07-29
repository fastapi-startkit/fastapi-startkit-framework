import asyncio

from dumpdie import dd
from langchain.agents import create_agent
from langchain_core.tools import tool

from app.agents.agent import JobSearchAgent
from bootstrap.application import app  # NOQA


@tool(description="Use this tool to search for jobs", return_direct=True)
def job_search_tool(query: str):
    return []


async def main():
    responses = await JobSearchAgent().prompt("suggest me python developer jobs")
    dd(responses)


asyncio.run(main())
#
# agent = create_agent(model="google_genai:gemini-3.1-flash-lite", tools=[job_search_tool])
#
# # agent.invoke({"messages": [{"role": "user", "content": "hi"}]})
#
# responses = agent.invoke(
#     {"messages": [{"role": "user", "content": "suggest me python developer jobs"}]}
# )
# dd(responses)
