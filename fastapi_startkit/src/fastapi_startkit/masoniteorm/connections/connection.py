from __future__ import annotations

from contextvars import ContextVar, Token
from types import TracebackType
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncTransaction

from fastapi_startkit.masoniteorm.models.builder import QueryBuilder

if TYPE_CHECKING:
    from typing import Self


class Transaction:
    def __init__(self, owner: Connection):
        self.owner = owner
        self.connection: AsyncConnection | None = None
        self.transaction: AsyncTransaction | None = None
        self._token: Token[AsyncConnection | None] | None = None
        self._owns_connection = False

    async def __aenter__(self) -> Self:
        connection = self.owner.connection
        if connection is None:
            connection = await self.owner.engine.connect()
            self._owns_connection = True
        self.connection = connection
        self._token = self.owner._connection_context.set(connection)

        try:
            if connection.in_transaction():
                self.transaction = await connection.begin_nested()
            else:
                self.transaction = await connection.begin()
        except BaseException:
            self.owner._connection_context.reset(self._token)
            if self._owns_connection:
                await connection.close()
            raise
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        assert self.connection is not None
        assert self.transaction is not None
        assert self._token is not None
        try:
            await self.transaction.__aexit__(exc_type, exc_value, traceback)
        finally:
            self.owner._connection_context.reset(self._token)
            if self._owns_connection:
                await self.connection.close()

    async def commit(self) -> None:
        assert self.transaction is not None
        await self.transaction.commit()

    async def rollback(self) -> None:
        assert self.transaction is not None
        await self.transaction.rollback()


class Connection:
    def __init__(self, engine: AsyncEngine, config: dict):
        self.config = config
        self.engine: AsyncEngine = engine
        self._connection_context: ContextVar[AsyncConnection | None] = ContextVar(
            f"masoniteorm_connection_{id(self)}", default=None
        )

    @property
    def connection(self) -> AsyncConnection | None:
        return self._connection_context.get()

    @property
    def transactions(self) -> list[AsyncTransaction]:
        connection = self.connection
        if connection is None:
            return []
        nested = connection.get_nested_transaction()
        root = connection.get_transaction()
        return [transaction for transaction in (root, nested) if transaction is not None]

    def transaction(self) -> Transaction:
        return Transaction(self)

    def query(self) -> QueryBuilder:
        return QueryBuilder(
            connection=self,
            grammar=self.get_query_grammar(),
            processor=self.get_post_processor(),
        )

    async def get_connection(self) -> AsyncConnection:
        return self.connection or await self.engine.connect()

    def get_query_grammar(cls):
        pass

    def get_post_processor(self):
        pass

    async def begin_transaction(self) -> None:
        connection = self.connection
        if connection is None:
            connection = await self.engine.connect()
            self._connection_context.set(connection)
        if connection.in_transaction():
            await connection.begin_nested()
        else:
            await connection.begin()

    async def commit_transaction(self) -> None:
        connection = self.connection
        if connection is None or not connection.in_transaction():
            raise RuntimeError("No active transaction to commit")
        nested = connection.get_nested_transaction()
        if nested is not None:
            await nested.commit()
        else:
            transaction = connection.get_transaction()
            assert transaction is not None
            await transaction.commit()
            await self._release_connection(connection)

    async def rollback(self) -> None:
        connection = self.connection
        if connection is None or not connection.in_transaction():
            raise RuntimeError("No active transaction to rollback")
        nested = connection.get_nested_transaction()
        if nested is not None:
            await nested.rollback()
        else:
            transaction = connection.get_transaction()
            assert transaction is not None
            await transaction.rollback()
            await self._release_connection(connection)

    async def _release_connection(self, connection: AsyncConnection) -> None:
        await connection.close()
        if self.connection is connection:
            self._connection_context.set(None)

    async def close(self) -> None:
        connection = self.connection
        if connection is not None:
            await connection.close()
            self._connection_context.set(None)

    async def reconnect(self) -> None:
        await self.close()

    @staticmethod
    def sql_alchemy_bindings(query: str, bindings: list | None = None):
        params = {}
        if bindings:
            for i, val in enumerate(bindings):
                name = f"p{i}"
                params[name] = val
                query = query.replace("?", f":{name}", 1)
        return (query, params)

    async def run(self, query: str, bindings: list | None = None):
        query, params = self.sql_alchemy_bindings(query, bindings)
        return await self._execute(query, params)

    async def execute(self, query: str, bindings: list | None = None):
        query, params = self.sql_alchemy_bindings(query, bindings)
        return await self._execute(query, params)

    async def _execute(self, query: str, bindings: dict):
        connection = self.connection
        if connection is not None:
            return await connection.execute(text(query), bindings or {})
        async with self.engine.begin() as operation_connection:
            return await operation_connection.execute(text(query), bindings or {})

    async def insert(self, query: str, bindings: list | None = None) -> int | None:
        result = await self.execute(query, bindings)
        return getattr(result, "lastrowid", None)

    async def insert_get_id(self, query: str, bindings: list | None = None) -> int | None:
        result = await self.execute(query, bindings)
        return getattr(result, "lastrowid", None)

    async def update(self, query: str, bindings: list | None = None) -> int:
        result = await self.execute(query, bindings)
        return result.rowcount  # type: ignore[return-value]

    async def delete(self, query: str, bindings: list | None = None) -> int:
        result = await self.execute(query, bindings)
        return result.rowcount  # type: ignore[return-value]

    async def select(self, query: str, bindings: list | None = None) -> list[dict]:
        result = await self.run(query, bindings)
        return result.mappings().all()

    async def select_one(self, query: str, bindings: list | None = None) -> dict | None:
        result = await self.run(query, bindings)
        row = result.fetchone()
        return dict(zip(result.keys(), row)) if row else None

    async def statement(self, query: str, bindings: list | None = None) -> bool:
        query, params = self.sql_alchemy_bindings(query, bindings)
        await self._execute(query, params)
        return True
