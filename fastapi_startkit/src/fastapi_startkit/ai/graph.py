
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Annotated, Any, TypedDict

from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from .agent import Agent
from .response import AgentResponse
from .runner import BaseRunner

if TYPE_CHECKING:
    from .document import Document


class GraphState(TypedDict):

    messages: Annotated[list, add_messages]
    llm_calls: int


class GraphAgent(Agent, ABC):

    def runner(self) -> GraphRunner:
        return GraphRunner(self)

    @abstractmethod
    def graph(self, runner: GraphRunner) -> StateGraph:
        ...


class GraphRunner(BaseRunner):

    agent: GraphAgent

    def __init__(self, agent: GraphAgent) -> None:
        super().__init__(agent)
        self._chat_model: Any = None


    async def llm(self, state: GraphState) -> dict:
        reply = await self._chat_model.ainvoke(state["messages"])
        return {"messages": [reply], "llm_calls": state.get("llm_calls", 0) + 1}

    async def call_tools(self, state: GraphState) -> dict:
        tools_by_name = {tool.name: tool for tool in self.agent.tools()}
        results = []
        for call in getattr(state["messages"][-1], "tool_calls", None) or []:
            results.append(await tools_by_name[call["name"]].ainvoke(call))
        return {"messages": results}

    def route(self, state: GraphState) -> str:
        return "tools" if getattr(state["messages"][-1], "tool_calls", None) else END


    def _compile(self, model: str | None, provider_options: dict | None) -> Any:
        self._chat_model = self._build_model(model, provider_options)
        return self.agent.graph(self).compile()

    @property
    def _config(self) -> dict:
        return {"recursion_limit": self.agent.max_steps * 2 + 1}

    async def run(
        self,
        message: str,
        *,
        model: str | None = None,
        attachments: list[Document] | None = None,
        provider_options: dict | None = None,
    ) -> AgentResponse:
        started = time.perf_counter()
        compiled = self._compile(model, provider_options)
        state = {"messages": self._build_messages(message, attachments), "llm_calls": 0}
        result = await compiled.ainvoke(state, config=self._config)
        response = self._apply_schema(self._to_response(result))
        response.runtime = time.perf_counter() - started
        return response

    async def stream(
        self,
        message: str,
        *,
        model: str | None = None,
        provider_options: dict | None = None,
    ) -> AsyncIterator[str]:
        compiled = self._compile(model, provider_options)
        state = {"messages": self._build_messages(message), "llm_calls": 0}
        async for chunk, _meta in compiled.astream(state, stream_mode="messages", config=self._config):
            text = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
            if text:
                yield text

    @staticmethod
    def _to_response(result: dict) -> AgentResponse:
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

        return AgentResponse(content=content, tool_calls=tool_calls, usage=usage, raw=result)
