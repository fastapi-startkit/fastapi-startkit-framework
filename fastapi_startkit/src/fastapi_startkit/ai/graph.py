from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Annotated, Any, TypedDict

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END
from langgraph.graph.message import add_messages

from .agent import Agent
from .pipeline import Response, build_pipeline
from .response import AgentResponse
from .runner import BaseRunner

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph

    from .document import Document


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    llm_calls: int


class GraphAgent(Agent, ABC):
    def __init__(self):
        super().__init__()

    def runner(self) -> GraphRunner:
        return GraphRunner(self)

    async def prompt(
        self,
        message: str,
        *,
        model: str | None = None,
        attachments: list[Document] | None = None,
        config: RunnableConfig | dict | None = None,
        provider_options: dict | None = None,
    ) -> AgentResponse:
        return await self.runner().run(
            message,
            model=model,
            attachments=attachments,
            config=config,
            provider_options=provider_options,
        )

    async def stream(
        self,
        message: str,
        *,
        model: str | None = None,
        config: RunnableConfig | dict | None = None,
        provider_options: dict | None = None,
    ) -> AsyncIterator[dict]:
        async for chunk in self.runner().stream(message, model=model, config=config, provider_options=provider_options):
            yield chunk

    @abstractmethod
    async def graph(self, runner: GraphRunner) -> CompiledStateGraph: ...


class GraphRunner(BaseRunner):
    agent: GraphAgent

    def __init__(self, agent: GraphAgent) -> None:
        super().__init__(agent)
        self.model: Any = None

    async def llm(self, state: AgentState) -> dict:
        started = time.perf_counter()
        reply = await self._invoke_model(state["messages"])
        self._record_ai_message(reply, (time.perf_counter() - started) * 1000)
        return {"messages": [reply], "llm_calls": state.get("llm_calls", 0) + 1}

    async def _invoke_model(self, messages: list) -> Any:
        """Invoke the model, wrapped in the agent's middleware pipeline (the same
        onion the plain ``Runner`` builds). Tool routing stays in the graph — the
        middleware only wraps the single model call."""
        chain = list(self.agent.middleware())
        if not chain:
            return await self.model.ainvoke(messages)

        def core(model: Any) -> Response:
            async def _run() -> AsyncIterator[Any]:
                yield await model.ainvoke(messages)

            return Response(_run)

        pipeline = build_pipeline(chain, core)
        return await pipeline(self.model)

    async def call_tools(self, state: AgentState) -> dict:
        tools_by_name = {tool.name: tool for tool in self.agent.tools()}
        results = []
        for call in getattr(state["messages"][-1], "tool_calls", None) or []:
            started = time.perf_counter()
            message = await tools_by_name[call["name"]].ainvoke(call)
            self._record_tool_message(call, message, (time.perf_counter() - started) * 1000)
            results.append(message)
        return {"messages": results}

    def route(self, state: AgentState) -> str:
        return "tools" if getattr(state["messages"][-1], "tool_calls", None) else END

    async def _compile(self, model: str | None, provider_options: dict | None) -> Any:
        self.model = self._build_model(model, provider_options)
        return await self.agent.graph(self)

    @property
    def _config(self) -> dict:
        return {"recursion_limit": self.agent.max_steps * 2 + 1}

    def _merge_config(self, config: RunnableConfig | dict | None) -> dict:
        """Layer a caller-supplied config (e.g. ``configurable.thread_id`` for the
        checkpointer) on top of the runner defaults."""
        return {**self._config, **(config or {})}

    async def run(
        self,
        message: str,
        *,
        model: str | None = None,
        attachments: list[Document] | None = None,
        config: RunnableConfig | dict | None = None,
        provider_options: dict | None = None,
    ) -> AgentResponse:
        started = time.perf_counter()
        self._reset_capture()
        compiled = await self._compile(model, provider_options)
        state = {"messages": await self._build_messages(message, attachments), "llm_calls": 0}
        result = await compiled.ainvoke(state, config=self._merge_config(config))
        response = self._apply_schema(self._to_response(result))
        response.runtime = time.perf_counter() - started
        return response

    async def stream(
        self,
        message: str,
        *,
        model: str | None = None,
        config: RunnableConfig | dict | None = None,
        provider_options: dict | None = None,
    ) -> AsyncIterator[dict]:
        self._reset_capture()
        compiled = await self._compile(model, provider_options)
        state = {"messages": await self._build_messages(message), "llm_calls": 0}
        final_state: dict = {}
        # "messages" streams tokens; "values" hands back the full state after each
        # step, whose last snapshot carries every message (and its tool_calls).
        async for mode, chunk in compiled.astream(
            state, stream_mode=["messages", "values"], config=self._merge_config(config)
        ):
            if mode == "values":
                final_state = chunk
                continue
            message_chunk, _meta = chunk
            text = message_chunk.content if isinstance(message_chunk.content, str) else str(message_chunk.content)
            if not text:
                continue
            if isinstance(message_chunk, ToolMessage):
                yield {"type": "tool_response", "name": message_chunk.name or "", "content": text}
            else:
                yield {"type": "delta", "text": text}
        self.last_response = self._to_response(final_state) if final_state else AgentResponse(content="")

    def _to_response(self, result: dict) -> AgentResponse:
        messages = result.get("messages", [])
        final = messages[-1] if messages else None
        content = getattr(final, "content", "") or ""
        if not isinstance(content, str):
            content = str(content)

        tool_calls = [call for m in messages for call in (getattr(m, "tool_calls", None) or [])]

        usage: dict[str, Any] = {}
        meta = getattr(final, "usage_metadata", None)
        if meta:
            usage = {"input": meta.get("input_tokens", 0), "output": meta.get("output_tokens", 0)}

        return AgentResponse(
            content=content,
            tool_calls=tool_calls,
            usage=usage,
            raw=result,
            tool_events=list(self._tool_events),
            transcript=list(self._transcript),
        )
