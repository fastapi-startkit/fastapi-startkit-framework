from typing import List

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncTransaction

from fastapi_startkit.masoniteorm.models.builder import QueryBuilder


class Connection:
    def __init__(self, engine: AsyncEngine, config: dict):
        self.config = config
        self.engine: AsyncEngine = engine
        self.connection: AsyncConnection | None = None
        self.transactions: List[AsyncTransaction] = []

    def query(self) -> "QueryBuilder":
        return QueryBuilder(
            connection=self,
            grammar=self.get_query_grammar(),
            processor=self.get_post_processor(),
        )

    async def get_connection(self) -> AsyncConnection:
        if self.connection is None:
            self.connection = await self.engine.connect()

        assert self.connection is not None
        return self.connection

    def get_query_grammar(cls):
        pass

    def get_post_processor(self):
        pass

    async def begin_transaction(self) -> None:
        connection = await self.get_connection()

        if not self.transactions:
            transaction = await connection.begin()
        else:
            transaction = await connection.begin_nested()

        self.transactions.append(transaction)

    async def commit_transaction(self) -> None:
        if not self.transactions:
            raise RuntimeError("No active transaction to commit")

        transaction = self.transactions.pop()
        await transaction.commit()

        await self._maybe_cleanup()

    async def rollback(self) -> None:
        if not self.transactions:
            raise RuntimeError("No active transaction to rollback")

        transaction = self.transactions.pop()
        await transaction.rollback()

        await self._maybe_cleanup()

    async def close(self) -> None:
        if self.connection is not None:
            await self.connection.close()
            self.connection = None
        self.transactions = []

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
        query, bindings = self.sql_alchemy_bindings(query, bindings)

        conn = await self.get_connection()
        result = await conn.execute(text(query), bindings or {})

        if not self.transactions:
            await conn.commit()

        return result

    async def execute(self, query: str, bindings: list | None = None):
        query, bindings = self.sql_alchemy_bindings(query, bindings)

        conn = await self.get_connection()
        result = await conn.execute(text(query), bindings or {})

        if not self.transactions:
            await conn.commit()

        return result

    async def insert(self, query: str, bindings: list | None = None) -> int | None:
        result = await self.execute(query, bindings)

        return getattr(result, "lastrowid", None)

    async def insert_get_id(self, query: str, bindings: list | None = None) -> int | None:
        result = await self.execute(query, bindings)
        return getattr(result, "lastrowid", None)

    async def upsert(self, statement) -> int:
        """Execute a prepared SQLAlchemy upsert construct.

        ``statement`` is a fully-bound Core ``Insert`` construct (the dialect
        specific ON CONFLICT / ON DUPLICATE KEY clause is already attached), so
        no extra bindings are needed. Returns the number of affected rows.
        """
        conn = await self.get_connection()
        result = await conn.execute(statement)

        if not self.transactions:
            await conn.commit()

        return result.rowcount

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
        result_dict = dict(zip(result.keys(), row)) if row else None
        if not self.transactions and self.connection is not None:
            await self.connection.commit()
        return result_dict

    async def statement(self, query: str, bindings: list | None = None) -> bool:
        query, bindings = self.sql_alchemy_bindings(query, bindings)

        conn = await self.get_connection()
        await conn.execute(text(query), bindings or {})

        # Only commit if NOT inside a transaction
        if not self.transactions:
            await conn.commit()

        return True

    async def _maybe_cleanup(self):
        if not self.transactions and self.connection:
            await self.connection.close()
            self.connection = None
