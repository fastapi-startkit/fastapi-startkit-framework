---
title: Cache module with remember, memo, locks and tags
date: 2026-10-21
---

## Problem

The framework ships a `Cache` facade bound to the `cache` key, but nothing registers that key, so every call fails. Applications need a Laravel-style cache: `get`, `put`, `forget`, `flush`, multiple named stores, and `remember`, which computes a value only on a miss. FastAPI code is async, so the API must be awaitable and must accept both sync and async factories.

On top of the basic cache, applications need the rest of Laravel's cache features:

- **Memoization.** A request or job often reads the same key several times (settings, the current tenant). With the file, database or Redis store each read is I/O and unpickling. Laravel's `Cache::memo()` remembers values read from the store for the rest of the request. The framework has no request object to hang that state on, so state must follow the running task without leaking between concurrent requests.
- **Atomic locks.** Only one worker may run some work at a time (rebuilding a report, charging an order, running a scheduled job on one of many servers). Laravel offers `Cache::lock($name, $seconds)` with `get`, `block`, `release` and `forceRelease`, backed by the cache store so every worker that shares the store sees the same lock. A check-then-write `put` cannot be used, because two workers can both see the key missing.
- **Tags.** Applications cache many related entries (every page of a user's posts, every report for a team) and must invalidate the group without knowing every key. Laravel's `Cache::tags([...])` reads entries only with the same tags, and `Cache::tags([...])->flush()` invalidates every entry that carries any of those tags.

## Alternatives

Core API:

- **`with Cache.remember(key, ttl):` block.** A context manager cannot skip its body or return a value, so it cannot express "compute only on a miss". Rejected.
- **Decorator-only API.** Fits functions, not inline expressions such as `await Cache.remember("users", 60, query)`. Rejected as the only form.
- **Third-party library (aiocache, cashews).** Adds a dependency and its own config model, and does not match the provider/config/facade pattern used by Redis and Storage. Rejected.
- **Sync API with `asyncio.to_thread` wrappers for callers.** Breaks the database store, which is async-only. Rejected.
- **Callable core API plus a decorator built on it, behind a store protocol.** Chosen.

Memoization:

- **Process-wide dict.** Shared by every request, so one request sees values another request cached and never sees later writes from other workers. Rejected.
- **Middleware that opens a scope per request.** Needs FastAPI wiring in the cache provider, does nothing for queue jobs or console commands, and a memo used outside the middleware would fall back to something else anyway. Rejected.
- **`ContextVar` holding a dict, created on first use.** A dict created in a parent context (lifespan, a test fixture, a worker loop) is inherited by every child task, so all requests would share it. Rejected on its own.
- **`ContextVar` holding a dict tagged with the task that created it.** A task that finds a dict owned by another task starts a fresh one. Chosen.

Locks:

- **Lock built on `get` + `put`.** Not atomic across processes. Rejected.
- **`asyncio.Lock`.** Process-local only. Rejected.
- **One generic lock over a new atomic `add(key, value, seconds)` on every store.** Each store still needs its own atomic primitive, and release must compare the owner and delete atomically too, which `add` does not cover. Rejected.
- **A `Lock` base class with the shared `get`/`block`/`async with` behaviour, and one subclass per store implementing `acquire`, `release` and `force_release` with that store's atomic primitive.** Chosen, matching Laravel's `Lock` / `CacheLock` / `DatabaseLock` split.

Tags:

- **Store a key list per tag and delete each key on flush.** Every store needs a list or set type and an atomic append, and the file and database stores have neither. Lists also grow without bound for keys that expire. Rejected.
- **Scan keys by pattern on flush.** Not possible for the file store (keys are hashed) and slow for the database. Rejected.
- **Namespaced keys (Laravel's original tagged cache).** Each tag has a random version id stored in the cache, a tagged entry's key is prefixed with a hash of its tags' ids, and flushing a tag writes a new id so old entries can no longer be addressed. Works on every store with plain `get`/`put`. Chosen.

## Decision

### Configuration, stores and repository

- Package `fastapi_startkit.cache` with `CacheConfig` in `cache/config/__init__.py` (`default`, `prefix`, `stores`) and one config dataclass per driver: `ArrayStoreConfig`, `FileStoreConfig(path)`, `DatabaseStoreConfig(connection, table)` and `RedisStoreConfig(connection)`. Env names: `CACHE_CONNECTION` (default `database`), `CACHE_PREFIX` (default `cache`), `CACHE_FILE_PATH`, `DB_CACHE_CONNECTION` (default: the default database connection) and `DB_CACHE_TABLE` (default `caches`). The provider reads it with `resolve_config`, so a plain dataclass of the same shape works (ADR 027).
- Store contract (async): `get(key)` returns a `MISSING` sentinel on a miss so that a cached `None` is a hit; `put(key, value, seconds | None)`, `forget(key)` and `flush()` return `bool`.
- `ArrayStore`: in-process dict of `(expires_at, value)`, values kept as-is.
- `FileStore`: one pickled `(expires_at, value)` file per key under `<sha1[:2]>/<sha1[2:4]>/<sha1>` inside the configured path. Writes are atomic through a temp file and `os.replace` (a failed write removes the temp file and keeps the previous value), and file I/O runs in `asyncio.to_thread`. The provider resolves a relative path against the application base path. Unreadable or corrupt files, including values whose class was renamed or removed, are a miss and deleted. `flush` removes only the two-hex-character shard directories, so a misconfigured path such as `storage` never loses unrelated files.
- `DatabaseStore`: masoniteorm table with `key` string primary key, `value` text holding base64 pickle and nullable big integer `expiration` (epoch seconds, rounded up; a 32-bit column would overflow in 2038). The connection is resolved from the `db` binding on each call, so provider order does not matter. `put` updates first and inserts when no row matched, retrying the update when a concurrent insert wins, because the ORM has no portable upsert. Inside a caller's open PostgreSQL transaction the failed insert aborts that transaction, so the retry cannot recover there and the `IntegrityError` propagates; MySQL and SQLite keep the transaction usable. Corrupt or expired rows, including values whose class was renamed or removed, are a miss and deleted. Queries go through the query builder so the reserved word `key` is quoted per grammar. The module imports SQLAlchemy and is loaded lazily by the provider, so the cache works without the `database` extra. The provider publishes the `create_caches_table` migration to `databases/migrations/`; the migration reads the table name from `cache.stores.database.table` (`DB_CACHE_TABLE`), falling back to `caches`.
- `RedisStore` (driver `redis`, `RedisStoreConfig(connection="cache")`) reuses the existing Redis support instead of creating its own client. It resolves the named connection from the `redis` binding (`RedisManager`, registered by `RedisProvider`) on each call; without `RedisProvider`, resolving the store still succeeds and the first operation raises a `RuntimeError` naming it. It therefore gets the `redis` extra, the `REDIS_*` connection settings, the lazy `redis.asyncio` import and the connection-level `REDIS_PREFIX` for free. `connection` selects any configured Redis connection (`cache` uses `REDIS_CACHE_DB`, `default` the main database). Values are base64 pickle like the database store, so they survive the manager's `decode_responses=True`; corrupt values are a miss and deleted. TTL is `SET ... PX` in milliseconds, rounded up to at least 1 ms, and Redis expires keys itself. `flush` never calls `FLUSHDB`/`FLUSHALL`: it `SCAN`s for `<connection prefix><cache prefix>:*` (glob characters escaped), strips the connection prefix that the connection re-applies, and `UNLINK`s in batches of 500. The provider passes the cache `prefix` to the store, and an empty prefix is rejected because flush could not be scoped.
- Pickle allows arbitrary Python values, and unpickling runs code, so the file directory, the cache table and the Redis database are trusted storage: never point them at a location that untrusted parties can write.
- `Repository` wraps one store and adds the key prefix (`<prefix>:<key>` when a prefix is set) and the public API: `get(key, default=None)` where a callable default is called (and awaited when it returns an awaitable) only on a miss, `put(key, value, ttl=None)`, `has`, `forget`, `flush`, `remember(key, ttl, factory)`, `lock` and `tags`.
- TTL is seconds or a `timedelta`; `None` stores forever; zero or less forgets the key and returns `False`. Expiry is an absolute epoch timestamp checked lazily on read, and expired entries are deleted when read.
- `remember(key, ttl)` without a factory returns a decorator. The decorated function becomes async; the cache key is `key` alone for a call without arguments, otherwise `key:` plus a SHA-256 prefix of the pickled `(args, sorted kwargs)` (falling back to `repr` for unpicklable arguments). Arguments that cannot be pickled and whose `repr` is not stable (for example one that includes a memory address that changes per call) produce a new key every call and always miss. `set` and `frozenset` arguments pickle in iteration order, which can differ for equal sets built in a different order or in another process (string hashing is randomized per process), so pass a sorted tuple instead. A `None` key uses `module.qualname` of the function; the factory form requires a key and raises `ValueError` without one. The decorator and the factory form share entries, so `put("users", ...)` is seen by a decorated function keyed `users` that takes no arguments. Instance methods include `self` in the hashed arguments, so each instance caches separately.
- `CacheManager` resolves a `Repository` per store name, caches it, delegates unknown attributes to the default store, and supports `extend(driver, factory)` for custom stores. `CacheProvider` merges config under `cache`, binds the manager as `cache` and publishes `config/cache.py`. The `Cache` facade defines `remember` on the facade class so decorating at import time does not resolve the container; resolution happens per call. A `.pyi` stub types the facade, including `memo`, `lock` and `tags`.

### Memoization: `Cache.memo()`

- `cache/memo_store.py` adds `MemoStore(store)`, a store that wraps another store. `get` returns the memoized value for the key when present, otherwise reads the inner store and memoizes the result, including `MISSING`, so repeated misses are free too. `put` and `forget` write through and drop the memoized key, so the next `get` re-reads the store. `flush` flushes the inner store and clears this store's memo.
- Memo state lives in one module `ContextVar` holding `(weakref to owning task, {MemoStore: {key: value}})`. On access, when there is no state or the owner is not `asyncio.current_task()`, a new dict is created and set for the current context. Each request, job or `asyncio` task therefore starts empty, and a dict is never shared with a sibling task. Child tasks (`asyncio.gather`, `create_task`) start their own memo and still read through to the same store.
- Memoized values ignore TTL for the rest of the task: a value that expires in the store mid-request stays visible to that request, matching Laravel. Values are kept as the same object, so mutating a memoized value mutates what later reads in the task see.
- `CacheManager.memo(name=None)` returns a `Repository` over `MemoStore(store(name).store)` with the same prefix, cached per store name, so `Cache.memo()` uses the default store and `Cache.memo("file")` a named one. Every repository method works through it.

### Atomic locks: `Cache.lock()`

- `cache/lock.py` defines `LockTimeoutError` and the abstract `Lock(name, seconds=0, owner=None)`. `owner` defaults to a random token; passing a known owner restores a lock acquired elsewhere (another request or process) so it can be released there. `seconds <= 0` means the lock never expires.
  - `await lock.get()` tries once and returns `bool`; `await lock.get(callback)` runs the sync or async callback only when acquired, releases afterwards (also on error) and returns the callback result, or `False` when not acquired.
  - `await lock.block(seconds, callback=None)` retries every 250 ms (`lock.sleep`) until acquired or `seconds` passed, then raises `LockTimeoutError`; with a callback it runs and releases like `get`.
  - `async with Cache.lock("name", 10):` acquires once or raises `LockTimeoutError`, and releases on exit. Use `block` to wait.
  - `release()` deletes the lock only when this owner holds it and it has not expired, and returns `bool`; releasing an owner's own expired lock returns `False` on every store. `force_release()` deletes it regardless of owner.
  - Locks are not re-entrant: acquiring a lock the same owner already holds fails, on every store.
- Store locks:
  - `ArrayStore`: a `locks` dict of `name -> (owner, expires_at)` on the store. Check and set run without an `await`, so they are atomic within the event loop.
  - `FileStore`: one file per lock under `<path>/locks/<sha1>`, holding JSON `[owner, expires_at]`. Each operation opens the file, takes an exclusive `fcntl.flock`, reads, decides, rewrites or truncates it, and closes it, so acquire and owner-checked release are atomic across processes on one host. Files are truncated, never unlinked, because unlinking a file another process has open would let both lock different inodes. Lock files live outside the shard directories, so `flush` keeps them. `fcntl` is imported on use, so the file cache still imports on Windows; file store locks are POSIX-only.
  - `DatabaseStore`: a row in the cache table with key `lock:<name>`, the pickled owner as value and the usual expiration column. Acquire inserts; on a primary-key conflict it updates the row only where `expiration <= now`, and the lock is acquired when one row changed. Release deletes where key and value match the owner and the row has not expired. Reusing the cache table needs no new migration; `flush` therefore also clears database locks. The PostgreSQL transaction caveat of `put` applies to the insert conflict.
  - `RedisStore`: key `lock:<name>` (the Redis connection prefix applies) holding the raw owner. Acquire is `SET NX PX` (no `PX` when the lock never expires). Release is a Lua script that deletes the key only while it holds this owner, and force release is `DEL`. Redis expires the key itself, so releasing an own expired lock returns `False`. The key is outside the store's `<prefix>:` namespace, so `flush` keeps Redis locks, and it never collides with a cache entry, whose corrupt-value handling would otherwise delete the lock.
- `Repository.lock(name, seconds=0, owner=None)` prefixes the name like a cache key and returns the store's lock; a store without locks (memo and tagged repositories) raises `TypeError`.

### Tags: `Cache.tags()`

- `cache/tagged_store.py` adds `TagSet(store, names, key)` and `TaggedStore(store, tags)`.
  - `TagSet` keeps the names deduplicated and sorted, so `tags(["a", "b"])` and `tags(["b", "a"])` address the same entries (Laravel is order-sensitive; sorting removes that trap). The id of tag `name` lives in the wrapped store under the repository key `tag:<name>:key` (`<prefix>:tag:<name>:key` with a prefix), stored forever, and is created as a random hex token on first use. `namespace()` returns the SHA-1 of the ids joined with `|`; `reset()` writes a new id for every tag.
  - `TaggedStore` implements the store contract over the wrapped store. `get`, `put` and `forget` use the key `<prefix>:<namespace>:<key>` (`<namespace>:<key>` without a prefix). The prefix comes first, as in Laravel, so a store that flushes by prefix, such as the Redis store's `SCAN <prefix>:*`, still reaches tagged entries. `flush` resets the tags instead of flushing the store.
  - Tag ids share the user key space: `tag:<name>:key` is an ordinary cache key, so `Cache.put("tag:people:key", ...)` or `Cache.forget(...)` on it changes or resets that tag. Avoid user keys of that form.
- `Repository.tags(names)` accepts a string or a sequence of strings and returns an unprefixed `Repository` over `TaggedStore`, which applies the prefix itself, so every repository method works tagged. It wraps whatever store the repository has, so `Cache.memo().tags(...)` and `Cache.store("file").tags(...)` work too. An empty tag list raises `ValueError`.
- Flushed entries are not deleted; they stay in the store until they expire or the store is flushed, so use a TTL on tagged entries in long-lived stores. If two workers create a tag's first id at the same time, the last write wins, and entries the other worker wrote under its id become misses, which only costs a recompute. Reading a tagged entry costs one extra store read per tag.

## Usage

```python
from fastapi_startkit.facades import Cache

value = await Cache.get("key")
value = await Cache.get("key", "default")
value = await Cache.get("key", lambda: compute_default())

await Cache.put("key", "value", 600)
await Cache.put("key", "value", timedelta(minutes=10))
await Cache.forever("key", "value")
await Cache.forget("key")
await Cache.flush()

value = await Cache.store("redis").get("key")

users = await Cache.remember("users", 600, lambda: DB.table("users").get())


@Cache.remember("users", 600)
async def users_by_role(role: str):
    return await DB.table("users").where("role", role).get()


settings = await Cache.memo().get("settings")
tenant = await Cache.memo("redis").remember("tenant", 600, load_tenant)

await Cache.lock("reports", 10).get(build_report)
await Cache.lock("reports", 10).block(5, build_report)
async with Cache.lock("reports", 10):
    await build_report()

await Cache.tags(["people", "artists"]).put("john", john, 600)
john = await Cache.tags(["people", "artists"]).get("john")
await Cache.tags("people").flush()
```

The default `database` store needs the `caches` table: run `artisan provider:publish` to copy the migration into `databases/migrations/`, then `artisan db:migrate`. Set `CACHE_CONNECTION=file` to skip the table, or `CACHE_CONNECTION=redis` (with `RedisProvider` registered) to use Redis.

A plain dataclass with the same shape configures it:

```python
@dataclass
class CacheConfig:
    default: str = env("CACHE_CONNECTION", "database")
    prefix: str = env("CACHE_PREFIX", "cache")
    stores: dict = field(
        default_factory=lambda: {
            "array": ArrayStoreConfig(),
            "file": FileStoreConfig(path="storage/framework/cache/data"),
            "database": DatabaseStoreConfig(table="caches"),
            "redis": RedisStoreConfig(connection="cache"),
        }
    )
```

## Delivery

Shipped as small PRs into the `feature/caches` integration branch: config; store contract, `ArrayStore`, `Repository` and `CacheManager`; the `remember` decorator; provider, facade and stub; `FileStore`; `DatabaseStore` and migration; `RedisStore`; `Cache.memo()`; `Cache.lock()` for array, file and database; the Redis lock; `Cache.tags()`. The memo, lock and tags work, first recorded as ADRs 030, 031 and 034, is folded into this record.

## Validation

Unittest suites under `fastapi_startkit/tests/cache/`:

- Config defaults and env overrides. Per store: miss/hit, cached `None`, expiry, forever, non-positive TTL, forget, flush. `get` with sync and async callable defaults; `remember` runs the factory once and awaits async factories; decorator keys differ per argument set and the function runs once per key. Provider binding, facade access after boot and the database store as default.
- Database store: upsert under a concurrent insert, corrupt rows, values of removed classes, the big integer expiration, and the migration up/down and configured table name on SQLite. Redis store: round trip, millisecond TTL, connection prefix and selectable connection, flush deleting only prefixed keys in batches with glob characters escaped and without `FLUSHDB`, using `fakeredis` through `RedisManager.extend`.
- `test_memo_store.py`: a repeated `get` reads the inner store once; a miss is memoized; `put`/`forget` invalidate and write through; `flush` clears memo and store; separate tasks do not share memo state, including when state exists in the parent context; two stores keep separate memos; the manager returns one memo repository per store with the configured prefix.
- `test_lock.py`: one shared case class against the array, file, database (SQLite) and Redis (fakeredis with Lua) stores: acquire once, exactly one winner among concurrent `asyncio.gather` acquires, same owner fails, expired lock can be taken, `seconds=0` never expires, release only by owner, releasing an own expired lock returns `False`, force release, restore by owner, `get` with sync/async callback releases also on error, `block` waits for a release and times out, `async with` acquires, releases when the body raises, and raises when held. The file store checks that `flush` keeps locks and a corrupt lock file counts as free; Redis checks the prefixed key and TTL, no collision with a cache key, and that `flush` keeps locks. The repository prefixes lock names, and a store without locks raises `TypeError`.
- `test_tagged_store.py` (array, file, in-memory SQLite and fakeredis): the tagged key is `<prefix>:<sha1>:<key>`; tagged round trips, and untagged or differently tagged reads miss; tag order and duplicates do not matter; flushing one tag invalidates every entry carrying it and keeps other and untagged entries; tag ids persist and are prefixed; forget removes only the tagged key; `remember` and the decorator work tagged; a string tag is accepted; an empty list raises; `tags().lock()` raises `TypeError`; tags work on a memo repository; a Redis store flush removes tagged entries and tag ids.
