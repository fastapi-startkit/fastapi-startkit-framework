from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool

Message = BaseMessage | dict[str, Any]


class Runner:
    def __init__(
        self,
        model: BaseChatModel,
        tools: Sequence[BaseTool] | None = None,
        max_steps: int = 10,
    ) -> None:
        self._tools: dict[str, BaseTool] = {tool.name: tool for tool in (tools or [])}
        self.model: Runnable[Any, BaseMessage] = (
            model.bind_tools(list(self._tools.values())) if self._tools else model
        )
        self.max_steps = max_steps

    async def run(self, messages: Sequence[Message]) -> BaseMessage:
        history: list[Message] = list(messages)
        response: AIMessage = await self.model.ainvoke(history)  # type: ignore[assignment]

        if not response.tool_calls:
            return response

        return (await self._run_tools(response.tool_calls))[-1]

    async def _run_tools(self, tool_calls: list[dict[str, Any]]) -> list[BaseMessage]:
        return [await self._resolve_tool(call["name"]).ainvoke(call) for call in tool_calls]

    def _resolve_tool(self, name: str) -> BaseTool:
        try:
            return self._tools[name]
        except KeyError:
            raise ValueError(f"Agent has no tool named {name!r}") from None


class StreamRunner(Runner):
    async def run(self, messages: Sequence[Message]) -> AsyncIterator[str]:  # type: ignore[override]
        history: list[Message] = list(messages)

        for _ in range(self.max_steps):
            gathered: AIMessageChunk | None = None
            async for chunk in self.model.astream(history):
                if chunk.content:
                    yield chunk.content if isinstance(chunk.content, str) else str(chunk.content)
                gathered = chunk if gathered is None else gathered + chunk  # type: ignore[operator]

            if gathered is None or not gathered.tool_calls:
                return
            history.append(gathered)
            history.extend(await self._run_tools(gathered.tool_calls))
