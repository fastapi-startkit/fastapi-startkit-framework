import json

from fastapi_startkit.ai import Middleware
from fastapi_startkit.ai import state as ai_state
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

from app.agents.job_search_graph import USER_PROFILE
from app.agents.remember import RememberMixin, ThreadAgent
from app.agents.state import Context, RouterOutput
from app.middleware.agent_logger import AgentLogger
from app.models.message import Message
from app.tools.job_search_tool import job_search_tool

JOB_SEARCH_PROMPT = """You find jobs for a user. ALWAYS call job_search_tool exactly once —
never reply with text only, and never ask clarifying questions.

Derive role/skill/location keywords from the LATEST user message only (e.g. 'python
developer remote'); it replaces any earlier search. Use earlier messages solely for
preferences like location or remote. Ignore filler words like 'suggest', 'me', 'jobs'.
If the latest message has no usable keywords, take them from the user's profile."""

SUMMARIZER_PROMPT = """Write a short, friendly summary of these job listings for the user.
Group by role type, mention company and location. If the list is empty, say so plainly.
Use only what is given - do not invent jobs."""

ROUTER_PROMPT = """You route a career assistant's queries.

- job_search: the user wants job listings / openings / roles.
- company_research: the user asks about a specific company.
- chat: greetings (hi / hello), thanks, small talk, or anything conversational.

Also decide which extra context the next node needs:
- include_user_profile: the query is vague about role, skills or location, so the user's own profile helps.
- include_last_job_search_response: the user is refining an earlier search.
"""


class JobSearchRouterAgent(RememberMixin, ThreadAgent):
    """Classifies a query into a RouterOutput via structured output, answering
    greetings inline through its `reply` field. Context: only the user input."""

    model = "gemini-3.1-flash-lite"  # match the graph's model, not the lab default

    def instructions(self) -> str:
        return ROUTER_PROMPT

    def schema(self) -> type:
        return RouterOutput

    def middleware(self) -> list[Middleware]:
        return [AgentLogger()]

    async def remember(self, state: dict) -> None:
        # The router's output is routing state, except when it answers a greeting
        # inline — that reply is conversation, so it goes on the thread.
        decision = ai_state.structured(state)
        if decision and decision.intent == "chat" and decision.reply:
            await self.remember_row("text", {"text": decision.reply}, state)


class JobSummarizerAgent(RememberMixin, ThreadAgent):
    """Summarizes a job list into prose. Context: only the tool response it is
    prompted with — no history, no profile, no tools."""

    model = "gemini-3.1-flash-lite"  # match the graph's model, not the lab default

    def instructions(self) -> str:
        return SUMMARIZER_PROMPT

    def middleware(self) -> list[Middleware]:
        return [AgentLogger()]


class JobSearchAgent(RememberMixin, ThreadAgent):
    tool_choice = "any"

    @property
    def contexts(self) -> list[Context]:
        return self.state.get("contexts") or []

    async def messages(self) -> list[BaseMessage]:
        messages: list[BaseMessage] = []

        if Context.INCLUDE_USER_PROFILE in self.contexts:
            messages.append(SystemMessage(content=f"User profile: {json.dumps(USER_PROFILE)}"))

        rows = list(await Message.where("thread_id", self.thread_id).where("role", "user").order_by("id").get())
        # The current turn's user row is persisted before the run; the runner appends
        # the live query itself, so drop it from history to avoid sending it twice.
        if rows and rows[-1].data.get("text") == self.state.get("query"):
            rows = rows[:-1]
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
