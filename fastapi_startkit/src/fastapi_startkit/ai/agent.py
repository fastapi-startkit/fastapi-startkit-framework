from __future__ import annotations

from typing import TYPE_CHECKING, AsyncIterator, Optional, Type

from .document import Document
from .response import AgentResponse
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
    ) -> AgentResponse:
        return await self.runner().run(
            message, model=model, attachments=attachments, provider_options=provider_options
        )

    async def stream(
            self,
            message: str,
            *,
            model: str | None = None,
            provider_options: dict | None = None,
    ) -> AsyncIterator[str]:
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
