# 058 — Transaction-scoped advisory locks (`DB.advisory_lock`) and `LockTimeoutError`

Date: 2026-10-31

## Problem

Applications serialise critical sections across processes, such as OAuth refresh-token rotation, with
PostgreSQL advisory locks. Today they write raw SQL inside `transaction()`:

```python
await connection.statement("SET LOCAL lock_timeout = '3000ms'")
await connection.statement("SELECT pg_advisory_xact_lock(42)")
```

and they catch the asyncpg `LockNotAvailableError` (SQLSTATE `55P03`) wrapped in SQLAlchemy's
`DBAPIError` to turn a lock-wait timeout into a client error. Every app repeats this. It leaks driver
exceptions into application code and invites string interpolation into `SET`, which does not accept
bind parameters.

## Alternatives

1. **Session-scoped locks** (`pg_advisory_lock` / `pg_advisory_unlock`). Rejected: the lock outlives
   a rolled-back transaction if the unlock is missed, and pooled connections can return to the pool
   still holding it. The transaction-scoped variant is released by PostgreSQL at commit or rollback.
2. **String keys hashed in SQL with `hashtext(:key)`.** Rejected: `hashtext` is an internal,
   undocumented function. It returns a 32-bit `int4`, so it collides far more often than a 64-bit key,
   and its output changed in the past (PostgreSQL 8.4). A key derived from it cannot be computed or
   tested outside the database either.
3. **String keys hashed in Python with `hash()`.** Rejected: randomised per process (`PYTHONHASHSEED`).
4. **String keys hashed in Python with `blake2b`, 8-byte digest, read as a signed big-endian integer.**
   Chosen. It is stable across processes, machines, Python versions and PostgreSQL versions. It uses
   the full `bigint` key space, and it can be unit-tested without a database.
5. **Interpolating the timeout into `SET LOCAL lock_timeout = ...`.** Rejected: user input in SQL.
   `set_config('lock_timeout', :value, true)` takes a bound value and has the same transaction-local
   scope (`is_local = true`).

## Decision

- `Connection.advisory_lock(key, timeout_ms=None)` and `Connection.lock_timeout(timeout_ms)` exist on
  every connection. The base `Connection` raises `NotImplementedError` naming the driver.
  `PostgresConnection` implements them.
- `DB.advisory_lock(key, timeout_ms=None, connection=None)` and `DB.lock_timeout(timeout_ms, connection=None)`
  forward to the named (or default) connection.
- Both must run inside an open transaction on that connection. Otherwise they raise `RuntimeError`,
  because outside a transaction the lock would be released at once (each statement autocommits) and
  `set_config(..., true)` would have no effect.
- Key: an `int` is used as-is and must fit a signed 64-bit `bigint`. A `str` is hashed as in
  alternative 4. `bool` and other types raise `TypeError`, and an out-of-range `int` raises `ValueError`.
- Timeout: an `int` in `0..2147483647` (PostgreSQL's `lock_timeout` maximum, in milliseconds). `0`
  disables the timeout, as in PostgreSQL. It is set with `SELECT set_config('lock_timeout', :ms, true)`
  and lasts until the transaction ends. Later lock waits in the same transaction also use it, as with
  the `SET LOCAL` this replaces.
- The lock is taken with `SELECT pg_advisory_xact_lock(:key)` and released by PostgreSQL at commit or
  rollback. Taking it inside a nested transaction (savepoint) still holds it until the outer
  transaction ends.
- A `DBAPIError` with SQLSTATE `55P03` raised while waiting is re-raised as
  `fastapi_startkit.masoniteorm.LockTimeoutError(key, timeout_ms)` chained `from` the driver error.
  Other errors propagate unchanged. PostgreSQL aborts the transaction on this error, so the caller's
  `transaction()` block rolls back when the exception leaves it.

## Implementation

- `masoniteorm/connections/advisory_lock.py`: `advisory_lock_key(key)` and `lock_timeout_value(ms)`
  (validation and hashing).
- `masoniteorm/exceptions.py`: `LockTimeoutError`, exported from `fastapi_startkit.masoniteorm`.
- `Connection`: `NotImplementedError` defaults. `PostgresConnection`: transaction check, `set_config`,
  `pg_advisory_xact_lock`, `55P03` mapping.
- `DB` facade: `advisory_lock` and `lock_timeout`.
- The transaction modules (`manages_transactions.py`, `transactions.py`) are not changed.

## Validation

- Unit tests: key hashing (stable known values, signed range, `int` pass-through, bounds, type errors),
  timeout validation, the no-transaction error, `NotImplementedError` on SQLite, `55P03` mapping and
  pass-through of other driver errors, and facade forwarding.
- Live PostgreSQL tests (`tests/masoniteorm/postgres`): the lock is visible in `pg_locks` while held,
  a second transaction blocks, a timeout raises `LockTimeoutError`, the lock is released on commit
  and on rollback, and `lock_timeout` returns to its previous value after the transaction.
- `uv run pytest --ignore=tests/masoniteorm/postgres --cov` stays at or above 80%.
