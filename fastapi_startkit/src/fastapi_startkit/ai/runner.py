"""Runner — drive a chat model through a tool-calling loop, no ``create_agent``.

The :class:`~fastapi_startkit.ai.agent.Agent` builds a chat model (via
``init_chat_model``) and its tools, then hands them to a Runner. The Runner binds
the tools, invokes the model, executes any tool calls the model requests, feeds
the results back, and repeats until the model answers without calling a tool (or
``max_steps`` is reached). :class:`StreamRunner` does the same while yielding
content tokens as they arrive.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool

# A turn in the running history: a chat message or a plain role/content dict.
Message = BaseMessage | dict[str, Any]


class Runner:
    """Run a chat model through a tool-calling loop and return the final message."""

    def __init__(
        self,
        model: BaseChatModel,
        tools: Sequence[BaseTool] | None = None,
        max_steps: int = 10,
    ) -> None:
        self._tools: dict[str, BaseTool] = {tool.name: tool for tool in (tools or [])}
        # Bind the tools so the model can request them; an unbound model otherwise.
        self.model: Runnable[Any, BaseMessage] = (
            model.bind_tools(list(self._tools.values())) if self._tools else model
        )
        self.max_steps = max_steps

    def run(self, messages: Sequence[Message]) -> AIMessage:
        history: list[Message] = list(messages)
        response: AIMessage = self.model.invoke(history)  # type: ignore[assignment]

        for _ in range(self.max_steps):
            if not response.tool_calls:
                break
            history.append(response)
            history.extend(self._run_tools(response.tool_calls))
            response = self.model.invoke(history)  # type: ignore[assignment]

        return response

    def _run_tools(self, tool_calls: list[dict[str, Any]]) -> list[BaseMessage]:
        return [self._resolve_tool(call["name"]).invoke(call) for call in tool_calls]

    def _resolve_tool(self, name: str) -> BaseTool:
        try:
            return self._tools[name]
        except KeyError:
            raise ValueError(f"Agent has no tool named {name!r}") from None


class StreamRunner(Runner):
    """Like :class:`Runner`, but yields content tokens as the model streams them."""

    def run(self, messages: Sequence[Message]) -> Iterator[str]:  # type: ignore[override]
        history: list[Message] = list(messages)

        for _ in range(self.max_steps):
            gathered: AIMessageChunk | None = None
            for chunk in self.model.stream(history):
                if chunk.content:
                    yield chunk.content if isinstance(chunk.content, str) else str(chunk.content)
                gathered = chunk if gathered is None else gathered + chunk  # type: ignore[operator]

            if gathered is None or not gathered.tool_calls:
                return
            history.append(gathered)
            history.extend(self._run_tools(gathered.tool_calls))
