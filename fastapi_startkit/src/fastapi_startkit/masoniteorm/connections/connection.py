import asyncio
from dataclasses import dataclass, field
from weakref import WeakKeyDictionary

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncTransaction

from fastapi_startkit.masoniteorm.models.builder import QueryBuilder


@dataclass
class _TaskConnectionState:
    connection: AsyncConnection | None = None
    transactions: list[AsyncTransaction] = field(default_factory=list)


class Connection:
    def __init__(self, engine: AsyncEngine, config: dict):
        self.config = config
        self.engine: AsyncEngine = engine
        self._task_states: WeakKeyDictionary[asyncio.Task, _TaskConnectionState] = WeakKeyDictionary()

    def _state(self) -> _TaskConnectionState:
        task = asyncio.current_task()
        if task is None:
            raise RuntimeError("Database operations require an active asyncio task")
        state = self._task_states.get(task)
        if state is None:
            state = _TaskConnectionState()
            self._task_states[task] = state
        return state

    @property
    def connection(self) -> AsyncConnection | None:
        return self._state().connection

    @property
    def transactions(self) -> list[AsyncTransaction]:
        return self._state().transactions

    def query(self) -> "QueryBuilder":
        return QueryBuilder(
            connection=self,
            grammar=self.get_query_grammar(),
            processor=self.get_post_processor(),
        )

    async def get_connection(self) -> AsyncConnection:
        state = self._state()
        if state.connection is None:
            state.connection = await self.engine.connect()

        return state.connection

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
        states = list(self._task_states.values())
        self._task_states.clear()
        for state in states:
            if state.connection is not None:
                await state.connection.close()
            state.transactions.clear()

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
        state = self._state()
        if state.transactions:
            assert state.connection is not None
            return await state.connection.execute(text(query), bindings or {})
        if state.connection is not None:
            result = await state.connection.execute(text(query), bindings or {})
            await state.connection.commit()
            return result

        async with self.engine.begin() as connection:
            return await connection.execute(text(query), bindings or {})

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

    async def _maybe_cleanup(self):
        state = self._state()
        if not state.transactions and state.connection:
            await state.connection.close()
            state.connection = None
