import json

from fastapi_startkit.ai import Agent, Middleware
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool

from app.agents.job_search_graph import USER_PROFILE
from app.agents.state import Context, OverallState
from app.middleware.agent_logger import AgentLogger
from app.models.message import Message
from app.tools.job_search_tool import job_search_tool

JOB_SEARCH_PROMPT = """You find jobs for a user. ALWAYS call job_search_tool exactly once —
never reply with text only, and never ask clarifying questions.

Derive role/skill/location keywords from the LATEST user message only (e.g. 'python
developer remote'); it replaces any earlier search. Use earlier messages solely for
preferences like location or remote. Ignore filler words like 'suggest', 'me', 'jobs'.
If the latest message has no usable keywords, take them from the user's profile."""


class JobSearchAgent(Agent):
    """Plain single-LLM agent (like ChatAgent) that owns its own context: the thread's
    past user messages plus the user profile, injected only when the router asked for
    it via `contexts`. messages() is async — the runner awaits it.
    """

    # The model must search, never chat: text-only replies here would be discarded
    # by job_search_node (it only reads tool_events).
    tool_choice = "any"

    def __init__(self, state: OverallState, config: RunnableConfig | None = None):
        super().__init__()
        self.state = state
        self.thread_id = ((config or {}).get("configurable") or {}).get("thread_id", "")
        self.contexts: list[Context] = state.get("contexts") or []

    async def messages(self) -> list[BaseMessage]:
        messages: list[BaseMessage] = []

        if Context.INCLUDE_USER_PROFILE in self.contexts:
            messages.append(SystemMessage(content=f"User profile: {json.dumps(USER_PROFILE)}"))

        rows = await Message.where("thread_id", self.thread_id).where("role", "user").order_by("id").get()
        messages.extend(HumanMessage(content=row.data.get("text", "")) for row in rows)

        if Context.INCLUDE_LAST_JOB_SEARCH_RESPONSE in self.contexts and (last := await self._last_job_search()):
            messages.append(AIMessage(content=f"Previous job search results: {json.dumps(last.data)}"))

        return messages

    async def _last_job_search(self) -> Message | None:
        return (
            await Message.where("thread_id", self.thread_id)
            .where("role", "ai")
            .where("type", "tool_response")
            .order_by("id", "desc")
            .first()
        )

    def instructions(self) -> str:
        return JOB_SEARCH_PROMPT

    def middleware(self) -> list[Middleware]:
        return [AgentLogger()]

    def tools(self) -> list[BaseTool]:
        return [job_search_tool]
