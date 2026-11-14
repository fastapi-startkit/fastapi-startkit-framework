from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Callable, Generic, Optional, Type, TypeVar

from .document import Document
from .runner import BaseRunner, Runner
from .streaming import StreamableAgentResponse

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool

    from .testing import AgentFake, AgentRecordFake
    from .types import Middleware

_R = TypeVar("_R")


class _hybridmethod(Generic[_R]):
    """A method callable on the class (bound to a freshly built instance) or on an
    existing instance (bound to that instance). Lets ``Agent.record()`` and
    ``Agent(state, config).record()`` both work, the latter keeping its state."""

    def __init__(self, func: Callable[..., _R]) -> None:
        self._func = func

    def __get__(self, instance: object, owner: type) -> Callable[..., _R]:
        target = instance if instance is not None else owner()
        return functools.partial(self._func, target)


class Agent:
    provider: str | None = None
    model: str | None = None
    max_steps: int = 10
    max_tokens: int = 4096
    timeout: float = 30.0
    top_p: float = 1.0
    temperature: float | None = None
    tool_choice: str | None = None
    conversation_id: str | None = None

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

    def stream(
        self,
        message: str,
        *,
        model: str | None = None,
        provider_options: dict | None = None,
    ) -> StreamableAgentResponse:
        return StreamableAgentResponse(
            lambda: self.runner().stream(message, model=model, provider_options=provider_options),
            conversation_id=self.conversation_id,
        )

    def runner(self) -> BaseRunner:
        return Runner(self)

    @classmethod
    def fake(cls, responses: list) -> "AgentFake":
        from .testing import AgentFake

        return AgentFake(cls, responses)

    @_hybridmethod
    def record(self, cassette: str | None = None, messages: list | None = None) -> "AgentRecordFake":
        from .testing import AgentRecordFake

        return AgentRecordFake(self, cassette, messages)
