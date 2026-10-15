from __future__ import annotations

from contextvars import ContextVar
from types import TracebackType
from typing import TYPE_CHECKING

from fastapi_startkit.masoniteorm.connections.transactions import AfterCommitCallback, TransactionsManager

if TYPE_CHECKING:
    from typing import Self

    from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncTransaction


class Transaction:
    def __init__(self, owner: ManagesTransactions):
        self.owner = owner
        self.transaction: AsyncTransaction | None = None

    async def __aenter__(self) -> Self:
        self.transaction = await self.owner.begin_transaction()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        transaction = self._started()
        if not transaction.is_active:
            await self.owner._release_if_idle(transaction.connection)
        elif exc_type is None:
            await self.owner.commit_transaction(transaction)
        else:
            await self.owner.rollback(transaction)

    async def commit(self) -> None:
        await self.owner.commit_transaction(self._started())

    async def rollback(self) -> None:
        await self.owner.rollback(self._started())

    def _started(self) -> AsyncTransaction:
        if self.transaction is None:
            raise RuntimeError("Transaction has not been started")
        return self.transaction


class ManagesTransactions:
    engine: AsyncEngine
    transactions_manager: TransactionsManager
    _connection_context: ContextVar[AsyncConnection | None]

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

    async def begin_transaction(self) -> AsyncTransaction:
        connection = self.connection
        owns_connection = connection is None
        if connection is None:
            connection = await self.engine.connect()
            _ = self._connection_context.set(connection)
        parent = connection.get_nested_transaction() or connection.get_transaction()
        try:
            transaction = await connection.begin_nested() if parent is not None else await connection.begin()
        except BaseException:
            if owns_connection:
                await self._release_connection(connection)
            raise
        self.transactions_manager.begin(connection, transaction, parent)
        return transaction

    async def commit_transaction(self, transaction: AsyncTransaction | None = None) -> None:
        transaction = transaction or self._innermost_transaction("commit")
        connection = transaction.connection
        try:
            await transaction.commit()
        except BaseException:
            self.transactions_manager.rollback(connection, transaction)
            raise
        committed = self.transactions_manager.commit(connection, transaction)
        await self._release_if_idle(connection)
        if committed is not None:
            await committed.execute_callbacks()

    async def rollback(self, transaction: AsyncTransaction | None = None) -> None:
        transaction = transaction or self._innermost_transaction("rollback")
        connection = transaction.connection
        try:
            await transaction.rollback()
        finally:
            self.transactions_manager.rollback(connection, transaction)
            await self._release_if_idle(connection)

    async def after_commit(self, callback: AfterCommitCallback) -> None:
        if not callable(callback):
            raise TypeError("after_commit requires a callable")
        await self.transactions_manager.add_callback(self.connection, callback)

    def _innermost_transaction(self, action: str) -> AsyncTransaction:
        connection = self.connection
        transaction = connection and (connection.get_nested_transaction() or connection.get_transaction())
        if transaction is None:
            raise RuntimeError(f"No active transaction to {action}")
        return transaction

    async def _release_if_idle(self, connection: AsyncConnection) -> None:
        if not connection.in_transaction():
            await self._release_connection(connection)

    async def _release_connection(self, connection: AsyncConnection) -> None:
        self.transactions_manager.forget(connection)
        try:
            await connection.close()
        finally:
            if self.connection is connection:
                _ = self._connection_context.set(None)
