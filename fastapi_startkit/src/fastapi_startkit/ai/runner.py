from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import TYPE_CHECKING, Any

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, ToolCall
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool

if TYPE_CHECKING:
    from .agent import Agent

Message = BaseMessage | dict[str, Any]


def _as_text(content: Any) -> str:
    return content if isinstance(content, str) else str(content)


class Runner:
    def __init__(self, agent: Agent, model: Runnable[Any, BaseMessage]) -> None:
        self._tools: dict[str, BaseTool] = {tool.name: tool for tool in agent.tools()}
        self.model: Runnable[Any, BaseMessage] = model
        self.max_steps = agent.max_steps
        self._schema = agent.schema()
        self._schema_tool = self._schema_tool_name(self._schema) if self._schema is not None else None

    async def run(self, messages: Sequence[Message]) -> BaseMessage:
        history: list[Message] = list(messages)
        response: AIMessage = await self.model.ainvoke(history)  # type: ignore[assignment]

        if isinstance(response, dict) and "parsed" in response:
            return response  # type: ignore[return-value]

        tool_calls = list(getattr(response, "tool_calls", None) or [])
        if not tool_calls:
            return response

        for call in tool_calls:
            if call.get("name") == self._schema_tool:
                parsed = self._parse_schema(call.get("args") or {})
                return {"raw": response, "parsed": parsed, "parsing_error": None}  # type: ignore[return-value]

        return (await self._run_tools(tool_calls))[-1]

    def _parse_schema(self, args: dict[str, Any]) -> Any:
        schema = self._schema
        if hasattr(schema, "model_validate"):
            return schema.model_validate(args)
        return schema(**args)

    @staticmethod
    def _schema_tool_name(schema: Any) -> str:
        from langchain_core.utils.function_calling import convert_to_openai_tool  # noqa: PLC0415

        return convert_to_openai_tool(schema)["function"]["name"]

    async def _run_tools(self, tool_calls: list[ToolCall]) -> list[BaseMessage]:
        return [await self._resolve_tool(call["name"]).ainvoke(call) for call in tool_calls]

    def _resolve_tool(self, name: str) -> BaseTool:
        try:
            return self._tools[name]
        except KeyError:
            raise ValueError(f"Agent has no tool named {name!r}") from None


class StreamRunner(Runner):
    async def run(self, messages: Sequence[Message]) -> AsyncIterator[str]:  # type: ignore[override]
        history: list[Message] = list(messages)

        gathered: AIMessageChunk | None = None
        async for chunk in self.model.astream(history):
            if chunk.content:
                yield _as_text(chunk.content)
            gathered = chunk if gathered is None else gathered + chunk  # type: ignore[operator]

        if gathered is None or not gathered.tool_calls:
            return

        for message in await self._run_tools(gathered.tool_calls):
            yield _as_text(message.content)
