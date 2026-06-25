import asyncio

from dumpdie import dd
from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langchain_protocol import ToolCall

from bootstrap.application import app  # noqa


@tool
def search_jobs(query: str):
    """Tools to perform searches on the jobs"""
    mock_db = [
        {"title": "Python Developer", "company": "Shopify", "location": "Remote"},
        {"title": "Senior Backend Engineer", "company": "Amazon", "location": "Vancouver"},
        {"title": "Data Engineer", "company": "Google", "location": "Remote"},
    ]

    # very naive filter for POC
    return [job for job in mock_db if query.lower() in job["title"].lower()] or mock_db


class Agent:
    def fake(self, messages: dict[str|ToolCall, AIMessage] | None = None):
        model = GenericFakeChatModel(
            messages=iter(
                [
                    "Hello",
                    AIMessage(content="", tool_calls=[ToolCall(name="foo", args={"bar": "baz"}, id="call_1")]),
                    "bar",
                ]
            )
        )

        return model.invoke("hello")
        # AIMessage(content='', ..., tool_calls=[{'name': 'foo', 'args': {'bar': 'baz'}, 'id': 'call_1', 'type': 'tool_call'}])

    async def prompt(self):
        agent = create_agent(
            model="google_genai:gemini-2.5-flash-lite",
            system_prompt="You are a helpful assistant",
            tools=[search_jobs],
        )

        return await agent.ainvoke({"messages": [{"role": "user", "content": "Find me a job for Python developer"}]})


Agent().fake([
{
        "**hi**": AIMessage(content="hi, how are you doing?"),
        "**Find me a Job for Python developer**": AIMessage(
            content="", tool_calls=[ToolCall(name="foo", args={"bar": "baz"}, id="call_1", type="tool_call")]
        ),
        ToolCall(name="foo", args={"bar": "baz"}, id="call_1", type="tool_call"): AIMessage(content=""),
    }
])

# Tool.fake({"search_jobs", [{"title": "Senior Python Developer"}]})
dd(asyncio.run(Agent().prompt()))
Agent().record()
