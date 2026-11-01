# 063. `lock(value)` on the query builder, for `SKIP LOCKED` claims

Date: 2026-11-01

## Problem

A worker that claims pending rows from a shared table, such as a job queue or a per-user work list, needs concurrent workers to take different rows without waiting on each other. ADR 061 added `lock_for_update()` and `shared_lock()`, but a second worker that asks for the same rows with `FOR UPDATE` waits for the first to commit. Postgres 9.5+, MySQL 8.0.1+ and MariaDB 10.6+ solve this with `FOR UPDATE SKIP LOCKED`, and SQL Server with the `READPAST` hint. The builder could not render either, so applications wrote the claim as raw SQL.

## Alternatives

1. **A `skip_locked` flag: `lock_for_update(skip_locked=True)`.** It adds a new grammar key per option and grows with `NOWAIT`, `FOR NO KEY UPDATE` and the rest. Laravel has no such flag.
2. **`UPDATE ... WHERE id = (SELECT ... FOR UPDATE SKIP LOCKED) RETURNING ...` in one statement.** It needs `RETURNING` support in every grammar and hides the claim inside a single statement.
3. **Laravel's `lock($value = true)`.** `true` takes the update lock, `false` the shared lock, and a string is the dialect's lock clause, rendered verbatim. Laravel's database queue claims a job this way: `lock('FOR UPDATE SKIP LOCKED')->orderBy('id')->first()` in a transaction, then an update of that job by id.

## Decision

Option 3.

- `QueryBuilder.lock(value: bool | str = True)` sets `_lock` to `"update"` for `True`, `"share"` for `False`, or the string itself. `lock_for_update()` is `lock(True)` and `shared_lock()` is `lock(False)`. The last call wins. `Model.lock(value)` proxies to a new query.
- `BaseGrammar.process_locks()` renders the dialect clause for `"update"` and `"share"` and any other string verbatim, in the same slot: after `LIMIT`/`OFFSET` on Postgres and MySQL, and after the table on MSSQL (`WITH(ROWLOCK, UPDLOCK, READPAST)`). `SQLiteGrammar.process_locks()` renders nothing, as it already did for both locks. SQLite locks the whole database for a write transaction, so the same code runs in tests.
- A locked builder used as a `where_in` subquery keeps its lock, because the subquery compiles through the sub-builder's own grammar.
- A claim reads the matching rows with a lock inside `connection.transaction()`, iterates them and updates each by key, so the caller knows which rows it claimed without `RETURNING`.

ADR 061 rejected a stringly `lock(mode)` because an unknown mode silently rendered no lock. A string now renders verbatim, so a typo fails in the database instead of running unlocked.

A lock string is SQL, not a binding. It must be a literal written in the application's code, such as a module constant, and never built from request input, configuration a user can change, or any other untrusted value. `lock()` does not escape or validate it, just as `select_raw` does not, because the set of valid clauses differs by dialect and version.

The caller picks the clause for its dialect, as in Laravel's `DatabaseQueue::getLockForPopping()`. A string meant for one dialect is invalid SQL on another, except on SQLite, where every lock is a no-op.

## Validation

- `tests/masoniteorm/query/grammars/test_lock_value_grammar.py` snapshots `to_qmark()` on SQLite, MySQL, Postgres and MSSQL: `lock()` and `lock(True)` take the update lock, `lock(False)` the shared lock, a string renders verbatim after `ORDER BY` and `LIMIT` (after the table and with `TOP` on MSSQL, nothing on SQLite), a locked `where_in` subquery keeps its lock, and the last call wins.
- `tests/masoniteorm/postgres/test_postgres_skip_locked.py` runs concurrent transactions on Postgres. Three workers each read up to two pending rows with `lock("FOR UPDATE SKIP LOCKED")`, update each by id and hold their transaction. They claim 2, 2 and 1 of five rows, no row twice, and all five end up processing. A worker using a plain `lock()` waits for the holder and never gets the held row.
- `test_lock_grammar.py`, `test_sqlite_lock.py` and `test_postgres_lock.py` from ADR 061 pass unchanged.
- The full framework suite passes with coverage at or above the threshold.
