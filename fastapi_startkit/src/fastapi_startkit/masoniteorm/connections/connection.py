from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from inspect import isawaitable
from types import TracebackType
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncTransaction

from fastapi_startkit.masoniteorm.models.builder import QueryBuilder

if TYPE_CHECKING:
    from typing import Self

    from fastapi_startkit.masoniteorm.query.grammars.BaseGrammar import BaseGrammar
    from fastapi_startkit.masoniteorm.schema.platforms.Platform import Platform


AfterCommitCallback = Callable[[], object]


@dataclass
class _CallbackFrame:
    parent: AsyncTransaction | None
    callbacks: list[tuple[int, AfterCommitCallback]] = field(default_factory=list)
    next_order: int = 0


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

        parent = connection.get_nested_transaction() or connection.get_transaction()
        try:
            if connection.in_transaction():
                self.transaction = await connection.begin_nested()
            else:
                self.transaction = await connection.begin()
            self.owner._register_transaction(connection, self.transaction, parent)
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
        callbacks: list[AfterCommitCallback] = []
        was_active = self.transaction.is_active
        try:
            await self.transaction.__aexit__(exc_type, exc_value, traceback)
            if was_active:
                callbacks = self.owner._finish_transaction(self.connection, self.transaction, exc_type is None)
        except BaseException:
            self.owner._finish_transaction(self.connection, self.transaction, False)
            raise
        finally:
            current = self.owner.connection
            self.owner._connection_context.reset(self._token)
            if current is not None and current is not self.connection:
                self.owner._connection_context.set(current)
            if self._owns_connection:
                await self.owner._release_connection(self.connection)
        await self.owner._run_callbacks(callbacks)

    async def commit(self) -> None:
        assert self.connection is not None
        assert self.transaction is not None
        try:
            await self.transaction.commit()
        except BaseException:
            self.owner._finish_transaction(self.connection, self.transaction, False)
            raise
        callbacks = self.owner._finish_transaction(self.connection, self.transaction, True)
        if self._owns_connection and not self.connection.in_transaction():
            await self.owner._release_connection(self.connection)
        await self.owner._run_callbacks(callbacks)

    async def rollback(self) -> None:
        assert self.connection is not None
        assert self.transaction is not None
        try:
            await self.transaction.rollback()
        finally:
            self.owner._finish_transaction(self.connection, self.transaction, False)


class Connection:
    def __init__(self, engine: AsyncEngine, config: dict):
        self.config = config
        self.engine: AsyncEngine = engine
        self._transaction_callbacks: dict[AsyncConnection, dict[AsyncTransaction, _CallbackFrame]] = {}
        self._connection_context: ContextVar[AsyncConnection | None] = ContextVar(
            f"masoniteorm_connection_{id(self)}", default=None
        )

    @property
    def connection(self) -> AsyncConnection | None:
        connection = self._connection_context.get()
        if connection is not None and connection.closed:
            return None
        return connection

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

    @classmethod
    def get_query_grammar(cls) -> type[BaseGrammar] | None:
        return None

    @classmethod
    def get_post_processor(cls) -> type | None:
        return None

    @classmethod
    def get_default_platform(cls) -> type[Platform]:
        raise NotImplementedError

    async def after_commit(self, callback: AfterCommitCallback) -> None:
        if not callable(callback):
            raise TypeError("after_commit requires a callable")
        connection = self.connection
        transaction = None
        if connection is not None:
            transaction = connection.get_nested_transaction() or connection.get_transaction()
        if connection is None or transaction is None:
            await self._run_callbacks([callback])
            return
        frames = self._callback_frames(connection)
        frame = frames.get(transaction)
        if frame is None:
            await self._run_callbacks([callback])
            return
        root = frame
        while root.parent in frames:
            root = frames[root.parent]
        frame.callbacks.append((root.next_order, callback))
        root.next_order += 1

    def _callback_frames(self, connection: AsyncConnection) -> dict[AsyncTransaction, _CallbackFrame]:
        return self._transaction_callbacks.setdefault(connection, {})

    def _register_transaction(
        self, connection: AsyncConnection, transaction: AsyncTransaction, parent: AsyncTransaction | None
    ) -> None:
        frames = self._callback_frames(connection)
        if parent is None:
            frames.clear()
        frames[transaction] = _CallbackFrame(parent)

    def _finish_transaction(
        self, connection: AsyncConnection, transaction: AsyncTransaction, committed: bool
    ) -> list[AfterCommitCallback]:
        frames = self._transaction_callbacks.get(connection, {})
        frame = frames.pop(transaction, None)
        if frame is None:
            return []
        descendants = {transaction}
        callbacks = frame.callbacks
        for child, child_frame in list(frames.items()):
            if child_frame.parent in descendants:
                descendants.add(child)
                callbacks.extend(child_frame.callbacks)
                del frames[child]
        if not committed:
            if not frames:
                self._transaction_callbacks.pop(connection, None)
            return []
        if frame.parent in frames:
            frames[frame.parent].callbacks.extend(callbacks)
            return []
        self._transaction_callbacks.pop(connection, None)
        return [callback for _, callback in sorted(callbacks, key=lambda item: item[0])]

    @staticmethod
    async def _run_callbacks(callbacks: list[AfterCommitCallback]) -> None:
        for callback in callbacks:
            result = callback()
            if isawaitable(result):
                await result

    async def begin_transaction(self) -> None:
        connection = self.connection
        owns_connection = connection is None
        if connection is None:
            connection = await self.engine.connect()
            self._connection_context.set(connection)
        parent = connection.get_nested_transaction() or connection.get_transaction()
        try:
            transaction = await connection.begin_nested() if parent is not None else await connection.begin()
            self._register_transaction(connection, transaction, parent)
        except BaseException:
            if owns_connection:
                await self._release_connection(connection)
            raise

    async def commit_transaction(self) -> None:
        connection = self.connection
        if connection is None or not connection.in_transaction():
            raise RuntimeError("No active transaction to commit")
        transaction = connection.get_nested_transaction() or connection.get_transaction()
        assert transaction is not None
        try:
            await transaction.commit()
        except BaseException:
            self._finish_transaction(connection, transaction, False)
            raise
        callbacks = self._finish_transaction(connection, transaction, True)
        if not connection.in_transaction():
            await self._release_connection(connection)
        await self._run_callbacks(callbacks)

    async def rollback(self) -> None:
        connection = self.connection
        if connection is None or not connection.in_transaction():
            raise RuntimeError("No active transaction to rollback")
        transaction = connection.get_nested_transaction() or connection.get_transaction()
        assert transaction is not None
        try:
            await transaction.rollback()
        finally:
            self._finish_transaction(connection, transaction, False)
            if not connection.in_transaction():
                await self._release_connection(connection)

    async def _release_connection(self, connection: AsyncConnection) -> None:
        self._transaction_callbacks.pop(connection, None)
        try:
            await connection.close()
        finally:
            if self.connection is connection:
                self._connection_context.set(None)

    async def close(self) -> None:
        connection = self.connection
        if connection is not None:
            await self._release_connection(connection)

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
        return [dict(row) for row in result.mappings().all()]

    async def select_one(self, query: str, bindings: list | None = None) -> dict | None:
        result = await self.run(query, bindings)
        row = result.fetchone()
        return dict(zip(result.keys(), row)) if row else None

    async def statement(self, query: str, bindings: list | None = None) -> bool:
        query, params = self.sql_alchemy_bindings(query, bindings)
        await self._execute(query, params)
        return True
