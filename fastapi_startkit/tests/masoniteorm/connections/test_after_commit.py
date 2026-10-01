import asyncio
from contextvars import Context
from functools import partial
from unittest.mock import patch

import pytest
from sqlalchemy.exc import PendingRollbackError
from sqlalchemy.ext.asyncio import AsyncTransaction, create_async_engine

from fastapi_startkit.masoniteorm.connections.sqlite_connection import SQliteConnection
from fastapi_startkit.masoniteorm.facades.DB import DB


@pytest.fixture
async def connection(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'callbacks.sqlite3'}", pool_size=1, max_overflow=0)
    conn = SQliteConnection(engine, {"driver": "sqlite"})
    await conn.statement("CREATE TABLE records (id INTEGER)")
    try:
        yield conn
    finally:
        await conn.close()
        await engine.dispose()


async def test_immediate_sync_async_and_returned_awaitable(connection):
    called = []

    async def callback():
        await asyncio.sleep(0)
        called.append("async")

    await connection.after_commit(partial(called.append, "sync"))
    await connection.after_commit(callback)
    await connection.after_commit(lambda: callback())
    assert called == ["sync", "async", "async"]


async def test_rejects_non_callable(connection):
    with pytest.raises(TypeError, match="requires a callable"):
        await connection.after_commit(None)


@pytest.mark.parametrize("mode", ["manual", "context", "object"])
async def test_commit_releases_connection_and_callbacks_see_durable_data(connection, mode):
    called = []

    async def callback():
        assert connection.connection is None
        assert await connection.select("SELECT id FROM records") == [{"id": 1}]
        async with connection.transaction():
            await connection.statement("INSERT INTO records VALUES (2)")
        called.append("async")

    async def register():
        await connection.statement("INSERT INTO records VALUES (1)")
        await connection.after_commit(partial(called.append, "sync"))
        await connection.after_commit(callback)
        assert called == []

    if mode == "manual":
        await connection.begin_transaction()
        await register()
        await connection.commit_transaction()
    else:
        async with connection.transaction() as transaction:
            await register()
            if mode == "object":
                await transaction.commit()
    assert called == ["sync", "async"]
    assert connection.connection is None
    assert await connection.select("SELECT id FROM records ORDER BY id") == [{"id": 1}, {"id": 2}]


@pytest.mark.parametrize("mode", ["manual", "context", "object"])
async def test_rollback_discards_callbacks(connection, mode):
    called = []
    if mode == "manual":
        await connection.begin_transaction()
        await connection.after_commit(partial(called.append, "discard"))
        await connection.rollback()
    else:
        try:
            async with connection.transaction() as transaction:
                await connection.after_commit(partial(called.append, "discard"))
                if mode == "object":
                    await transaction.rollback()
                else:
                    raise ValueError("abort")
        except ValueError:
            pass
    async with connection.transaction():
        await connection.after_commit(partial(called.append, "next"))
    assert called == ["next"]


@pytest.mark.parametrize("mode", ["manual", "context", "object"])
@pytest.mark.parametrize("rollback", [False, True])
async def test_nested_callbacks_defer_and_rollback_is_scoped(connection, mode, rollback):
    called = []
    async with connection.transaction():
        await connection.statement("INSERT INTO records VALUES (1)")
        await connection.after_commit(partial(called.append, "before"))
        if mode == "manual":
            await connection.begin_transaction()
            await connection.after_commit(partial(called.append, "nested"))
            if rollback:
                await connection.rollback()
            else:
                await connection.commit_transaction()
        else:
            try:
                async with connection.transaction() as transaction:
                    await connection.after_commit(partial(called.append, "nested"))
                    if mode == "object":
                        if rollback:
                            await transaction.rollback()
                        else:
                            await transaction.commit()
                    elif rollback:
                        raise ValueError("abort")
            except ValueError:
                pass
        assert called == []
        await connection.after_commit(partial(called.append, "after"))
    assert called == (["before", "after"] if rollback else ["before", "nested", "after"])


async def test_deep_savepoints_preserve_order(connection):
    called = []
    await connection.begin_transaction()
    await connection.statement("INSERT INTO records VALUES (1)")
    for value in [1, 2, 3]:
        await connection.after_commit(partial(called.append, value))
        await connection.begin_transaction()
    await connection.after_commit(partial(called.append, 4))
    for _ in range(3):
        await connection.commit_transaction()
        assert called == []
    await connection.commit_transaction()
    assert called == [1, 2, 3, 4]


async def test_outer_rollback_discards_committed_nested_callbacks(connection):
    called = []
    await connection.begin_transaction()
    await connection.statement("INSERT INTO records VALUES (1)")
    async with connection.transaction():
        await connection.after_commit(partial(called.append, "inner"))
    await connection.rollback()
    async with connection.transaction():
        pass
    assert called == []


@pytest.mark.parametrize("explicit", [False, True])
async def test_ancestor_commit_includes_open_savepoint_callbacks(connection, explicit):
    called = []
    async with connection.transaction() as root:
        await connection.statement("INSERT INTO records VALUES (1)")
        await connection.after_commit(partial(called.append, "root"))
        await connection.begin_transaction()
        await connection.after_commit(partial(called.append, "child"))
        await connection.begin_transaction()
        await connection.after_commit(partial(called.append, "grandchild"))
        if explicit:
            await root.commit()
    assert called == ["root", "child", "grandchild"]


@pytest.mark.parametrize("mode", ["manual", "context", "object"])
async def test_callback_error_propagates_after_commit_without_queue_leak(connection, mode):
    called = []

    async def fail():
        raise ValueError("callback failed")

    async def register():
        await connection.statement("INSERT INTO records VALUES (1)")
        await connection.after_commit(fail)
        await connection.after_commit(partial(called.append, "skip"))

    with pytest.raises(ValueError, match="callback failed"):
        if mode == "manual":
            await connection.begin_transaction()
            await register()
            await connection.commit_transaction()
        else:
            async with connection.transaction() as transaction:
                await register()
                if mode == "object":
                    await transaction.commit()
    assert connection.connection is None
    assert await connection.select("SELECT id FROM records") == [{"id": 1}]
    async with connection.transaction():
        await connection.after_commit(partial(called.append, "next"))
    assert called == ["next"]


@pytest.mark.parametrize("mode", ["manual", "object"])
async def test_failed_commit_discards_callbacks(connection, mode):
    called = []
    with patch.object(AsyncTransaction, "commit", side_effect=RuntimeError("commit failed")):
        with pytest.raises(RuntimeError, match="commit failed"):
            if mode == "manual":
                await connection.begin_transaction()
                await connection.after_commit(partial(called.append, "failed"))
                await connection.commit_transaction()
            else:
                async with connection.transaction() as transaction:
                    await connection.after_commit(partial(called.append, "failed"))
                    await transaction.commit()
    await connection.close()
    async with connection.transaction():
        await connection.after_commit(partial(called.append, "next"))
    assert called == ["next"]


@pytest.mark.parametrize("method", ["close", "reconnect"])
async def test_close_discards_callbacks(connection, method):
    called = []
    await connection.begin_transaction()
    await connection.after_commit(partial(called.append, "discard"))
    await getattr(connection, method)()
    async with connection.transaction():
        await connection.after_commit(partial(called.append, "next"))
    assert called == ["next"]


async def test_cancelled_transaction_discards_callbacks(connection):
    called = []
    ready = asyncio.Event()

    async def worker():
        async with connection.transaction():
            await connection.after_commit(partial(called.append, "discard"))
            ready.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(worker())
    await ready.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    async with connection.transaction():
        await connection.after_commit(partial(called.append, "next"))
    assert called == ["next"]


async def test_inherited_task_joins_parent_and_clean_context_is_isolated(connection):
    called = []
    async with connection.transaction():
        await asyncio.create_task(connection.after_commit(partial(called.append, "inherited")))
        await Context().run(asyncio.create_task, connection.after_commit(partial(called.append, "isolated")))
        assert called == ["isolated"]
    assert called == ["isolated", "inherited"]


async def test_independent_tasks_have_separate_callback_queues(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'tasks.sqlite3'}", pool_size=2)
    connection = SQliteConnection(engine, {"driver": "sqlite"})
    ready = asyncio.Event()
    committed = asyncio.Event()
    called = []

    async def committing():
        await connection.begin_transaction()
        await connection.after_commit(partial(called.append, "commit"))
        await ready.wait()
        await connection.commit_transaction()
        committed.set()

    async def rolling_back():
        await connection.begin_transaction()
        await connection.after_commit(partial(called.append, "rollback"))
        ready.set()
        await committed.wait()
        assert called == ["commit"]
        await connection.rollback()

    try:
        await asyncio.gather(committing(), rolling_back())
        assert called == ["commit"]
    finally:
        await engine.dispose()


async def test_facade_default_and_named_connections(connection, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'other.sqlite3'}")
    other = SQliteConnection(engine, {"driver": "sqlite"})
    called = []
    with patch.object(DB, "instance") as instance:
        instance.return_value.connection.side_effect = lambda name=None: other if name == "other" else connection
        async with connection.transaction():
            async with other.transaction():
                await DB.after_commit(partial(called.append, "default"))
                await DB.after_commit(partial(called.append, "other"), name="other")
                assert called == []
            assert called == ["other"]
        assert called == ["other", "default"]
    await engine.dispose()


async def test_inherited_task_can_query_after_parent_exits(connection):
    ready = asyncio.Event()

    async def child():
        await ready.wait()
        await connection.after_commit(lambda: None)
        return await connection.select("SELECT 1 AS value")

    async with connection.transaction():
        task = asyncio.create_task(child())
    ready.set()
    assert await task == [{"value": 1}]


async def test_callback_manual_transaction_survives_old_context_exit(connection):
    called = []

    async def callback():
        await connection.begin_transaction()
        await connection.statement("INSERT INTO records VALUES (2)")
        await connection.after_commit(partial(called.append, "new"))

    async with connection.transaction() as transaction:
        await connection.after_commit(callback)
        await transaction.commit()
        replacement = connection.connection
    assert connection.connection is replacement
    assert replacement is not None
    await connection.commit_transaction()
    assert called == ["new"]
    assert await connection.select("SELECT id FROM records") == [{"id": 2}]


@pytest.mark.parametrize("mode", ["manual", "context", "object"])
async def test_invalidated_connection_discards_callbacks_and_can_be_closed(connection, mode):
    called = []
    with pytest.raises(PendingRollbackError):
        if mode == "manual":
            await connection.begin_transaction()
            await connection.after_commit(partial(called.append, "discard"))
            await connection.connection.invalidate()
            await connection.commit_transaction()
        else:
            async with connection.transaction() as transaction:
                await connection.after_commit(partial(called.append, "discard"))
                await connection.connection.invalidate()
                if mode == "object":
                    await transaction.commit()
    await connection.close()
    assert connection.connection is None
    async with connection.transaction():
        await connection.after_commit(partial(called.append, "next"))
    assert called == ["next"]


async def test_unregistered_transaction_runs_callback_immediately(connection):
    called = []
    raw = await connection.engine.connect()
    connection._connection_context.set(raw)
    await raw.begin()
    await connection.after_commit(partial(called.append, "immediate"))
    assert called == ["immediate"]
    await connection.close()


async def test_savepoint_in_unregistered_transaction_does_not_raise(connection):
    called = []
    raw = await connection.engine.connect()
    connection._connection_context.set(raw)
    await raw.begin()
    async with connection.transaction():
        await connection.after_commit(partial(called.append, "savepoint"))
    assert called == ["savepoint"]
    await connection.close()


async def test_nested_rollback_then_new_registration_keeps_order(connection):
    called = []
    async with connection.transaction():
        await connection.after_commit(partial(called.append, 1))
        await connection.begin_transaction()
        await connection.after_commit(partial(called.append, "discard"))
        await connection.rollback()
        await connection.after_commit(partial(called.append, 2))
    assert called == [1, 2]
