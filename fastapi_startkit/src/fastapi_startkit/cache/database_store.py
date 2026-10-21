import base64
import math
import pickle
from collections.abc import Callable
from typing import Any

from sqlalchemy.exc import IntegrityError

from fastapi_startkit.masoniteorm.connections.connection import Connection
from fastapi_startkit.masoniteorm.models.builder import QueryBuilder

from .store import MISSING, expired, expires_at


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
        except (pickle.UnpicklingError, EOFError, ValueError, TypeError):
            await self.forget(key)
            return MISSING

        if expired(row["expiration"]):
            await self.forget(key)
            return MISSING
        return value

    async def put(self, key: str, value: Any, seconds: float | None) -> bool:
        expiration = expires_at(seconds)
        record = {
            "value": base64.b64encode(pickle.dumps(value)).decode(),
            "expiration": None if expiration is None else math.ceil(expiration),
        }
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
