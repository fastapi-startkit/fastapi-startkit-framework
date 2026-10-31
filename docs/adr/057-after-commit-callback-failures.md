# 057 — After-commit callback failures are logged, not raised

- Date: 2026-10-31
- Status: Accepted

## Problem

`DB.after_commit` / `Connection.after_commit` callbacks (ADR 006, ADR 018) run after the durable commit through `TransactionRecord.execute_callbacks`. When one callback raises, the error propagates out of `commit_transaction` (and out of `async with connection.transaction()`), the remaining callbacks never run, and the caller sees a failure for a write that is already committed. Applications such as Salut AI wrap every callback themselves to log the error, keep going and avoid reporting the committed write as failed. The framework should own that policy.

## Alternatives

1. **Keep propagating.** Rejected: a committed write looks failed, later callbacks are silently skipped, and every application repeats the same wrapper.
2. **Run every callback, then raise an aggregated `ExceptionGroup` behind an opt-in flag.** Rejected: whatever the flag, the error still surfaces at the commit site and reports a durable write as failed, and callers need `except*` around every transaction to tell callback failures from commit failures. Applications that want to be told about failures need a report, not an exception.
3. **Log and continue, with an optional reporter hook.** Every callback runs; a failing one is logged with its traceback and handed to an application-supplied reporter (for example Sentry). Chosen.

## Decision

- Each queued callback (sync, async or returning an awaitable) runs in order after the commit. An `Exception` raised by one is logged with `logger.exception` on the `fastapi_startkit.masoniteorm` logger, which the framework `LoggingHandler` on the root logger forwards to the configured log channel, and the next callback runs. The commit returns normally.
- `DB.report_after_commit_failures_using(handler)` (also importable from `fastapi_startkit.masoniteorm.connections.transactions`) registers one process-wide reporter `handler(error, callback)`, sync or async, called after the log entry for every failure. `None` removes it. A reporter that raises is itself logged and does not stop the remaining callbacks.
- Only `Exception` is handled. `BaseException`s such as `asyncio.CancelledError` and `KeyboardInterrupt` still propagate and stop the remaining callbacks, because swallowing cancellation would break task cancellation.
- Callbacks registered outside a transaction still run immediately; the same failure policy applies, since that write is already autocommitted.
- Unchanged: callbacks queued in a savepoint merge into the parent on release and run after the outermost commit, are discarded on rollback, and the connection is returned to the pool before any callback runs (`commit_transaction` releases it first), so a failing callback cannot leak a pooled connection.

## Consequences

- A callback failure no longer surfaces at the commit site. Code that relied on catching it there must use the reporter.
- The documentation's Database Transactions section, which says errors propagate after a durable commit, needs updating in the docs repository.

## Validation

`tests/masoniteorm/connections/test_after_commit.py`:

- with the first of three callbacks raising, the second and third (one sync, one async) still run, for manual, context-manager and `Transaction.commit()` commits;
- the failure is logged on `fastapi_startkit.masoniteorm` at `ERROR` with its traceback;
- the row stays committed and a `pool_size=1, max_overflow=0` engine has no checked-out connection afterwards, and a following transaction works;
- a failing callback queued in a released savepoint runs, and fails without blocking the others, after the outer commit;
- an immediate (no transaction) failing callback is logged and does not raise;
- a sync and an async reporter receive the error and the callback; a raising reporter is logged and the remaining callbacks run; `None` removes the reporter;
- `CancelledError` from a callback still propagates.

`uv run pytest --ignore=tests/masoniteorm/postgres --cov` passes with coverage at or above 80%.
