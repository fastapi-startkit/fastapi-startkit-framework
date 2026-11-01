# 061. Row locks on the query builder: `lock_for_update` and `shared_lock`

Date: 2026-10-31

## Problem

An application that checks a row and then writes depending on it needs the row locked for the rest of its transaction, for example "soft delete this record unless another record still references it". The grammars already know the lock clause of each dialect (`BaseGrammar.lock`, `process_locks()` and a `{lock}` slot in every `select_format`), inherited from Masonite ORM, but no builder method sets it and `QueryBuilder.get_grammar()` never passes `lock`. Applications fell back to `DB.select("SELECT ... FOR UPDATE")` and lost the builder, its scopes and model hydration.

The MSSQL lock hints were also too weak to be wired as they were: both locks rendered `WITH(ROWLOCK)`, which is only a granularity hint and holds no lock past the statement under the default isolation level.

## Alternatives

1. **Update first.** Run the guarded `UPDATE ... WHERE deleted_at IS NULL` before the checks, so concurrent writers on the same row serialize. On Postgres this takes a `FOR NO KEY UPDATE` row lock, which does not conflict with the `FOR KEY SHARE` lock a foreign-key insert takes on the parent row, so the check cannot wait for an in-flight child insert. It also needs no framework change, but it leaves the gap for every other caller.
2. **A generic `lock(mode: str)`.** One method, but the mode strings differ per dialect and a typo silently renders no lock, because `process_locks()` falls back to `""`.
3. **`lock_for_update()` and `shared_lock()` that set the existing grammar lock**, as in Laravel's `lockForUpdate()` and `sharedLock()`.

## Decision

Option 3.

- `QueryBuilder._lock` starts as `False`. `lock_for_update()` sets it to `"update"` and `shared_lock()` to `"share"`; the last call wins. `get_grammar()` passes `lock=self._lock`, so `_compile_select` renders the dialect clause through the existing `process_locks()`.
- Rendering, unchanged in every grammar except MSSQL:
  - Postgres: `FOR UPDATE` and `FOR SHARE`, after `LIMIT`/`OFFSET`.
  - MySQL: `FOR UPDATE` and `LOCK IN SHARE MODE` (understood by 5.7 and 8.0), at the end.
  - SQLite: nothing. SQLite locks the whole database for a write transaction, so both calls are no-ops and the same code runs in tests.
  - MSSQL: `WITH(ROWLOCK, UPDLOCK, HOLDLOCK)` and `WITH(ROWLOCK, HOLDLOCK)` after the table, matching Laravel's SQL Server grammar.
- `Model.lock_for_update()` and `Model.shared_lock()` proxy to a new query, like `Model.distinct()`.
- Only selects lock. `update()`, `delete()` and `insert()` formats have no `{lock}` slot, so a locked builder still writes normally. Nested builders from `new()` (a `where(lambda ...)` group) and the `paginate()` count builder start without a lock, so the group renders once and the count stays a plain aggregate.

A lock only lasts until the end of the current transaction, so call it inside `connection.transaction()`. Outside a transaction the statement runs in its own short transaction and the lock is released at once.

### Known limits

- **Postgres rejects locks with aggregates, `DISTINCT` and `GROUP BY`.** `count()`, `exists()`, `sum()` and the other aggregates on a locked builder render `SELECT COUNT(*) ... FOR UPDATE`, which Postgres refuses (`FOR UPDATE is not allowed with aggregate functions`). Lock the rows with `get()`/`first()`, then aggregate with a builder that has no lock. Laravel has the same limit. `paginate()` is unaffected because its count builder carries no lock.
- **MySQL 8 `FOR SHARE`, `NOWAIT` and `SKIP LOCKED`** are not offered. They can be added as their own options later.

## Validation

- `tests/masoniteorm/query/grammars/test_lock_grammar.py` snapshots `to_qmark()` and the bindings on SQLite, MySQL, Postgres and MSSQL: no lock by default, both locks, the lock after a join, where, order and limit, the last call winning, and `delete()` ignoring the lock.
- `tests/masoniteorm/sqlite/builder/test_sqlite_lock.py` runs on SQLite, where both locks are no-ops: a locked read and update inside a transaction, `shared_lock()` through the `Model` proxy, and a locked query with a grouped where, `count()` and `paginate()`.
- `tests/masoniteorm/postgres/test_postgres_lock.py` runs two transactions on Postgres: `lock_for_update()` waits for a holder of the same lock and then reads its commit, while a plain read does not wait; `lock_for_update()` waits for an in-flight insert of a child row with a foreign key to the locked row; `shared_lock()` readers share the row and block `lock_for_update()`.
- A mutation check killed each of: not passing the lock to the grammar, `shared_lock()` taking an update lock, `lock_for_update()` taking a share lock, and `lock_for_update()` doing nothing. The Postgres file alone kills all four.
- The full framework suite passes with coverage at or above the threshold.
