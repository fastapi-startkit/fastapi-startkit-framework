from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

from fastapi_startkit.masoniteorm.config.config import DBConfig

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from fastapi_startkit.masoniteorm.connections.manages_transactions import ManagesTransactions, Transaction
from fastapi_startkit.masoniteorm.connections.transactions import AfterCommitCallback, TransactionsManager
from fastapi_startkit.masoniteorm.models.builder import QueryBuilder

if TYPE_CHECKING:
    from fastapi_startkit.masoniteorm.query.grammars.BaseGrammar import BaseGrammar
    from fastapi_startkit.masoniteorm.schema.platforms.Platform import Platform

__all__ = ["AfterCommitCallback", "Connection", "Transaction"]


class Connection(ManagesTransactions):
    def __init__(self, engine: AsyncEngine, config: DBConfig):
        self.config: DBConfig = config
        self.engine: AsyncEngine = engine
        self.transactions_manager: TransactionsManager = TransactionsManager()
        self._connection_context: ContextVar[AsyncConnection | None] = ContextVar(
            f"masoniteorm_connection_{id(self)}", default=None
        )

    def query(self) -> QueryBuilder[Any]:
        return QueryBuilder(
            connection=self,
            grammar=self.get_query_grammar(),
            processor=self.get_post_processor(),
        )

    async def get_connection(self) -> AsyncConnection:
        return self.connection or await self.engine.connect()

    @classmethod
    def get_query_grammar(cls) -> type[BaseGrammar] | None:
        return None

    @classmethod
    def get_post_processor(cls) -> type | None:
        return None

    @classmethod
    def get_default_platform(cls) -> type[Platform]:
        raise NotImplementedError

    async def close(self) -> None:
        connection = self.connection
        if connection is not None:
            await self._release_connection(connection)

    async def reconnect(self) -> None:
        await self.close()

    @classmethod
    def prepare_binding(cls, value: Any) -> Any:
        return value

    @classmethod
    def sql_alchemy_bindings(cls, query: str, bindings: list[Any] | None = None):
        params: dict[str, Any] = {}
        if bindings:
            for i, val in enumerate(bindings):
                name = f"p{i}"
                params[name] = cls.prepare_binding(val)
                query = query.replace("?", f":{name}", 1)
        return (query, params)

    async def run(self, query: str, bindings: list[Any] | None = None):
        query, params = self.sql_alchemy_bindings(query, bindings)
        return await self._execute(query, params)

    async def execute(self, query: str, bindings: list[Any] | None = None):
        query, params = self.sql_alchemy_bindings(query, bindings)
        return await self._execute(query, params)

    async def _execute(self, query: str, bindings: dict[str, Any]):
        connection = self.connection
        if connection is not None:
            return await connection.execute(text(query), bindings or {})
        async with self.engine.begin() as operation_connection:
            return await operation_connection.execute(text(query), bindings or {})

    async def insert(self, query: str, bindings: list[Any] | None = None) -> int | None:
        result = await self.execute(query, bindings)
        return getattr(result, "lastrowid", None)

    async def insert_get_id(self, query: str, bindings: list[Any] | None = None) -> int | None:
        result = await self.execute(query, bindings)
        return getattr(result, "lastrowid", None)

    async def update(self, query: str, bindings: list[Any] | None = None) -> int:
        result = await self.execute(query, bindings)
        return result.rowcount  # type: ignore[return-value]

    async def delete(self, query: str, bindings: list[Any] | None = None) -> int:
        result = await self.execute(query, bindings)
        return result.rowcount  # type: ignore[return-value]

    async def select(self, query: str, bindings: list[Any] | None = None) -> list[dict[str, Any]]:
        result = await self.run(query, bindings)
        return [dict(row) for row in result.mappings().all()]

    async def select_one(self, query: str, bindings: list[Any] | None = None) -> dict[str, Any] | None:
        result = await self.run(query, bindings)
        row = result.fetchone()
        return dict(zip(result.keys(), row)) if row else None

    async def statement(self, query: str, bindings: list[Any] | None = None) -> bool:
        query, params = self.sql_alchemy_bindings(query, bindings)
        await self._execute(query, params)
        return True

    async def advisory_lock(self, key: str | int, timeout_ms: int | None = None) -> None:
        raise NotImplementedError(f"Advisory locks are only supported on Postgres, not the {self.config.driver} driver")

    async def lock_timeout(self, timeout_ms: int) -> None:
        raise NotImplementedError(f"lock_timeout is only supported on Postgres, not the {self.config.driver} driver")
