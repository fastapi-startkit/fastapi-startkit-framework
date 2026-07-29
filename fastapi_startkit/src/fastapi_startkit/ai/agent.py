from __future__ import annotations

from typing import TYPE_CHECKING, AsyncIterator, Optional, Type

from .document import Document
from .runner import BaseRunner, Runner

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool

    from .testing import AgentFake, AgentRecordFake
    from .types import Middleware


class Agent:
    provider: str | None = None
    model: str | None = None
    max_steps: int = 10
    max_tokens: int = 4096
    timeout: float = 30.0
    top_p: float = 1.0
    # Forwarded to bind_tools() when set: "auto" (default), "any" (must call a tool),
    # or a specific tool name.
    tool_choice: str | None = None

    def messages(self) -> list[dict]:
        return []

    def instructions(self) -> str | None:
        return None

    def schema(self) -> Optional[Type]:
        return None

    def tools(self) -> list[BaseTool]:
        return []

    def middleware(self) -> list[Middleware]:
        return []

    def provider_options(self) -> dict:
        return {}

    async def prompt(
        self,
        message: str,
        *,
        model: str | None = None,
        attachments: list[Document] | None = None,
        provider_options: dict | None = None,
    ) -> dict:
        """Returns the turn as ``{"messages": [HumanMessage, AIMessage, ToolMessage,
        ...]}`` — the same state langchain's ``create_agent().invoke()`` yields —
        plus ``"structured_response"`` when the agent defines a schema()."""
        return await self.runner().run(message, model=model, attachments=attachments, provider_options=provider_options)

    async def stream(
        self,
        message: str,
        *,
        model: str | None = None,
        provider_options: dict | None = None,
    ) -> AsyncIterator[dict]:
        """Yields StandardStreamEvent dicts — the same shape LangChain's
        astream_events produces: on_chat_model_(start|stream|end) for the model
        turn (data.chunk carries each AIMessageChunk) and on_tool_(start|end)
        around each tool execution."""
        async for chunk in self.runner().stream(message, model=model, provider_options=provider_options):
            yield chunk

    def runner(self) -> BaseRunner:
        return Runner(self)

    @classmethod
    def fake(cls, responses: list) -> "AgentFake":
        from .testing import AgentFake

        return AgentFake(cls, responses)

    @classmethod
    def record(cls, cassette: str | None = None, messages: list | None = None) -> "AgentRecordFake":
        from .testing import AgentRecordFake

        return AgentRecordFake(cls(), cassette, messages)
