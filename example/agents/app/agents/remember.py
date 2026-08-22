import json

from fastapi_startkit.ai import Agent
from fastapi_startkit.ai import state as ai_state
from langchain_core.runnables import RunnableConfig

from app.agents.state import OverallState
from app.models.message import Message
from app.models.thread import Thread


class ThreadAgent(Agent):
    """An agent bound to a conversation thread via the graph's (state, config)."""

    def __init__(self, state: OverallState | None = None, config: RunnableConfig | None = None):
        super().__init__()
        self.state: dict = dict(state or {})
        configurable = (config or {}).get("configurable") or {}
        self.thread_id: str = configurable.get("thread_id", "")
        self.turn_id: str | None = configurable.get("turn_id")


class RememberMixin:
    """Persists what the agent did — tool calls, tool responses and text replies —
    onto its thread, right after each prompt(). No thread_id -> remembers nothing.
    """

    async def prompt(self, message: str, **kwargs) -> dict:
        state = await super().prompt(message, **kwargs)
        await self.remember(state)
        return state

    async def remember(self, state: dict) -> None:
        events = ai_state.tool_events(state)
        for event in events:
            await self.remember_row("tool_call", {"name": event["name"], "args": event["args"]}, state)
            await self.remember_row("tool_response", json.loads(event["content"]), state)

        # A plain text reply; structured output is state, not conversation.
        text = ai_state.text(state)
        if text and not events and ai_state.structured(state) is None:
            await self.remember_row("text", {"text": text}, state)

    async def remember_row(self, type_: str, data: dict | list, state: dict) -> None:
        if not self.thread_id:  # not bound to a conversation -> nothing to remember
            return
        await Thread.first_or_create({"id": self.thread_id}, {"id": self.thread_id})
        row: dict = {
            "thread_id": self.thread_id,
            "role": "ai",
            "type": type_,
            "data": data,
            "data_type": "string" if type_ == "text" else "json",
            "run_id": self.turn_id,
            "meta": {"agent": type(self).__name__, **({"model": self.model} if self.model else {})},
        }
        usage = ai_state.usage(state)
        if usage["input"] or usage["output"]:
            row["usage"] = usage
        await Message.create(row)
