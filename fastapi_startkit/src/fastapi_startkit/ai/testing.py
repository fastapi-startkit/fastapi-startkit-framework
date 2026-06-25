from __future__ import annotations

import fnmatch
import functools
import hashlib
import inspect
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from .response import AgentResponse

if TYPE_CHECKING:
    from .agent import Agent
    from .document import Document


class NoFakeResponse(LookupError):
    pass


def _matches(pattern: str, message: str) -> bool:
    pattern, message = pattern.lower(), message.lower()
    if any(ch in pattern for ch in "*?["):
        return fnmatch.fnmatch(message, pattern)
    return pattern in message


def _reply_text(reply: Any) -> str:
    if isinstance(reply, AgentResponse):
        return reply.content
    return getattr(reply, "content", None) or str(reply)


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.attachments: list[list[Document]] = []

    def _record_call(self, message: str, attachments: list[Document] | None) -> None:
        self.calls.append(message)
        self.attachments.append(list(attachments or []))

    @property
    def prompt_count(self) -> int:
        return len(self.calls)

    def assert_prompted(self, pattern: str | None = None) -> None:
        if pattern is None:
            assert self.calls, "Expected the agent to be prompted, but it never was."
            return
        assert any(_matches(pattern, message) for message in self.calls), (
            f"Expected a prompt matching {pattern!r}, but none did. Got: {self.calls!r}"
        )

    def assert_not_prompted(self) -> None:
        assert not self.calls, f"Expected no prompts, but got: {self.calls!r}"


class FakeAgent(_Recorder):
    def __init__(self, responses: dict[str, Any] | None = None) -> None:
        super().__init__()
        self.responses = responses or {}

    async def prompt(self, message: str, attachments: list[Document] | None = None) -> AgentResponse:
        self._record_call(message, attachments)
        if not self.responses:
            return AgentResponse(content="")
        for pattern, reply in self.responses.items():
            if _matches(pattern, message):
                return AgentResponse(content=_reply_text(reply))
        raise NoFakeResponse(f"No fake response matched message: {message!r}")


class RecordingAgent(_Recorder):
    def __init__(self, real: Agent, cassette: str | None = None) -> None:
        super().__init__()
        self._real = real
        self.cassette: Path | None = Path(cassette) if cassette else None

    @staticmethod
    def _key(message: str, attachments: list[Document] | None) -> str:
        names = [getattr(doc, "name", "") for doc in (attachments or [])]
        payload = json.dumps({"message": message, "attachments": names}, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    async def prompt(self, message: str, attachments: list[Document] | None = None) -> AgentResponse:
        self._record_call(message, attachments)
        cassette = self.cassette
        assert cassette is not None, "RecordingAgent has no cassette resolved"
        store = json.loads(cassette.read_text()) if cassette.exists() else {}
        key = self._key(message, attachments)
        if key in store:
            return AgentResponse(content=store[key])
        response = await self._real._run(message, attachments=attachments)
        store[key] = response.content
        cassette.parent.mkdir(parents=True, exist_ok=True)
        cassette.write_text(json.dumps(store, indent=2, sort_keys=True))
        return response


class AgentBinding:
    def __init__(self, agent_cls: type[Agent], stand_in: Any) -> None:
        self._agent_cls = agent_cls
        self._stand_in = stand_in

    def _resolve_cassette(self, filename: str, qualname: str) -> None:
        stand_in = self._stand_in
        if not isinstance(stand_in, RecordingAgent):
            return
        here = Path(filename).parent
        if stand_in.cassette is None:
            stand_in.cassette = here / "cassettes" / f"{qualname.replace('.', '_')}.json"
        elif not stand_in.cassette.is_absolute():
            stand_in.cassette = here / stand_in.cassette

    def __enter__(self) -> Any:
        from fastapi_startkit.application import app

        caller = sys._getframe(1).f_code
        self._resolve_cassette(caller.co_filename, caller.co_qualname)
        app().bind(self._agent_cls.__name__, self._stand_in)
        return self._stand_in

    def __exit__(self, *_exc: Any) -> bool:
        from fastapi_startkit.application import app

        app().unbind(self._agent_cls.__name__)
        return False

    def __call__(self, func: Callable) -> Callable:
        self._resolve_cassette(inspect.getfile(func), func.__qualname__)

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                with self:
                    return await func(*args, **kwargs)

            return async_wrapper

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with self:
                return func(*args, **kwargs)

        return wrapper
