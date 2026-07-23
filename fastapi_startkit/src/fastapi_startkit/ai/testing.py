from __future__ import annotations

import functools
import hashlib
import inspect
import json
import sys
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from .response import AgentResponse

if TYPE_CHECKING:
    from .agent import Agent
    from .document import Document


def _joined(value: Any) -> str:
    return "".join(value) if isinstance(value, list) else value


class AgentFake:

    def __init__(self, agent_cls: type[Agent], responses: list) -> None:
        self._agent_cls = agent_cls
        self._responses = list(responses)
        self._agent = agent_cls()
        self._agent.messages = self._history  # type: ignore[method-assign]
        self._records: list[dict] = []
        self._last_response: AgentResponse | None = None
        self.last_elapsed: float | None = None

    def _history(self) -> list:
        return self._records

    @property
    def _prompts(self) -> list[str]:
        return [r["content"] for r in self._records if r.get("role") == "user"]

    def __enter__(self) -> "AgentFake":
        from .ai import Ai

        Ai.fake(self._agent_cls.__name__, self._responses)
        return self

    def __exit__(self, *_exc: Any) -> bool:
        from .ai import Ai

        Ai.forget(self._agent_cls.__name__)
        return False

    async def prompt(self, message: str, *, attachments: list[Document] | None = None) -> AgentResponse:
        start = time.monotonic()
        self._last_response = await self._agent.prompt(message, attachments=attachments)
        self.last_elapsed = time.monotonic() - start
        self._remember(message, self._last_response)
        return self._last_response

    async def stream(self, message: str) -> AsyncIterator[str]:
        chunks: list[str] = []
        async for chunk in self._agent.stream(message):
            chunks.append(chunk)
            yield chunk
        self._last_response = AgentResponse(content="".join(chunks))
        self._remember(message, self._last_response)

    def _remember(self, message: str, response: AgentResponse) -> None:
        self._records.append({"role": "user", "content": message})
        self._records.append({"role": "assistant", "content": response.content})


    def assert_prompt(self, expected: str | Callable[[str], bool]) -> None:
        if callable(expected):
            assert any(expected(p) for p in self._prompts), (
                f"No recorded prompt satisfied the predicate. Got: {self._prompts!r}"
            )
        else:
            assert any(expected in p for p in self._prompts), (
                f"Expected a prompt containing {expected!r}, but none did. Got: {self._prompts!r}"
            )

    def assert_response(self, expected: str) -> None:
        response = self._require_response()
        assert expected in response.content, f"Expected response to contain {expected!r}, got {response.content!r}"

    def assert_tool_call(self, name: str) -> None:
        response = self._require_response()
        called = [tc.get("name") for tc in response.tool_calls]
        assert name in called, f"Expected tool {name!r} to be called, but got: {called}"

    def assert_prompted(self, times: int | None = None) -> None:
        if times is not None:
            assert len(self._prompts) == times, f"Expected {times} prompt call(s), got {len(self._prompts)}"
        else:
            assert self._prompts, "Expected at least one prompt() or stream() call, but none were made"

    def assert_not_prompted(self) -> None:
        self.assert_prompted(times=0)

    def reset(self) -> "AgentFake":
        self._records.clear()
        self._last_response = None
        return self

    def _require_response(self) -> AgentResponse:
        assert self._last_response is not None, "No prompt() call has been made yet."
        return self._last_response

    def _tool_call_names(self) -> list[str]:
        return [tc.get("name", "") for tc in self._require_response().tool_calls]

    def assert_text_response(self) -> None:
        response = self._require_response()
        assert response.content, "Expected a non-empty text response, but content was empty."

    def assert_tool_called(self, name: str, predicate: Callable[[ToolCallView], bool] | None = None) -> None:
        response = self._require_response()
        matches = [tc for tc in response.tool_calls if tc.get("name") == name]
        assert matches, f"Expected tool {name!r} to be called, but it wasn't. Called: {self._tool_call_names()}"
        if predicate is not None:
            assert any(predicate(ToolCallView(tc)) for tc in matches), (
                f"Tool {name!r} was called, but no call satisfied the given predicate."
            )

    def assert_tool_not_called(self, names: list[str]) -> None:
        unexpected = set(self._tool_call_names()) & set(names)
        assert not unexpected, f"Expected tools {sorted(names)} not to be called, but got: {sorted(unexpected)}"

    def assert_response_time_lt(self, seconds: float) -> None:
        assert self.last_elapsed is not None, "No prompt() call has been made yet."
        assert self.last_elapsed < seconds, f"Expected response time < {seconds}s, took {self.last_elapsed:.3f}s"

    async def assert_response_judged(self, *, model: str, expectation: str, provider: str | None = None) -> None:
        response = self._require_response()
        verdict = await self._judge(model, expectation, response.content, provider)
        assert verdict.get("passed"), (
            f"Judge ({model}) rejected the response for expectation {expectation!r}: "
            f"{verdict.get('reasoning', '')!r} — response was {response.content!r}"
        )

    async def _judge(self, model: str, expectation: str, content: str, provider: str | None = None) -> dict:
        return await self._judge_live(model, expectation, content, provider)

    async def _judge_live(self, model: str, expectation: str, content: str, provider: str | None = None) -> dict:
        from .judge import JudgeAgent  # noqa: PLC0415

        judge = JudgeAgent()
        judge.model = model
        judge.provider = provider
        return await judge.judge(expectation, content)

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


class ToolCallView:

    def __init__(self, data: dict) -> None:
        self.name = data.get("name", "")
        self.args = data.get("args") or {}
        self.id = data.get("id")
        self._data = data

    def __repr__(self) -> str:
        return f"ToolCallView(name={self.name!r}, args={self.args!r})"


class AgentRecordFake(AgentFake):
    def __init__(self, real: Agent, cassette: str | None = None, messages: list | None = None) -> None:
        self._real = real
        self.cassette: Path | None = Path(cassette) if cassette else None
        self._seed_messages: list = list(messages or [])
        self._records: list[dict] = []
        self._real.messages = self._history  # type: ignore[method-assign]
        self._last_response: AgentResponse | None = None
        self.last_elapsed: float | None = None

    def _history(self) -> list:
        return self._seed_messages + self._records

    @staticmethod
    def _serialize(value: Any) -> Any:
        if isinstance(value, dict):
            return value
        return {"type": type(value).__name__, "content": getattr(value, "content", str(value))}

    def _key(self, message: str, attachments: list[Document] | None) -> str:
        names = [getattr(doc, "name", "") for doc in (attachments or [])]
        payload = json.dumps(
            {
                "history": [self._serialize(m) for m in self._history()],
                "message": message,
                "attachments": names,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def _load(self) -> tuple[Path, dict]:
        cassette = self.cassette
        assert cassette is not None, "AgentRecordFake has no cassette resolved"
        return cassette, (json.loads(cassette.read_text()) if cassette.exists() else {})

    def _save(self, cassette: Path, store: dict, key: str, value: Any) -> None:
        store[key] = value
        cassette.parent.mkdir(parents=True, exist_ok=True)
        cassette.write_text(json.dumps(store, indent=2, sort_keys=True))

    @staticmethod
    def _cache_prompt_value(response: AgentResponse) -> dict:
        return {"content": response.content, "tool_calls": response.tool_calls}

    @staticmethod
    def _response_from_cache(value: Any) -> AgentResponse:
        if isinstance(value, dict) and "content" in value:
            return AgentResponse(content=_joined(value.get("content", "")), tool_calls=value.get("tool_calls") or [])
        return AgentResponse(content=_joined(value))

    def _remember_turn(self, message: str, response: AgentResponse) -> None:
        self._records.append({"role": "user", "content": message})
        turn: dict[str, Any] = {"role": "assistant", "content": response.content}
        if response.tool_calls:
            turn["tool_calls"] = response.tool_calls
        self._records.append(turn)

    async def prompt(self, message: str, *, attachments: list[Document] | None = None) -> AgentResponse:
        cassette, store = self._load()
        key = self._key(message, attachments)
        start = time.monotonic()
        if key in store:
            response = self._response_from_cache(store[key])
        else:
            response = await self._real.prompt(message, attachments=attachments)
            self._save(cassette, store, key, self._cache_prompt_value(response))
        response = self._real.runner()._apply_schema(response)
        self.last_elapsed = time.monotonic() - start
        self._last_response = response
        self._remember_turn(message, response)
        return response

    async def stream(self, message: str) -> AsyncIterator[str]:
        cassette, store = self._load()
        key = self._key(message, None)
        if key in store:
            value = store[key]
            chunks = value if isinstance(value, list) else [value]
        else:
            chunks = [chunk async for chunk in self._real.stream(message)]
            self._save(cassette, store, key, chunks)
        for chunk in chunks:
            yield chunk
        self._remember_turn(message, AgentResponse(content=_joined(chunks)))

    async def _judge(self, model: str, expectation: str, content: str, provider: str | None = None) -> dict:
        cassette, store = self._load()
        key = self._judge_key(model, expectation, content, provider)
        if key in store:
            return store[key]
        verdict = await self._judge_live(model, expectation, content, provider)
        self._save(cassette, store, key, verdict)
        return verdict

    @staticmethod
    def _judge_key(model: str, expectation: str, content: str, provider: str | None = None) -> str:
        payload = json.dumps(
            {"judge_model": model, "judge_provider": provider, "expectation": expectation, "content": content},
            sort_keys=True,
        )
        return "judge:" + hashlib.sha256(payload.encode()).hexdigest()

    def _resolve_cassette(self, filename: str, qualname: str) -> None:
        here = Path(filename).parent
        if self.cassette is None:
            self.cassette = here / "cassettes" / f"{qualname.replace('.', '_')}.json"
        elif not self.cassette.is_absolute():
            self.cassette = here / self.cassette

    def __enter__(self) -> "AgentRecordFake":
        caller = sys._getframe(1).f_code
        self._resolve_cassette(caller.co_filename, caller.co_qualname)
        return self

    def __exit__(self, *_exc: Any) -> bool:
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
