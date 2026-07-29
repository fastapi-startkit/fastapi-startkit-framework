from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Annotated, Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END
from langgraph.graph.message import add_messages

from .agent import Agent
from .pipeline import Response, build_pipeline
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
    ) -> dict:
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
    ) -> dict:
        self._reset_capture()
        compiled = await self._compile(model, provider_options)
        state = {"messages": await self._build_messages(message, attachments), "llm_calls": 0}
        result = await compiled.ainvoke(state, config=self._merge_config(config))
        result["messages"] = self._with_response_times(result.get("messages", []))
        return self._apply_schema(result)

    async def stream(
        self,
        message: str,
        *,
        model: str | None = None,
        config: RunnableConfig | dict | None = None,
        provider_options: dict | None = None,
    ) -> AsyncIterator[dict]:
        """Yields the graph's astream_events verbatim — StandardStreamEvent dicts
        (on_chain_*, on_chat_model_*, on_tool_*). The root chain's end event
        carries the final state, exposed as ``last_response``."""
        self._reset_capture()
        compiled = await self._compile(model, provider_options)
        state = {"messages": await self._build_messages(message), "llm_calls": 0}
        final_state: dict = {}
        async for event in compiled.astream_events(state, config=self._merge_config(config)):
            if event["event"] == "on_chain_end" and not event.get("parent_ids"):
                output = event["data"].get("output")
                final_state = output if isinstance(output, dict) else {}
            yield event
        if final_state:
            final_state["messages"] = self._with_response_times(final_state.get("messages", []))
        self.last_response = final_state or {"messages": []}

    def _with_response_times(self, messages: list) -> list:
        """Stamp each recorded model/tool call's ``response_time`` (ms) onto the
        turn's trailing AI/tool messages — the graph state also holds history, so
        the recorded entries align with the last N ai/tool messages."""
        entries = [e for e in self._transcript if e["type"] in ("ai", "tool_response")]
        targets = [m for m in messages if getattr(m, "type", "") in ("ai", "tool")]
        for entry, message in zip(entries, targets[max(0, len(targets) - len(entries)) :]):
            message.additional_kwargs["response_time"] = entry.get("response_time", 0.0)
        return list(messages)
