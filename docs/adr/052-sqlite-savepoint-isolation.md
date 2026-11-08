# 052 — SQLite savepoints start a real transaction

- Date: 2026-10-31
- Status: Accepted

## Problem

pysqlite (and aiosqlite, which wraps it) defers `BEGIN` until the first DML statement. SQLAlchemy's `connection.begin()` therefore sends nothing to SQLite. When the first statement inside that outer transaction is a nested transaction, SQLite receives a bare `SAVEPOINT`, which starts a new transaction. Its `RELEASE SAVEPOINT` then commits for real, so a later outer rollback leaves the rows behind.

This breaks `DatabaseTransaction`/`RefreshDatabase` test isolation on SQLite whenever the first database work in a test is application code that opens its own transaction (`async with connection.transaction()`): the application transaction becomes a savepoint, and its rows survive the test rollback. The same happens when the outer transaction has only read so far (`SELECT` does not trigger pysqlite's implicit `BEGIN`).

## Alternatives

1. **SQLAlchemy's documented recipe.** Set `isolation_level = None` on the driver connection in a `connect` listener and emit `BEGIN` in a `begin` listener, so every SQLAlchemy transaction is a real SQLite transaction. Rejected: `SQLiteConfig.engine_options()` uses `StaticPool`, so every coroutine shares a single sqlite3 connection. Concurrent `engine.begin()` blocks (for example parallel cache lock acquires, `tests/cache/test_lock.py::test_concurrent_acquires_have_exactly_one_winner`) now send overlapping `BEGIN`s and fail with `cannot start a transaction within a transaction`. Guarding the `BEGIN` with `in_transaction` does not help: the check runs on the event loop and the `BEGIN` runs later on aiosqlite's worker thread, so two coroutines both pass the check.
2. **Change the SQLite pool.** Out of scope: `StaticPool` is what makes `:memory:` databases usable, and changing it alters connection semantics for every SQLite app.
3. **Begin the real transaction only when a savepoint is opened.** Keep pysqlite's implicit `BEGIN` for ordinary transactions and, in a `savepoint` listener, emit `BEGIN` first when the driver connection is not already in a transaction. Chosen.

## Decision

`SQliteConnection.__init__` registers `on_savepoint` on `engine.sync_engine` for the `savepoint` event, which SQLAlchemy fires just before it emits `SAVEPOINT`. If `connection.connection.driver_connection.in_transaction` is false, the listener runs `BEGIN`, so the savepoint is nested inside a real transaction and `RELEASE SAVEPOINT` no longer commits. The check runs on the event loop and `BEGIN` runs later on aiosqlite's worker thread, so on a shared `StaticPool` connection another coroutine can start the transaction in between. The listener therefore catches `OperationalError` from `BEGIN` and re-raises it only when the driver connection is still not in a transaction. Losing that race means a transaction is already open, which is all the savepoint needs. The listener is a static method, and SQLAlchemy registers the same function only once per engine.

Ordinary transactions keep their current behaviour, including concurrent use of the shared `StaticPool` connection.

## Consequences

- Nested transactions on SQLite now roll back with their outer transaction, whatever statement comes first.
- DDL run before any DML in an outer transaction is still autocommitted by SQLite's deferred-begin behaviour. Only the savepoint case is fixed.
- Concurrent nested transactions on one shared `StaticPool` connection behave as on `main`: no errors, all rows written. On `main` they were not isolated from each other (each savepoint committed for real) but they did not raise. A lost `BEGIN` race is tolerated so this stays true.
- Sharing one connection still gives no isolation between coroutines. When a plain transaction and a nested transaction overlap on it, the plain transaction's `COMMIT` also ends the other coroutine's savepoint, which then fails with `no such savepoint`. This happens on `main` too and is not changed here.

## Validation

`tests/masoniteorm/sqlite/test_savepoint_isolation.py` covers:

- an outer transaction that has only run a `SELECT` before a savepoint, rolled back → 0 rows;
- a savepoint as the first statement of an outer transaction, rolled back → 0 rows;
- `DatabaseTransaction` around an application `connection.transaction()` → 0 rows after the harness stops;
- a rolled-back savepoint inside a committed outer transaction keeps the outer row and drops the inner one.
- five concurrent nested transactions on a `StaticPool` `:memory:` engine → no errors and 5 rows (fails without the race tolerance);
- a nested and a plain transaction racing on that engine, in both orders, never fail with `cannot start a transaction within a transaction`;
- a `BEGIN` failure while the driver connection is still not in a transaction is re-raised.

The full suite (`uv run pytest --ignore=tests/masoniteorm/postgres --cov`) passes, including the concurrent cache lock test that rejected alternative 1.
