from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from fastapi_startkit.masoniteorm import LockTimeoutError, PostgresConfig, SQLiteConfig
from fastapi_startkit.masoniteorm.connections.advisory_lock import (
    BIGINT_MAX,
    BIGINT_MIN,
    LOCK_TIMEOUT_MAX_MS,
    advisory_lock_key,
    lock_timeout_value,
)
from fastapi_startkit.masoniteorm.connections.postgres_connection import PostgresConnection
from fastapi_startkit.masoniteorm.connections.sqlite_connection import SQliteConnection
from fastapi_startkit.masoniteorm.facades.DB import DB


class DriverError(Exception):
    def __init__(self, sqlstate: str):
        super().__init__(sqlstate)
        self.sqlstate = sqlstate


@pytest.fixture
async def postgres():
    engine = create_async_engine("postgresql+asyncpg://app:secret@localhost:1/unused")
    try:
        yield PostgresConnection(engine, PostgresConfig(driver="postgres"))
    finally:
        await engine.dispose()


@pytest.fixture
def in_transaction(postgres):
    active = MagicMock(closed=False)
    active.in_transaction.return_value = True
    token = postgres._connection_context.set(active)
    try:
        yield postgres
    finally:
        postgres._connection_context.reset(token)


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("oauth:refresh", -4881159482311254756),
        ("", -1970711489451281740),
        ("é", -3811523526868657873),
    ],
)
def test_str_keys_hash_to_stable_signed_bigints(key, expected):
    assert advisory_lock_key(key) == expected


def test_distinct_str_keys_hash_differently():
    assert advisory_lock_key("user:1") != advisory_lock_key("user:2")


@pytest.mark.parametrize("key", [0, 42, -7, BIGINT_MIN, BIGINT_MAX])
def test_int_keys_pass_through(key):
    assert advisory_lock_key(key) == key


@pytest.mark.parametrize("key", [BIGINT_MIN - 1, BIGINT_MAX + 1])
def test_int_keys_outside_bigint_are_rejected(key):
    with pytest.raises(ValueError, match="bigint range"):
        advisory_lock_key(key)


@pytest.mark.parametrize("key", [True, 1.5, None, b"key"])
def test_other_key_types_are_rejected(key):
    with pytest.raises(TypeError, match="str or int"):
        advisory_lock_key(key)


@pytest.mark.parametrize("timeout_ms", [0, 1, 3000, LOCK_TIMEOUT_MAX_MS])
def test_valid_timeouts_become_strings(timeout_ms):
    assert lock_timeout_value(timeout_ms) == str(timeout_ms)


@pytest.mark.parametrize("timeout_ms", [-1, LOCK_TIMEOUT_MAX_MS + 1])
def test_out_of_range_timeouts_are_rejected(timeout_ms):
    with pytest.raises(ValueError, match="between 0 and"):
        lock_timeout_value(timeout_ms)


@pytest.mark.parametrize("timeout_ms", [False, 1.5, "100", "1; DROP TABLE users"])
def test_non_int_timeouts_are_rejected(timeout_ms):
    with pytest.raises(TypeError, match="int number of milliseconds"):
        lock_timeout_value(timeout_ms)


async def test_advisory_lock_requires_a_transaction(postgres):
    with pytest.raises(RuntimeError, match="advisory_lock requires an open transaction"):
        await postgres.advisory_lock("key", timeout_ms=100)


async def test_lock_timeout_requires_a_transaction(postgres):
    with pytest.raises(RuntimeError, match="lock_timeout requires an open transaction"):
        await postgres.lock_timeout(100)


async def test_invalid_arguments_fail_before_any_query(in_transaction):
    with patch.object(in_transaction, "statement", AsyncMock()) as statement:
        with pytest.raises(TypeError):
            await in_transaction.advisory_lock("key", timeout_ms="100")
        with pytest.raises(ValueError):
            await in_transaction.advisory_lock(BIGINT_MAX + 1)
    statement.assert_not_awaited()


async def test_advisory_lock_binds_timeout_and_key(in_transaction):
    with patch.object(in_transaction, "statement", AsyncMock()) as statement:
        await in_transaction.advisory_lock("oauth:refresh", timeout_ms=250)
    assert [call.args for call in statement.await_args_list] == [
        ("SELECT set_config('lock_timeout', ?, true)", ["250"]),
        ("SELECT pg_advisory_xact_lock(?)", [-4881159482311254756]),
    ]


async def test_advisory_lock_without_timeout_leaves_lock_timeout_alone(in_transaction):
    with patch.object(in_transaction, "statement", AsyncMock()) as statement:
        await in_transaction.advisory_lock(7)
    statement.assert_awaited_once_with("SELECT pg_advisory_xact_lock(?)", [7])


async def test_lock_timeout_binds_value(in_transaction):
    with patch.object(in_transaction, "statement", AsyncMock()) as statement:
        await in_transaction.lock_timeout(0)
    statement.assert_awaited_once_with("SELECT set_config('lock_timeout', ?, true)", ["0"])


async def test_lock_not_available_becomes_lock_timeout_error(in_transaction):
    driver_error = DBAPIError("SELECT pg_advisory_xact_lock($1)", {}, DriverError("55P03"))
    with patch.object(in_transaction, "statement", AsyncMock(side_effect=[True, driver_error])):
        with pytest.raises(LockTimeoutError) as raised:
            await in_transaction.advisory_lock("oauth:refresh", timeout_ms=100)
    assert raised.value.key == "oauth:refresh"
    assert raised.value.timeout_ms == 100
    assert raised.value.__cause__ is driver_error
    assert "oauth:refresh" in str(raised.value)


async def test_other_driver_errors_propagate(in_transaction):
    driver_error = DBAPIError("SELECT pg_advisory_xact_lock($1)", {}, DriverError("40P01"))
    with patch.object(in_transaction, "statement", AsyncMock(side_effect=driver_error)):
        with pytest.raises(DBAPIError) as raised:
            await in_transaction.advisory_lock(1)
    assert raised.value is driver_error


async def test_sqlite_raises_not_implemented(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'locks.sqlite3'}")
    connection = SQliteConnection(engine, SQLiteConfig(driver="sqlite"))
    try:
        async with connection.transaction():
            with pytest.raises(NotImplementedError, match="only supported on Postgres, not the sqlite driver"):
                await connection.advisory_lock("key")
            with pytest.raises(NotImplementedError, match="only supported on Postgres, not the sqlite driver"):
                await connection.lock_timeout(100)
    finally:
        await connection.close()
        await engine.dispose()


async def test_facade_forwards_to_the_named_connection():
    connection = MagicMock(advisory_lock=AsyncMock(), lock_timeout=AsyncMock())
    manager = MagicMock()
    manager.connection.return_value = connection
    with patch.object(DB, "_instance", manager):
        await DB.advisory_lock("key", 100, connection="dev")
        await DB.lock_timeout(50)
    assert [call.args for call in manager.connection.call_args_list] == [("dev",), (None,)]
    connection.advisory_lock.assert_awaited_once_with("key", 100)
    connection.lock_timeout.assert_awaited_once_with(50)
