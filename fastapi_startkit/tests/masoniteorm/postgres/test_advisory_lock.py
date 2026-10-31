import asyncio
from contextvars import Context

import pytest
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from fastapi_startkit.masoniteorm import LockTimeoutError, PostgresConfig
from fastapi_startkit.masoniteorm.connections.advisory_lock import advisory_lock_key
from fastapi_startkit.masoniteorm.connections.postgres_connection import PostgresConnection

from .fixtures.db import URL

KEY = "tests:advisory-lock"


def make_connection(**engine_options) -> PostgresConnection:
    engine = create_async_engine(URL, **engine_options)
    return PostgresConnection(engine, PostgresConfig(driver="postgres", url=URL, database="database_app_test"))


@pytest.fixture
async def connection():
    connection = make_connection()
    try:
        yield connection
    finally:
        await connection.close()
        await connection.engine.dispose()


async def is_locked(connection: PostgresConnection, key: str | int) -> bool:
    async def probe() -> bool:
        async with connection.transaction():
            row = await connection.select_one(
                "SELECT pg_try_advisory_xact_lock(?) AS acquired", [advisory_lock_key(key)]
            )
            return not row["acquired"]

    return await asyncio.create_task(probe(), context=Context())


async def hold(connection: PostgresConnection, key: str | int, acquired: asyncio.Event, release: asyncio.Event):
    async with connection.transaction():
        await connection.advisory_lock(key)
        acquired.set()
        await release.wait()


async def test_lock_is_held_inside_the_transaction(connection):
    async with connection.transaction():
        await connection.advisory_lock(KEY)
        assert await is_locked(connection, KEY)
        assert not await is_locked(connection, "tests:other-key")


async def test_int_key_is_locked_as_is(connection):
    async with connection.transaction():
        await connection.advisory_lock(424242)
        row = await connection.select_one(
            "SELECT count(*) AS held FROM pg_locks WHERE locktype = 'advisory' AND pid = pg_backend_pid() "
            "AND classid = 0 AND objid = 424242 AND objsubid = 1"
        )
        assert row["held"] == 1


async def test_second_transaction_blocks_until_the_holder_commits(connection):
    acquired, release = asyncio.Event(), asyncio.Event()
    holder = asyncio.create_task(hold(connection, KEY, acquired, release))
    await acquired.wait()

    waiter_acquired, waiter_release = asyncio.Event(), asyncio.Event()
    waiter = asyncio.create_task(hold(connection, KEY, waiter_acquired, waiter_release))
    await asyncio.sleep(0.3)
    assert not waiter_acquired.is_set()

    release.set()
    await holder
    await asyncio.wait_for(waiter_acquired.wait(), timeout=2)
    waiter_release.set()
    await waiter


async def test_timeout_raises_lock_timeout_error(connection):
    acquired, release = asyncio.Event(), asyncio.Event()
    holder = asyncio.create_task(hold(connection, KEY, acquired, release))
    await acquired.wait()

    async def contend():
        async with connection.transaction():
            await connection.advisory_lock(KEY, timeout_ms=100)

    try:
        with pytest.raises(LockTimeoutError) as raised:
            await asyncio.wait_for(asyncio.create_task(contend()), timeout=5)
    finally:
        release.set()
        await holder

    assert raised.value.key == KEY
    assert raised.value.timeout_ms == 100
    assert isinstance(raised.value.__cause__, DBAPIError)
    assert connection.connection is None


async def test_lock_is_released_on_commit(connection):
    async with connection.transaction():
        await connection.advisory_lock(KEY)
    assert not await is_locked(connection, KEY)


async def test_lock_is_released_on_rollback(connection):
    with pytest.raises(ZeroDivisionError):
        async with connection.transaction():
            await connection.advisory_lock(KEY)
            1 / 0
    assert not await is_locked(connection, KEY)


async def test_lock_taken_in_a_savepoint_is_held_until_the_outer_transaction_ends(connection):
    async with connection.transaction():
        async with connection.transaction():
            await connection.advisory_lock(KEY)
        assert await is_locked(connection, KEY)
    assert not await is_locked(connection, KEY)


async def test_lock_timeout_ends_with_the_transaction():
    connection = make_connection(pool_size=1, max_overflow=0)
    try:
        async with connection.transaction():
            before = await connection.select_one(
                "SELECT current_setting('lock_timeout') AS value, pg_backend_pid() AS pid"
            )
        async with connection.transaction():
            await connection.lock_timeout(1234)
            during = await connection.select_one("SELECT current_setting('lock_timeout') AS value")
            await connection.advisory_lock(KEY, timeout_ms=4321)
            overridden = await connection.select_one("SELECT current_setting('lock_timeout') AS value")
        async with connection.transaction():
            after = await connection.select_one(
                "SELECT current_setting('lock_timeout') AS value, pg_backend_pid() AS pid"
            )
    finally:
        await connection.close()
        await connection.engine.dispose()

    assert during["value"] == "1234ms"
    assert overridden["value"] == "4321ms"
    assert after["value"] == before["value"]
    assert after["pid"] == before["pid"]


async def test_facade_takes_the_lock_on_the_named_connection(monkeypatch):
    from fastapi_startkit.masoniteorm.facades.DB import DB as Facade

    from .fixtures.db import DB

    monkeypatch.setattr(Facade, "_instance", DB)
    connection = DB.connection("dev")
    try:
        async with connection.transaction():
            await Facade.advisory_lock(KEY, timeout_ms=500, connection="dev")
            assert await is_locked(connection, KEY)
    finally:
        await DB.clear()
