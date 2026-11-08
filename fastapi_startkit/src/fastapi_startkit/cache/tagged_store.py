import hashlib
import secrets
from collections.abc import Callable, Iterable
from typing import Any

from .store import MISSING, Store


class TagSet:
    def __init__(self, store: Store, names: Iterable[str], key: Callable[[str], str]):
        self.store = store
        self.names = sorted(set(names))
        self.key = key

    def tag_key(self, name: str) -> str:
        return self.key(f"tag:{name}:key")

    async def tag_id(self, name: str) -> str:
        identifier = await self.store.get(self.tag_key(name))
        if identifier is MISSING:
            return await self.reset_tag(name)
        return identifier

    async def reset_tag(self, name: str) -> str:
        identifier = secrets.token_hex(12)
        await self.store.put(self.tag_key(name), identifier, None)
        return identifier

    async def namespace(self) -> str:
        identifiers = [await self.tag_id(name) for name in self.names]
        return hashlib.sha1("|".join(identifiers).encode()).hexdigest()

    async def reset(self) -> None:
        for name in self.names:
            await self.reset_tag(name)


class TaggedStore:
    def __init__(self, store: Store, tags: TagSet):
        self.store = store
        self.tags = tags

    async def tagged(self, key: str) -> str:
        return self.tags.key(f"{await self.tags.namespace()}:{key}")

    async def get(self, key: str) -> Any:
        return await self.store.get(await self.tagged(key))

    async def put(self, key: str, value: Any, seconds: float | None) -> bool:
        return await self.store.put(await self.tagged(key), value, seconds)

    async def forget(self, key: str) -> bool:
        return await self.store.forget(await self.tagged(key))

    async def flush(self) -> bool:
        await self.tags.reset()
        return True
