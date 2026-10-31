# 057 — After-commit callbacks all run before a failure is raised

- Date: 2026-10-31
- Status: Accepted

## Problem

`DB.after_commit` / `Connection.after_commit` callbacks (ADR 006, ADR 018) run after the durable commit through `TransactionRecord.execute_callbacks`. When one callback raises, the loop stops, so the remaining callbacks never run even though the write they depend on is committed.

## Alternatives

1. **Keep stopping at the first failure.** Rejected: one broken callback silently skips every later one.
2. **Log and continue without raising, with an optional reporter hook.** Rejected: a callback failure is an exception and the caller must see it. Swallowing it hides bugs and makes the framework choose an error policy that belongs to the application.
3. **Raise an `ExceptionGroup` of every failure.** Rejected: callers would need `except*` around every transaction, and a single failure, by far the common case, would no longer be catchable as its own type.
4. **Run every callback, then raise the first failure.** Chosen.

## Decision

- `execute_callbacks` runs every queued callback (sync, async or returning an awaitable) in order. The first `Exception` is kept, and the next callback runs. After the last callback, the first exception is re-raised unchanged, with its original traceback, from `commit_transaction`, `Transaction.commit()` or `async with connection.transaction()`.
- A second or later failure is logged with `logger.exception` on the `fastapi_startkit.masoniteorm` logger (which the framework `LoggingHandler` on the root logger forwards to the log channel), so it is not lost. The raised exception is not logged, because the caller receives it.
- Only `Exception` is collected. `BaseException`s such as `asyncio.CancelledError` and `KeyboardInterrupt` propagate at once and stop the remaining callbacks.
- The commit is durable and the connection is returned to the pool before any callback runs (`commit_transaction` releases it first), so a raising callback cannot roll back the write or leak a pooled connection.
- Unchanged: outside a transaction a callback runs immediately and its exception propagates directly; callbacks queued in a savepoint merge into the parent on release and run after the outermost commit; callbacks are discarded on rollback.

## Consequences

- An exception from the commit site may now come from a callback after a durable commit. Applications that must tell a failed commit from a failed callback should handle errors inside the callback.
- The documentation's Database Transactions section ("errors propagate after a durable commit") stays accurate and should add that the remaining callbacks still run and only the first error is raised.

## Validation

`tests/masoniteorm/connections/test_after_commit.py`:

- with the first of three callbacks raising, the second and third (one sync, one async) still run, then the first error is raised, for manual, context-manager and `Transaction.commit()` commits; nothing is logged;
- the row stays committed, a `pool_size=1, max_overflow=0` engine has no checked-out connection afterwards, and a following transaction works;
- with two failures, the first is raised and the second is logged on `fastapi_startkit.masoniteorm` at `ERROR` with its traceback;
- a failing callback queued in a released savepoint runs after the outer commit, the others still run, and its error is raised;
- an immediate (no transaction) failing callback raises;
- `CancelledError` from a callback propagates and stops the remaining callbacks.

`uv run pytest --ignore=tests/masoniteorm/postgres --cov` passes with coverage at or above 80%.
