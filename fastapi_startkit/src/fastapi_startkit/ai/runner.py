from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, ToolCall
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool

from .pipeline import Response, build_pipeline
from .response import AgentResponse

if TYPE_CHECKING:
    from .agent import Agent
    from .document import Document

Message = BaseMessage | dict[str, Any]


def _as_text(content: Any) -> str:
    return content if isinstance(content, str) else str(content)


class BaseRunner(ABC):
    def __init__(self, agent: Agent) -> None:
        self.agent = agent

    def _build_messages(self, message: str, attachments: list[Document] | None = None) -> list[dict]:
        agent = self.agent
        messages: list[dict] = []

        instruction = agent.instructions()
        if instruction:
            messages.append({"role": "system", "content": instruction})

        messages.extend(agent.messages() or [])

        if message:
            messages.append({"role": "user", "content": message})

        if attachments:
            content: Any = [{"type": "text", "text": message}]
            for doc in attachments:
                content.append(doc.to_langchain_block())
            messages.append({"role": "user", "content": content})

        return messages

    def _build_model(self, model: str | None = None, provider_options: dict | None = None) -> Any:
        from .ai import Ai  # noqa: PLC0415

        return Ai().get_model_for(self.agent, model, provider_options)

    def _apply_schema(self, response: AgentResponse) -> AgentResponse:
        schema = self.agent.schema()
        if schema is not None and response.parsed is None and response.content:
            response.parsed = self._build_schema(schema, response.content)
        return response

    @staticmethod
    def _build_schema(schema: Any, content: str) -> Any:
        import json  # noqa: PLC0415

        if hasattr(schema, "model_validate_json"):
            return schema.model_validate_json(content)
        if hasattr(schema, "model_validate"):
            return schema.model_validate(json.loads(content))
        return schema(**json.loads(content))

    @abstractmethod
    async def run(
        self,
        message: str,
        *,
        model: str | None = None,
        attachments: list[Document] | None = None,
        provider_options: dict | None = None,
    ) -> AgentResponse: ...

    @abstractmethod
    def stream(
        self,
        message: str,
        *,
        model: str | None = None,
        provider_options: dict | None = None,
    ) -> AsyncIterator[str]: ...


class Runner(BaseRunner):
    async def run(
        self,
        message: str,
        *,
        model: str | None = None,
        attachments: list[Document] | None = None,
        provider_options: dict | None = None,
    ) -> AgentResponse:
        started = time.perf_counter()
        messages = self._build_messages(message, attachments)
        model = self._build_model(model, provider_options)

        create_agent(
            model=model,
            tools=self.agent.tools,
        )
        response = await self._run_pipeline(model, messages)
        response = self._apply_schema(response)
        response.runtime = time.perf_counter() - started
        return response

    async def _run_pipeline(self, chat_model: Any, messages: list) -> AgentResponse:
        chain = list(self.agent.middleware())
        if not chain:
            raw = await self._invoke(chat_model, messages)
            return self._to_agent_response(raw)

        def core(model: Any) -> Response:
            async def _run() -> AsyncIterator[Any]:
                yield await self._invoke(model, messages)

            return Response(_run)

        pipeline = build_pipeline(chain, core)
        raw = await pipeline(chat_model)
        return self._to_agent_response(raw)

    def _to_agent_response(self, result: Any) -> AgentResponse:
        parsed = None
        structured = isinstance(result, dict) and "parsed" in result and "raw" in result
        if structured:
            parsed = result.get("parsed")
            result = result.get("raw")

        messages = result.get("messages", []) if isinstance(result, dict) else []
        final = messages[-1] if messages else result

        content = getattr(final, "content", "")
        if not isinstance(content, str):
            content = str(content)
        if structured and not content and hasattr(parsed, "model_dump_json"):
            content = parsed.model_dump_json()

        tool_calls = [] if structured else list(getattr(final, "tool_calls", None) or [])

        usage: dict[str, Any] = {}
        meta = getattr(final, "usage_metadata", None)
        if meta:
            usage = {"input": meta.get("input_tokens", 0), "output": meta.get("output_tokens", 0)}

        return AgentResponse(content=content, tool_calls=tool_calls, usage=usage, raw=result, parsed=parsed)

    async def stream(
        self,
        message: str,
        *,
        model: str | None = None,
        provider_options: dict | None = None,
    ) -> AsyncIterator[str]:
        messages = self._build_messages(message)
        chat_model = self._build_model(model, provider_options)
        chain = list(self.agent.middleware())

        def core(m: Any) -> Response:
            return Response(lambda: self._invoke_stream(m, messages))

        pipeline = build_pipeline(chain, core) if chain else core

        async for chunk in pipeline(chat_model):
            yield chunk

    async def _invoke(self, model: Runnable[Any, BaseMessage], messages: list) -> BaseMessage:
        response: AIMessage = await model.ainvoke(list(messages))  # type: ignore[assignment]
        if isinstance(response, dict) and "parsed" in response:
            return response  # type: ignore[return-value]
        if not response.tool_calls:
            return response
        return (await self._run_tools(response.tool_calls))[-1]

    async def _invoke_stream(self, model: Runnable[Any, BaseMessage], messages: list) -> AsyncIterator[str]:
        gathered: AIMessageChunk | None = None
        async for chunk in model.astream(list(messages)):
            if chunk.content:
                yield _as_text(chunk.content)
            gathered = chunk if gathered is None else gathered + chunk  # type: ignore[operator]

        if gathered is None or not gathered.tool_calls:
            return
        for message in await self._run_tools(gathered.tool_calls):
            yield _as_text(message.content)

    async def _run_tools(self, tool_calls: list[ToolCall]) -> list[BaseMessage]:
        tools: dict[str, BaseTool] = {tool.name: tool for tool in self.agent.tools()}
        results: list[BaseMessage] = []
        for call in tool_calls:
            try:
                selected = tools[call["name"]]
            except KeyError:
                raise ValueError(f"Agent has no tool named {call['name']!r}") from None
            results.append(await selected.ainvoke(call))
        return results
