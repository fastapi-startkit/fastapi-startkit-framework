# 001: ORM after-commit callbacks

Date: 2026-10-01
Status: Accepted

## Problem

Applications need to send notifications or perform other follow-up work only after database changes have committed. Model `created`, `updated`, and `saved` observers run during the model operation and can therefore run before a transaction commits. The ORM currently exposes both explicit transactions and transaction context managers but has no commit callback API.

Repository conventions are moving from the previous guide into `AGENTS.md`. Server configuration belongs in `.mcp.json`, so repository guidance should describe contribution practices without embedding MCP endpoints or tool instructions. ADRs need a valid, concise index.

## Alternatives

- Run model observers after commit: this would change existing observer timing and would not cover raw queries.
- Attach SQLAlchemy events: engine commit events run before the commit completes and cannot directly await asynchronous callbacks.
- Track callbacks in the ORM transaction lifecycle: this covers the public transaction APIs and can await callbacks after a successful commit. This is the chosen design.

## Decision and API

Expose `await connection.after_commit(callback)` and `await DB.after_commit(callback, name=None)`. Callbacks take no arguments and may return an awaitable. Callers can capture arguments in a closure or `functools.partial`.

Registration queues the callable when a transaction is active. Without an active transaction, registration invokes and awaits the callback immediately. Reject non-callables at registration.

Run callbacks sequentially in registration order after a successful outermost commit. A nested commit merges its callbacks into its parent rather than running them. A nested rollback discards only callbacks registered in that scope; an outer rollback discards all callbacks. Close, reconnect, cancellation, and failed commits must not retain callbacks for later transactions.

Release the root connection before invoking callbacks so they can query committed data or open a fresh transaction, including with a pool of one connection. Callback errors propagate to the caller; the commit remains durable, remaining callbacks do not run, and the queue is already cleared. This API is an in-process hook, not a durable delivery guarantee; applications needing reliable external delivery should use an outbox.

## Usage

```python
from fastapi_startkit.masoniteorm.facades import DB

async with DB.connection().transaction():
    await DB.table("users").where("id", user_id).update({"verified": True})
    await DB.after_commit(lambda: send_confirmation(user_id))
```

The confirmation callback runs after the transaction exits successfully. Rollback skips it.

## Implementation

Store callback frames in the ORM connection, keyed by the active SQLAlchemy connection wrapper and transaction, with an explicit parent link captured when entering each transaction or savepoint. This follows existing ContextVar connection propagation: inherited tasks share the current transaction, while independent tasks and named connections use separate physical connections and callback queues. Avoid SQLAlchemy `connection.info` for this state because accessing it during connection invalidation can require DBAPI reconnection and prevent cleanup. Remove each root batch and closed connection from the registry.

Wire frame creation, commit merging, and rollback removal into `Connection.begin_transaction`, `Connection.commit_transaction`, `Connection.rollback`, and `Transaction` enter, exit, commit, and rollback. Detach root callback batches before execution and clear connection state on close. Direct transaction manipulation through a raw SQLAlchemy connection is outside this API.

Carry the supplied repository guidance into `AGENTS.md`, correct its wording and stale test paths, replace the prior guide, and format `docs/adr/AGENTS.md` as an index. Preserve unrelated local changes such as the dependency lockfile.

## Validation

Use real SQLite integration tests to cover synchronous and asynchronous callbacks, committed data visibility, manual and context transactions, explicit transaction-object methods, nested commit and rollback, multiple nested levels, mixed transaction APIs, errors, cancellation, close and reconnect, task isolation, invalidated connections, named facade connections, registration order, and callbacks that start new transactions. Run existing SQLite transaction tests, Ruff checks on modified Python files, and the framework type checker.
