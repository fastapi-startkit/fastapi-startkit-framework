import base64
import math
import pickle
import time
from collections.abc import Callable
from typing import Any

from sqlalchemy.exc import IntegrityError

from fastapi_startkit.masoniteorm.connections.connection import Connection
from fastapi_startkit.masoniteorm.models.builder import QueryBuilder

from .lock import Lock
from .store import MISSING, expired, expires_at


def encode(value: Any) -> str:
    return base64.b64encode(pickle.dumps(value)).decode()


class DatabaseStore:
    def __init__(self, connection: Callable[[], Connection], table: str = "caches"):
        self.connection = connection
        self.table = table

    def query(self) -> QueryBuilder[Any]:
        return self.connection().query().table(self.table)

    async def get(self, key: str) -> Any:
        builder = self.query().where("key", key).limit(1)
        row = await builder.connection.select_one(builder.to_qmark(), list(builder.get_bindings()))
        if row is None:
            return MISSING

        try:
            value = pickle.loads(base64.b64decode(row["value"]))
        except Exception:
            await self.forget(key)
            return MISSING

        if expired(row["expiration"]):
            await self.forget(key)
            return MISSING
        return value

    async def put(self, key: str, value: Any, seconds: float | None) -> bool:
        expiration = expires_at(seconds)
        record = {"value": encode(value), "expiration": None if expiration is None else math.ceil(expiration)}
        if await self.query().where("key", key).update(record):
            return True
        try:
            await self.query().insert({"key": key, **record})
        except IntegrityError:
            await self.query().where("key", key).update(record)
        return True

    async def forget(self, key: str) -> bool:
        return bool(await self.query().where("key", key).delete())

    async def flush(self) -> bool:
        await self.query().delete()
        return True

    def lock(self, name: str, seconds: float = 0, owner: str | None = None) -> "DatabaseLock":
        return DatabaseLock(self, name, seconds, owner)


class DatabaseLock(Lock):
    def __init__(self, store: DatabaseStore, name: str, seconds: float = 0, owner: str | None = None):
        super().__init__(name, seconds, owner)
        self.store = store
        self.key = f"lock:{name}"

    async def acquire(self) -> bool:
        expiration = expires_at(self.ttl)
        record = {"value": encode(self.owner), "expiration": None if expiration is None else math.ceil(expiration)}
        try:
            await self.store.query().insert({"key": self.key, **record})
        except IntegrityError:
            expired_lock = self.store.query().where("key", self.key).where("expiration", "<=", time.time())
            return bool(await expired_lock.update(record))
        return True

    async def release(self) -> bool:
        return bool(await self.store.query().where("key", self.key).where("value", encode(self.owner)).delete())

    async def force_release(self) -> None:
        await self.store.query().where("key", self.key).delete()
