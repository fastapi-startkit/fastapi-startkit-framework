# 067. Database cache lock refuses contention inside a transaction

Date: 2026-11-08

## Problem

`DatabaseLock.acquire()` (ADR 029) inserts a `lock:<name>` row and, on `IntegrityError`, updates the row if it has expired. On Postgres a failed statement aborts the surrounding transaction. When `acquire()` runs inside an open transaction and the lock is held, the insert fails, the transaction is aborted, and the follow-up update raises `InFailedSQLTransactionError` instead of returning `False`. Any application that takes a lock from inside `transaction()`, or whose tests wrap each test in a rolled-back transaction, gets an error on contention instead of a refusal. SQLite rolls back only the failed statement, so the existing contract tests on SQLite never showed it.

## Alternatives

- **Insert with `ON CONFLICT DO NOTHING`.** The query builder has no upsert or insert-ignore call, and adding one across the four grammars is a larger change than this fix.
- **Catch the error and roll back the caller's transaction.** This would discard the caller's work.
- **Run the insert in a savepoint.** `connection.transaction()` already starts a nested transaction (a savepoint) when one is open, and a normal transaction otherwise.

## Decision

`DatabaseLock.acquire()` runs the insert inside `self.store.connection().transaction()`. On a duplicate key only the savepoint rolls back, the `IntegrityError` still reaches the existing handler, and the expired-lock update runs in the caller's live transaction. Outside a transaction the insert gets its own short transaction, as before.

## Validation

`tests/masoniteorm/postgres/test_postgres_cache_lock.py` opens a transaction on Postgres. In it, a second owner's `acquire()` returns `False`, and an expired lock is taken over. Both tests fail with `InFailedSQLTransactionError` without the change. The cache lock contract tests still pass.
