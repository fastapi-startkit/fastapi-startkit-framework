from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Middleware(Protocol):
    """An agent middleware layer.

    ``handler(model)`` returns a :class:`Response`. Return it (optionally with
    ``.then(callback)`` for an after-hook) to stay streaming-safe — do NOT
    ``await`` it, as awaiting buffers the whole stream. ``handle`` may be sync or
    ``async``; both are supported.
    """

    def handle(self, model: Any, handler: Callable) -> Any: ...


class Response:
    """Deferred response — the model only runs when consumed.

    - ``await response``              → buffered; returns the final message
    - ``async for chunk in response`` → streaming chunks
    - ``.then(cb)``                   → callback fired with the final value (sync or async)
    """

    def __init__(self, source: Callable[[], AsyncIterator]) -> None:
        self._source = source
        self._callbacks: list[Callable] = []

    def then(self, callback: Callable[[Any], Any]) -> "Response":
        self._callbacks.append(callback)
        return self

    async def _finish(self, final: Any) -> Any:
        for callback in self._callbacks:
            result = callback(final)
            if hasattr(result, "__await__"):
                await result
        return final

    @staticmethod
    def _merge(accumulated: Any, chunk: Any) -> Any:
        # Stream frames are dicts ({"type": "delta"/"tool_response", ...}); the
        # after-hooks want the joined text, not a dict sum.
        if isinstance(chunk, dict):
            text = chunk.get("text") or chunk.get("content") or ""
            return text if accumulated is None else accumulated + text
        return chunk if accumulated is None else accumulated + chunk

    def __aiter__(self) -> AsyncIterator:
        async def _it() -> AsyncIterator:
            accumulated = None
            finished = False
            try:
                async for chunk in self._source():
                    accumulated = self._merge(accumulated, chunk)
                    yield chunk
                finished = True
                await self._finish(accumulated)
            finally:
                # The consumer may close the stream before it is fully drained
                # (client disconnect, connection reuse, early break). Run the
                # after-hooks on close too, so they fire exactly once either way.
                if not finished:
                    await self._finish(accumulated)

        return _it()

    def __await__(self):
        async def _run() -> Any:
            accumulated = None
            async for chunk in self._source():
                accumulated = self._merge(accumulated, chunk)
            return await self._finish(accumulated)

        return _run().__await__()


def build_pipeline(middlewares: list[Callable], core: Callable) -> Callable:
    """Compose middlewares around core — first in list = outermost (the onion).

    Every layer (and the ``handler`` handed to each middleware) returns a
    :class:`Response`. A middleware may ``await`` it to buffer the full result,
    or — to stay streaming-safe — attach ``.then(callback)`` and return it
    without awaiting. Awaiting consumes the whole stream, so streaming after-hooks
    must use ``.then`` rather than ``final = await handler(model)``.
    """
    handler = core
    for mw in reversed(middlewares):
        nxt = handler
        instance = mw() if isinstance(mw, type) else mw
        call = instance.handle if hasattr(instance, "handle") else instance

        def layer(model: Any, call: Callable = call, nxt: Callable = nxt) -> Response:
            async def _source() -> AsyncIterator:
                produced = call(model, nxt)
                if not isinstance(produced, Response) and hasattr(produced, "__await__"):
                    produced = await produced
                if isinstance(produced, Response):
                    async for chunk in produced:
                        yield chunk
                else:
                    yield produced

            return Response(_source)

        handler = layer
    return handler
