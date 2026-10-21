import datetime
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine

from fastapi_startkit.masoniteorm.config.config import DBConfig
from fastapi_startkit.masoniteorm.query.grammars import PostgresGrammar
from fastapi_startkit.masoniteorm.query.processors import PostgresPostProcessor
from fastapi_startkit.masoniteorm.schema.platforms import PostgresPlatform
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

    @classmethod
    def get_query_grammar(cls) -> type[PostgresGrammar]:
        return PostgresGrammar

    @classmethod
    def get_default_platform(cls):
        return PostgresPlatform

    @classmethod
    def get_post_processor(cls) -> type[PostgresPostProcessor]:
        return PostgresPostProcessor
