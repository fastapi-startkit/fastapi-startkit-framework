from functools import partial
from typing import cast

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncTransaction

from fastapi_startkit.masoniteorm.connections.transactions import TransactionRecord, TransactionsManager


class FakeConnection:
    def __init__(self):
        self.stack: list[AsyncTransaction] = []

    @property
    def connection(self) -> AsyncConnection:
        return cast(AsyncConnection, cast(object, self))

    def get_transaction(self):
        return self.stack[0] if self.stack else None

    def get_nested_transaction(self):
        return self.stack[-1] if len(self.stack) > 1 else None


def new_transaction() -> AsyncTransaction:
    return cast(AsyncTransaction, object())


def begin(manager: TransactionsManager, fake: FakeConnection) -> AsyncTransaction:
    transaction = new_transaction()
    parent = fake.stack[-1] if fake.stack else None
    fake.stack.append(transaction)
    manager.begin(fake.connection, transaction, parent)
    return transaction


def end(fake: FakeConnection, transaction: AsyncTransaction):
    fake.stack.remove(transaction)


async def test_record_executes_sync_and_async_callbacks_in_order():
    called = []

    async def later():
        called.append("async")

    record = TransactionRecord()
    record.add_callback(partial(called.append, "sync"))
    record.add_callback(later)
    await record.execute_callbacks()
    assert called == ["sync", "async"]


def test_record_descends_from_ancestors_only():
    root = TransactionRecord()
    child = TransactionRecord(root)
    grandchild = TransactionRecord(child)
    assert grandchild.descends_from(root)
    assert grandchild.descends_from(child)
    assert not root.descends_from(child)
    assert not child.descends_from(TransactionRecord())


async def test_callback_without_transaction_runs_immediately():
    called = []
    await TransactionsManager().add_callback(None, partial(called.append, "now"))
    assert called == ["now"]


async def test_nested_commit_appends_to_parent_in_registration_order():
    manager, fake, called = TransactionsManager(), FakeConnection(), []
    root = begin(manager, fake)
    await manager.add_callback(fake.connection, partial(called.append, 1))
    child = begin(manager, fake)
    await manager.add_callback(fake.connection, partial(called.append, 2))
    end(fake, child)
    assert manager.commit(fake.connection, child) is None
    await manager.add_callback(fake.connection, partial(called.append, 3))
    end(fake, root)
    committed = manager.commit(fake.connection, root)
    assert committed is not None
    await committed.execute_callbacks()
    assert called == [1, 2, 3]
    assert manager.current(fake.connection) is None


async def test_rollback_discards_record_and_open_descendants():
    manager, fake, called = TransactionsManager(), FakeConnection(), []
    root = begin(manager, fake)
    await manager.add_callback(fake.connection, partial(called.append, "root"))
    child = begin(manager, fake)
    begin(manager, fake)
    await manager.add_callback(fake.connection, partial(called.append, "grandchild"))
    manager.rollback(fake.connection, child)
    fake.stack = [root]
    committed = manager.commit(fake.connection, root)
    assert committed is not None
    await committed.execute_callbacks()
    assert called == ["root"]


async def test_root_commit_collects_open_descendants():
    manager, fake, called = TransactionsManager(), FakeConnection(), []
    root = begin(manager, fake)
    await manager.add_callback(fake.connection, partial(called.append, "root"))
    begin(manager, fake)
    await manager.add_callback(fake.connection, partial(called.append, "child"))
    committed = manager.commit(fake.connection, root)
    assert committed is not None
    await committed.execute_callbacks()
    assert called == ["root", "child"]


async def test_untracked_parent_makes_savepoint_a_root():
    manager, fake, called = TransactionsManager(), FakeConnection(), []
    fake.stack.append(new_transaction())
    savepoint = begin(manager, fake)
    await manager.add_callback(fake.connection, partial(called.append, "savepoint"))
    committed = manager.commit(fake.connection, savepoint)
    assert committed is not None
    await committed.execute_callbacks()
    assert called == ["savepoint"]


def test_forget_drops_connection_records():
    manager, fake = TransactionsManager(), FakeConnection()
    begin(manager, fake)
    manager.forget(fake.connection)
    assert manager.current(fake.connection) is None
