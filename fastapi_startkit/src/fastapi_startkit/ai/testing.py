from __future__ import annotations

import fnmatch
import functools
import hashlib
import inspect
import json
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from .response import AgentResponse

if TYPE_CHECKING:
    from .agent import Agent
    from .document import Document


def _matches(pattern: str, message: str) -> bool:
    pattern, message = pattern.lower(), message.lower()
    if any(ch in pattern for ch in "*?["):
        return fnmatch.fnmatch(message, pattern)
    return pattern in message


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


def _joined(value: Any) -> str:
    """A cassette value is a buffered string or a list of stream chunks."""
    return "".join(value) if isinstance(value, list) else value


class AgentModelFake:
    """Registers a fixed, ordered list of replies as ``agent_cls``'s chat
    model for the duration of a ``with`` block (or a decorated function).

    Unlike the old pattern-matching stand-in, this swaps only the model —
    ``prompt()``/``stream()`` still run the real message-building, pipeline,
    and tool-execution path; see ``Ai.fake()``.
    """

    def __init__(self, agent_cls: type[Agent], responses: list) -> None:
        self._agent_cls = agent_cls
        self._responses = responses

    def __enter__(self) -> None:
        from .model_builder import Ai

        Ai.fake(self._agent_cls.__name__, self._responses)

    def __exit__(self, *_exc: Any) -> bool:
        from .model_builder import Ai

        Ai.forget(self._agent_cls.__name__)
        return False

    def __call__(self, func: Callable) -> Callable:
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

    def _load(self) -> tuple[Path, dict]:
        cassette = self.cassette
        assert cassette is not None, "RecordingAgent has no cassette resolved"
        return cassette, (json.loads(cassette.read_text()) if cassette.exists() else {})

    def _save(self, cassette: Path, store: dict, key: str, value: Any) -> None:
        store[key] = value
        cassette.parent.mkdir(parents=True, exist_ok=True)
        cassette.write_text(json.dumps(store, indent=2, sort_keys=True))

    async def prompt(self, message: str, attachments: list[Document] | None = None) -> AgentResponse:
        self._record_call(message, attachments)
        cassette, store = self._load()
        key = self._key(message, attachments)
        if key in store:
            return AgentResponse(content=_joined(store[key]))
        response = await self._real._run(message, attachments=attachments)
        self._save(cassette, store, key, response.content)
        return response

    async def stream(self, message: str) -> AsyncIterator[str]:
        self._record_call(message, None)
        cassette, store = self._load()
        key = self._key(message, None)
        if key in store:
            value = store[key]
            for chunk in value if isinstance(value, list) else [value]:
                yield chunk
            return
        chunks = [chunk async for chunk in self._real._stream(message)]
        self._save(cassette, store, key, chunks)
        for chunk in chunks:
            yield chunk


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
