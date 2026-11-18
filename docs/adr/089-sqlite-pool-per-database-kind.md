# 089. SQLite pool chosen by database kind

- Date: 2026-11-18
- Status: Accepted

## Problem

`SQLiteConfig.engine_options()` returned `poolclass=StaticPool` for every SQLite database. `StaticPool` hands every checkout the same DBAPI connection. `Connection._execute` runs each statement in its own `engine.begin()` block, so concurrent coroutines open, commit and roll back transactions on that one aiosqlite connection at the same time. One coroutine's commit commits another's half-finished work, and the rollback a connection gets when it returns to the pool discards another coroutine's uncommitted write.

The database cache store showed it first: under the rate limiter's concurrency tests, a `DatabaseLock.release` `DELETE` was rolled back by a neighbour, the lock row stayed, and every other request waited until `LockTimeoutError` (10 s). Since `database` is the default cache store, a SQLite app with concurrent requests would stall and then return 500. Any concurrent writes on a file-backed SQLite app are exposed to the same lost writes.

## Alternatives

- A. Use `StaticPool` only for in-memory databases, where a single shared connection is what keeps the database alive, and SQLAlchemy's default pool for file databases, so each checkout has its own connection and its own transaction.
- B. Keep `StaticPool` and make `SQliteConnection` serialize statement execution with an `asyncio.Lock`. Statements would no longer interleave, but every query in the app would queue behind one lock, and multi-statement transactions on the shared connection would still interleave.
- C. Serialize only the database cache store's statements. The cache would work, but its statements could still interleave with other queries on the shared connection, and the underlying problem would remain for everything else.

## Decision

Option A. `SQLiteConfig.engine_options()` always passes `connect_args={"check_same_thread": False}` and adds `poolclass=StaticPool` only when `in_memory()` is true. `in_memory()` parses `build_url()` with SQLAlchemy's `make_url` and treats an empty database, `:memory:`, a `file::memory:` URI and any URI with `mode=memory` as in memory. Everything else gets SQLAlchemy's default pool for aiosqlite file databases (`AsyncAdaptedQueuePool`).

`ConnectionFactory.create_engine` still uses `NullPool` and ignores `engine_options()` when the application is testing; that path already opened a fresh connection per checkout, so it is unchanged.

With several connections, SQLite's own file lock arbitrates writers. Each statement is a single-statement transaction, and pysqlite waits up to its default 5 s busy timeout for the write lock, which the concurrency tests never came close to, so no explicit `timeout` is set.

Known limitation: an in-memory SQLite database still shares one connection and remains unsafe for concurrent writes. It is meant for tests and scratch work.

## Validation

- Parametrized `engine_options()` tests: `:memory:`, an empty URL database, `file::memory:` and `mode=memory` URIs get `StaticPool`; relative, absolute and URL file databases get no `poolclass`.
- The rate limiter's `DatabaseStore` concurrency tests build their engine from a file-backed `SQLiteConfig` with the real `engine_options()`, including two limiters sharing one store, and pass; they time out with the previous `StaticPool` options.
- The masoniteorm config and sqlite suites and the cache suite pass.
