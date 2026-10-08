# 006: ORM after-commit callbacks

Date: 2026-10-01
Status: Accepted

## Problem

Applications often need to run follow-up work, such as sending a notification, only once a database change is durable. Model observers (`created`, `updated`, `saved`) fire while the model operation is still running, so they can fire before the surrounding transaction commits. The ORM offers explicit transactions and transaction context managers, but no way to hook into a commit.

Repository conventions are also moving into `AGENTS.md`, and ADRs need a concise index.

## Alternatives

- **Fire model observers after commit.** This changes the timing of existing observers and does not cover raw queries.
- **Use SQLAlchemy engine events.** Commit events fire before the commit completes and cannot await asynchronous callbacks.
- **Track callbacks in the ORM transaction lifecycle (chosen).** This covers every public transaction API and can await callbacks once the commit has succeeded.

## Decision

Add `await connection.after_commit(callback)` and `await DB.after_commit(callback, name=None)`. A callback takes no arguments and may be synchronous or return an awaitable. Callers bind arguments with a closure or `functools.partial`. Non-callables are rejected at registration.

Behaviour:

- **Active transaction:** the callback is queued.
- **No transaction (or one the ORM did not start):** the callback runs and is awaited immediately.
- **Outermost commit:** queued callbacks run sequentially in registration order.
- **Nested commit (savepoint):** callbacks merge into the parent and do not run yet.
- **Rollback:** a nested rollback discards only that scope's callbacks; an outer rollback discards everything.
- **Close, reconnect, cancellation, failed commit:** no callbacks survive into later transactions.
- **Callback errors:** the error propagates to the caller. The commit stays durable, remaining callbacks are skipped, and the queue is already cleared.

The root connection is released before callbacks run, so they can read committed data or open a new transaction, even with a pool of one connection.

This is an in-process hook, not a durable delivery guarantee. Work that must not be lost should use an outbox.

## Usage

```python
from fastapi_startkit.masoniteorm.facades import DB

async with DB.connection().transaction():
    await DB.table("users").where("id", user_id).update({"verified": True})
    await DB.after_commit(lambda: send_confirmation(user_id))
```

`send_confirmation` runs after the transaction exits successfully and is skipped on rollback.

## Implementation

The ORM `Connection` keeps a registry of callback frames, keyed by the SQLAlchemy connection and transaction, with each frame linking to its parent. This follows the existing ContextVar connection propagation: tasks that inherit the context share the current transaction, while independent tasks and named connections use separate physical connections and queues. SQLAlchemy's `connection.info` is avoided because reading it during invalidation can force a DBAPI reconnect and block cleanup.

A transaction the ORM did not register (for example one begun directly on the raw SQLAlchemy connection) is treated as untracked: callbacks registered inside it run immediately, and an ORM savepoint inside it acts as its own root.

Frames are created, merged and discarded in `Connection.begin_transaction`, `commit_transaction` and `rollback`, and in the `Transaction` enter, exit, commit and rollback paths. Root batches are detached before they run, and closing a connection clears its frames.

Repository guidance moves into `AGENTS.md` with corrected wording and test paths, and `docs/adr/AGENTS.md` becomes the ADR index.

## Validation

Real SQLite integration tests cover:

- sync and async callbacks, registration order, and visibility of committed data
- manual, context-manager and transaction-object APIs, including mixed use
- nested and deeply nested savepoints, commit and rollback
- callback errors, failed commits, cancellation, close and reconnect, and invalidated connections
- task isolation, named facade connections, callbacks that start new transactions, and untracked transactions

Existing SQLite transaction tests, Ruff, and the framework type checker also run.
