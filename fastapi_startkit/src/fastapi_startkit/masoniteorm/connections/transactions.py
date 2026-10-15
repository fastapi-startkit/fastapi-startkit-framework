from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from inspect import isawaitable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection, AsyncTransaction


AfterCommitCallback = Callable[[], object]


async def _invoke(callback: AfterCommitCallback) -> None:
    result = callback()
    if isawaitable(result):
        await result


@dataclass(eq=False)
class TransactionRecord:
    parent: TransactionRecord | None = None
    callbacks: list[AfterCommitCallback] = field(default_factory=list)

    def add_callback(self, callback: AfterCommitCallback) -> None:
        self.callbacks.append(callback)

    def descends_from(self, record: TransactionRecord) -> bool:
        parent = self.parent
        while parent is not None:
            if parent is record:
                return True
            parent = parent.parent
        return False

    async def execute_callbacks(self) -> None:
        for callback in self.callbacks:
            await _invoke(callback)


class TransactionsManager:
    def __init__(self) -> None:
        self._records: dict[AsyncConnection, dict[AsyncTransaction, TransactionRecord]] = {}

    def begin(
        self, connection: AsyncConnection, transaction: AsyncTransaction, parent: AsyncTransaction | None
    ) -> None:
        records = self._records.setdefault(connection, {})
        if parent is None:
            records.clear()
        records[transaction] = TransactionRecord(records.get(parent) if parent is not None else None)

    def commit(self, connection: AsyncConnection, transaction: AsyncTransaction) -> TransactionRecord | None:
        record = self._detach(connection, transaction)
        if record is None:
            return None
        if record.parent is not None:
            record.parent.callbacks.extend(record.callbacks)
            return None
        self.forget(connection)
        return record

    def rollback(self, connection: AsyncConnection, transaction: AsyncTransaction) -> None:
        _ = self._detach(connection, transaction)

    async def add_callback(self, connection: AsyncConnection | None, callback: AfterCommitCallback) -> None:
        record = self.current(connection)
        if record is None:
            await _invoke(callback)
        else:
            record.add_callback(callback)

    def current(self, connection: AsyncConnection | None) -> TransactionRecord | None:
        if connection is None:
            return None
        transaction = connection.get_nested_transaction() or connection.get_transaction()
        if transaction is None:
            return None
        return self._records.get(connection, {}).get(transaction)

    def forget(self, connection: AsyncConnection) -> None:
        _ = self._records.pop(connection, None)

    def _detach(self, connection: AsyncConnection, transaction: AsyncTransaction) -> TransactionRecord | None:
        records = self._records.get(connection, {})
        record = records.pop(transaction, None)
        if record is None:
            return None
        for child_transaction, child in list(records.items()):
            if child.descends_from(record):
                record.callbacks.extend(child.callbacks)
                del records[child_transaction]
        if not records:
            self.forget(connection)
        return record
