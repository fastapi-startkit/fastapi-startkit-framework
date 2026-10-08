import inspect
from collections.abc import Callable, Iterable
from typing import Any

from .prefix import apply_prefix


class Connection:
    def __init__(self, client: Any, name: str, prefix: str = ""):
        self.client = apply_prefix(client, prefix)
        self.name = name
        self.prefix = prefix

    def __getattr__(self, method: str) -> Any:
        if method.startswith("_"):
            raise AttributeError(method)
        return getattr(self.client, method)

    async def command(self, method: str, parameters: Iterable[Any] | None = None) -> Any:
        return await self.client.execute_command(method.upper(), *(parameters or []))

    def pipeline(self, callback: Callable[[Any], Any] | None = None) -> Any:
        return self._pipeline(False, callback)

    def transaction(self, callback: Callable[[Any], Any] | None = None) -> Any:
        return self._pipeline(True, callback)

    async def subscribe(self, channels: str | Iterable[str], callback: Callable[[Any, Any], Any]) -> None:
        await self._listen("subscribe", channels, callback)

    async def psubscribe(self, patterns: str | Iterable[str], callback: Callable[[Any, Any], Any]) -> None:
        await self._listen("psubscribe", patterns, callback)

    async def disconnect(self) -> None:
        await self.client.aclose()

    def _pipeline(self, transaction: bool, callback: Callable[[Any], Any] | None) -> Any:
        pipe = apply_prefix(self.client.pipeline(transaction=transaction), self.prefix)
        if callback is None:
            return pipe
        return self._execute(pipe, callback)

    async def _execute(self, pipe: Any, callback: Callable[[Any], Any]) -> list[Any]:
        async with pipe:
            await self._call(callback, pipe)
            return await pipe.execute()

    async def _listen(self, method: str, channels: str | Iterable[str], callback: Callable[[Any, Any], Any]) -> None:
        names = [channels] if isinstance(channels, str) else list(channels)
        pubsub = self.client.pubsub(ignore_subscribe_messages=True)
        try:
            await getattr(pubsub, method)(*names)
            async for message in pubsub.listen():
                await self._call(callback, message["data"], message["channel"])
        finally:
            await pubsub.aclose()

    @staticmethod
    async def _call(callback: Callable[..., Any], *args: Any) -> Any:
        result = callback(*args)
        if inspect.isawaitable(result):
            return await result
        return result
