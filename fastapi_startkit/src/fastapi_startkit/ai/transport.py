"""Transport strategies for Agent.prompt()/stream().

A single call resolves exactly one transport — the real model pipeline, a
stand-in bound via ``Agent.fake()``/``Agent.record()``, or an inline fake matched
from ``Agent._fakes``. Concentrating the branch here lets the public methods keep
one call path and log / apply their schema in one place instead of once per branch.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncIterator

from .response import AgentResponse, AgentSnapshot

if TYPE_CHECKING:
    from .agent import Agent
    from .document import Document


class Transport:
    def __init__(self, agent: Agent) -> None:
        self._agent = agent

    async def prompt(
        self,
        message: str,
        *,
        model: str | None,
        attachments: list[Document] | None,
        provider_options: dict | None,
    ) -> AgentResponse:
        raise NotImplementedError

    def stream(
        self,
        message: str,
        *,
        model: str | None,
        provider_options: dict | None,
    ) -> AsyncIterator[str]:
        raise NotImplementedError


class LiveTransport(Transport):
    """Runs the real model pipeline."""

    async def prompt(
        self,
        message: str,
        *,
        model: str | None,
        attachments: list[Document] | None,
        provider_options: dict | None,
    ) -> AgentResponse:
        agent = self._agent
        messages = agent._build_messages(message, attachments)
        chat_model = agent._build_model(model, provider_options)
        return await agent._run_pipeline(chat_model, messages)

    async def stream(
        self,
        message: str,
        *,
        model: str | None,
        provider_options: dict | None,
    ) -> AsyncIterator[str]:
        async for chunk in self._agent._stream(message, model=model, provider_options=provider_options):
            yield chunk


class StandInTransport(Transport):
    """Delegates to a stand-in bound via Agent.fake()/record()."""

    def __init__(self, agent: Agent, stand_in: Any) -> None:
        super().__init__(agent)
        self._stand_in = stand_in

    async def prompt(
        self,
        message: str,
        *,
        model: str | None,
        attachments: list[Document] | None,
        provider_options: dict | None,
    ) -> AgentResponse:
        return await self._stand_in.prompt(message, attachments=attachments)

    async def stream(
        self,
        message: str,
        *,
        model: str | None,
        provider_options: dict | None,
    ) -> AsyncIterator[str]:
        stand_in = self._stand_in
        if hasattr(stand_in, "stream"):
            async for chunk in stand_in.stream(message):
                yield chunk
        else:
            response = await stand_in.prompt(message)
            yield response.content


class InlineFakeTransport(Transport):
    """Serves a canned response matched from Agent._fakes."""

    def __init__(self, agent: Agent, match: AgentResponse | AgentSnapshot) -> None:
        super().__init__(agent)
        self._match = match

    async def prompt(
        self,
        message: str,
        *,
        model: str | None,
        attachments: list[Document] | None,
        provider_options: dict | None,
    ) -> AgentResponse:
        match = self._match
        if isinstance(match, AgentSnapshot):
            return await match.resolve(
                self._agent,
                message,
                model=model,
                attachments=attachments,
                provider_options=provider_options,
            )
        return match

    async def stream(
        self,
        message: str,
        *,
        model: str | None,
        provider_options: dict | None,
    ) -> AsyncIterator[str]:
        match = self._match
        if isinstance(match, AgentSnapshot):
            response = await match.resolve(self._agent, message)
        else:
            response = match
        yield response.content
