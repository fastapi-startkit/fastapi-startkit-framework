---
title: Atomic cache locks with Cache.lock()
date: 2026-10-21
---

## Problem

Applications need to make sure only one worker runs a piece of work at a time (rebuilding a report, charging an order, running a scheduled job on one of many servers). Laravel offers `Cache::lock($name, $seconds)` with `get`, `block`, `release` and `forceRelease`, backed by the cache store so every worker that shares the store sees the same lock. The cache module has no locks, and the check-then-write `put` cannot be used for one because two workers can both see the key missing.

## Alternatives

- **Lock built on `get` + `put`.** Not atomic across processes. Rejected.
- **`asyncio.Lock`.** Process-local only. Rejected.
- **One generic lock that calls a new atomic `add(key, value, seconds)` on every store.** Each store still needs its own atomic primitive, and release must compare the owner and delete atomically too, which `add` does not cover. Rejected.
- **A `Lock` base class with the shared `get`/`block`/`async with` behaviour, and one subclass per store implementing `acquire`, `release` and `force_release` with that store's atomic primitive.** Chosen, matching Laravel's `Lock` / `CacheLock` / `DatabaseLock` split.

## Decision

- `cache/lock.py` defines `LockTimeoutError` and the abstract `Lock(name, seconds=0, owner=None)`. `owner` defaults to a random token; passing a known owner restores a lock acquired elsewhere (another request or process) so it can be released there. `seconds <= 0` means the lock never expires.
  - `await lock.get()` tries once and returns `bool`; `await lock.get(callback)` runs the sync or async callback only when acquired, releases afterwards (also on error) and returns the callback result, or `False` when not acquired.
  - `await lock.block(seconds, callback=None)` retries every 250 ms (`lock.sleep`) until acquired or `seconds` passed, then raises `LockTimeoutError`; with a callback it runs and releases like `get`.
  - `async with Cache.lock("name", 10):` acquires once or raises `LockTimeoutError`, and releases on exit. Use `block` to wait.
  - `release()` deletes the lock only when this owner holds it and it has not expired, and returns `bool` (an owner's own expired lock returns `False` on every store); `force_release()` deletes it regardless of owner.
  - Locks are not re-entrant: acquiring a lock the same owner already holds fails, on every store.
- Store locks:
  - `ArrayStore`: a `locks` dict of `name -> (owner, expires_at)` on the store. Check and set run without an `await`, so they are atomic within the event loop.
  - `FileStore`: one file per lock under `<path>/locks/<sha1>`, holding JSON `[owner, expires_at]`. Each operation opens the file, takes an exclusive `fcntl.flock`, reads, decides, rewrites or truncates it, and closes it, so acquire and owner-checked release are atomic across processes on one host. Files are truncated, never unlinked, because unlinking a file another process has open would let both lock different inodes. Lock files live outside the two-hex shard directories, so `flush` does not touch them. `fcntl` is imported on use, so the file cache still imports on Windows; locks on the file store are POSIX-only.
  - `DatabaseStore`: a row in the cache table with key `lock:<name>`, the pickled owner as value and the usual expiration column. Acquire inserts; on a primary-key conflict it updates the row only where `expiration <= now`, and the lock is acquired when one row changed. Release deletes where key and value match the owner and the row has not expired. Reusing the cache table needs no new migration; `flush` therefore also clears database locks. The PostgreSQL transaction caveat of ADR 029 applies to the insert conflict.
  - `RedisStore`: key `lock:<name>` (the Redis connection prefix applies) holding the raw owner. Acquire is `SET NX PX` (no `PX` when the lock never expires). Release is a Lua script that deletes the key only while it holds this owner, and force release is `DEL`. Redis expires the key itself, so releasing your own expired lock returns `False`. The key is outside the store's `<prefix>:` namespace, so `flush` keeps Redis locks. The key also never collides with a cache entry, whose corrupt-value handling would otherwise delete the lock.
- `Repository.lock(name, seconds=0, owner=None)` prefixes the name like a cache key and returns the store's lock; a store without locks raises `TypeError`. The facade reaches it through the manager; the stub adds `lock`.

## Usage

```python
from fastapi_startkit.facades import Cache

lock = Cache.lock("reports", 10)
if await lock.get():
    try:
        await build_report()
    finally:
        await lock.release()

await Cache.lock("reports", 10).get(build_report)
await Cache.lock("reports", 10).block(5, build_report)

async with Cache.lock("reports", 10):
    await build_report()

owner = lock.owner
await Cache.lock("reports", 10, owner).release()
```

## Validation

`tests/cache/test_lock.py` (unittest) runs one shared case class against the array, file, database (SQLite) and Redis (fakeredis with Lua) stores: acquire once, exactly one winner among concurrent `asyncio.gather` acquires, second owner fails, same owner fails, expired lock can be taken, `seconds=0` never expires, release only by owner, releasing an own expired lock returns `False`, force release, restore by owner, `get` with sync/async callback releases also on error, `block` waits for a release and times out with `LockTimeoutError`, `async with` acquires/releases, releases when the body raises, and raises when held, the repository prefixes lock names, and a store without locks raises `TypeError`. The file store also checks that `flush` keeps locks and that a corrupt lock file counts as free. The Redis store checks the prefixed key and its TTL, that the lock does not collide with a cache key, and that `flush` keeps locks.
