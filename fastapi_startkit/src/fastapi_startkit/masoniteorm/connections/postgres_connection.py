import datetime
from typing import Any

from sqlalchemy import event
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from fastapi_startkit.masoniteorm.config.config import DBConfig
from fastapi_startkit.masoniteorm.exceptions import LockTimeoutError
from fastapi_startkit.masoniteorm.query.grammars import PostgresGrammar
from fastapi_startkit.masoniteorm.query.processors import PostgresPostProcessor
from fastapi_startkit.masoniteorm.schema.platforms import PostgresPlatform
from .advisory_lock import LOCK_NOT_AVAILABLE, advisory_lock_key, lock_timeout_value
from .connection import Connection

POSTGRES_EPOCH = datetime.datetime(2000, 1, 1)
POSTGRES_INFINITY = 2**63 - 1
POSTGRES_NEGATIVE_INFINITY = -(2**63)


def encode_timestamp(value: datetime.datetime) -> tuple[int]:
    if value.tzinfo is not None:
        value = value.astimezone(datetime.UTC).replace(tzinfo=None)
    if value == datetime.datetime.max:
        return (POSTGRES_INFINITY,)
    if value == datetime.datetime.min:
        return (POSTGRES_NEGATIVE_INFINITY,)
    days = value.toordinal() - POSTGRES_EPOCH.toordinal()
    seconds = days * 86400 + value.hour * 3600 + value.minute * 60 + value.second
    return (seconds * 1_000_000 + value.microsecond,)


def decode_timestamp(value: tuple[int]) -> datetime.datetime:
    (microseconds,) = value
    if microseconds == POSTGRES_INFINITY:
        return datetime.datetime.max
    if microseconds == POSTGRES_NEGATIVE_INFINITY:
        return datetime.datetime.min
    return POSTGRES_EPOCH + datetime.timedelta(microseconds=microseconds)


async def register_timestamp_codec(connection: Any) -> None:
    await connection.set_type_codec(
        "timestamp",
        schema="pg_catalog",
        encoder=encode_timestamp,
        decoder=decode_timestamp,
        format="tuple",
    )


class PostgresConnection(Connection):
    """Async PostgreSQL connection backed by asyncpg via SQLAlchemy."""

    def __init__(self, engine: AsyncEngine, config: DBConfig):
        super().__init__(engine, config)
        event.listen(engine.sync_engine, "connect", self.on_connect)

    @staticmethod
    def on_connect(dbapi_connection: Any, connection_record: Any) -> None:
        dbapi_connection.run_async(register_timestamp_codec)

    async def insert_get_id(self, query: str, bindings: list | None = None) -> int | None:
        result = await self.run(query, bindings)
        row = result.fetchone()
        return row[0] if row is not None else None

    async def advisory_lock(self, key: str | int, timeout_ms: int | None = None) -> None:
        lock_key = advisory_lock_key(key)
        timeout = None if timeout_ms is None else lock_timeout_value(timeout_ms)
        self._require_transaction("advisory_lock")
        if timeout is not None:
            await self._set_lock_timeout(timeout)
        try:
            await self.statement("SELECT pg_advisory_xact_lock(?)", [lock_key])
        except DBAPIError as error:
            if getattr(error.orig, "sqlstate", None) == LOCK_NOT_AVAILABLE:
                raise LockTimeoutError(key, timeout_ms) from error
            raise

    async def lock_timeout(self, timeout_ms: int) -> None:
        value = lock_timeout_value(timeout_ms)
        self._require_transaction("lock_timeout")
        await self._set_lock_timeout(value)

    async def _set_lock_timeout(self, value: str) -> None:
        await self.statement("SELECT set_config('lock_timeout', ?, true)", [value])

    def _require_transaction(self, operation: str) -> None:
        connection = self.connection
        if connection is None or not connection.in_transaction():
            raise RuntimeError(f"{operation} requires an open transaction on the [{self.config.driver}] connection")

    @classmethod
    def get_query_grammar(cls) -> type[PostgresGrammar]:
        return PostgresGrammar

    @classmethod
    def get_default_platform(cls):
        return PostgresPlatform

    @classmethod
    def get_post_processor(cls) -> type[PostgresPostProcessor]:
        return PostgresPostProcessor
