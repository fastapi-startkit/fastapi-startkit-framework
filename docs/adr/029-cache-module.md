---
title: Cache module with callable remember and pluggable stores
date: 2026-10-21
---

## Problem

The framework ships a `Cache` facade bound to the `cache` key, but nothing registers that key, so every call fails. Applications need a Laravel-style cache: `get`, `put`, `forget`, `flush`, multiple named stores, and `remember`, which computes a value only on a miss. FastAPI code is async, so the API must be awaitable and must accept both sync and async factories.

## Alternatives

- **`with Cache.remember(key, ttl):` block.** A context manager cannot skip its body or return a value, so it cannot express "compute only on a miss". Rejected.
- **Decorator-only API.** Fits functions, not inline expressions such as `await Cache.remember("users", 60, query)`. Rejected as the only form.
- **Third-party library (aiocache, cashews).** Adds a dependency and its own config model, and does not match the provider/config/facade pattern used by Redis and Storage. Rejected.
- **Sync API with `asyncio.to_thread` wrappers for callers.** Breaks the database store, which is async-only. Rejected.
- **Callable core API plus a decorator built on it, behind a store protocol.** Chosen.

## Decision

- Package `fastapi_startkit.cache` with `CacheConfig` in `cache/config/__init__.py` (`default`, `prefix`, `stores`) and one config dataclass per driver: `ArrayStoreConfig`, `FileStoreConfig(path)` and `DatabaseStoreConfig(connection, table)`. Env names follow the original sketch: `CACHE_CONNECTION` (default `database`), `CACHE_PREFIX` (default `cache`), `CACHE_FILE_PATH`, `DB_CACHE_CONNECTION` (default: the default database connection) and `DB_CACHE_TABLE` (default `caches`). The provider reads it with `resolve_config`, so a plain dataclass of the same shape works (ADR 027).
- Store contract (async): `get(key)` returns a `MISSING` sentinel on a miss so that a cached `None` is a hit; `put(key, value, seconds | None)`, `forget(key)` and `flush()` return `bool`.
- Stores: `ArrayStore` (in-process dict of `(expires_at, value)`, values kept as-is), `FileStore` (one pickled `(expires_at, value)` file per key under `<sha1[:2]>/<sha1[2:4]>/<sha1>` inside the configured path, atomic write through a temp file and `os.replace` (a failed write removes the temp file and keeps the previous value), file I/O in `asyncio.to_thread`, a relative path resolved against the application base path by the provider, unreadable or corrupt files, including values whose class was renamed or removed, treated as a miss and deleted, and `flush` removing only the two-hex-character shard directories so a misconfigured path such as `storage` never loses unrelated files) and `DatabaseStore` (masoniteorm table with `key` string primary key, `value` text holding base64 pickle and nullable integer `expiration` rounded up to the next second; the connection is resolved from the `db` binding on each call so provider order does not matter; `put` updates first and inserts when no row matched, retrying the update when a concurrent insert wins, because the ORM has no portable upsert; corrupt or expired rows are a miss and deleted; queries go through the query builder so the reserved word `key` is quoted per grammar; the module imports SQLAlchemy and is loaded lazily by the provider, so the cache works without the `database` extra; the provider publishes the `create_caches_table` migration to `databases/migrations/`). Pickle allows arbitrary Python values, and unpickling runs code, so the file directory and the cache table are trusted storage: never point them at a location or table that untrusted parties can write.
- `Repository` wraps one store and adds the key prefix (`<prefix>:<key>` when a prefix is set) and the public API: `get(key, default=None)` where a callable default is called (and awaited when it returns an awaitable) only on a miss, `put(key, value, ttl=None)`, `has`, `forget`, `flush`, and `remember(key, ttl, factory)`.
- TTL is seconds or a `timedelta`; `None` stores forever; zero or less forgets the key and returns `False`. Expiry is an absolute epoch timestamp checked lazily on read, and expired entries are deleted when read.
- `remember(key, ttl)` without a factory returns a decorator. The decorated function becomes async; the cache key is `key` alone for a call without arguments, otherwise `key:` plus a SHA-256 prefix of the pickled `(args, sorted kwargs)` (falling back to `repr` for unpicklable arguments). Arguments that cannot be pickled and whose `repr` is not stable (for example one that includes a memory address that changes per call) produce a new key every call and always miss. A `None` key uses `module.qualname` of the function; the factory form requires a key and raises `ValueError` without one. The decorator and the factory form share entries, so `put("users", ...)` is seen by a decorated function keyed `users` that takes no arguments. Instance methods include `self` in the hashed arguments, so each instance caches separately.
- `CacheManager` resolves a `Repository` per store name, caches it, delegates unknown attributes to the default store, and supports `extend(driver, factory)` for custom stores. `CacheProvider` merges config under `cache`, binds the manager as `cache` and publishes `config/cache.py`. The `Cache` facade defines `remember` on the facade class so decorating at import time does not resolve the container; resolution happens per call. A `.pyi` stub types the facade.
- Out of scope: request memoization, tags and atomic locks (the sketch's lock settings were dropped until locks land).

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

value = await Cache.store("array").get("key")
value = await Cache.store("file").get("key")

users = await Cache.remember("users", 600, lambda: DB.table("users").get())


@Cache.remember("users", 600)
async def users_by_role(role: str):
    return await DB.table("users").where("role", role).get()
```

The default `database` store needs the `caches` table: run `artisan provider:publish` to copy the migration into `databases/migrations/`, then `artisan db:migrate`. Set `CACHE_CONNECTION=file` to skip the table.

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
        }
    )
```

## Delivery

Shipped as small PRs into the `feature/caches` integration branch: (1) this ADR and `CacheConfig`; (2) store contract, `ArrayStore`, `Repository` and `CacheManager`; (3) the `remember` decorator; (4) provider, facade and stub; (5) `FileStore`; (6) `DatabaseStore` and migration.

## Validation

Tests under `fastapi_startkit/tests/cache/`: config defaults and env overrides; per store: miss/hit, cached `None`, expiry, forever, non-positive TTL, forget, flush; `get` with sync and async callable defaults; `remember` runs the factory once and awaits async factories; decorator keys differ per argument set and the function runs once per key; database store upsert under a concurrent insert, corrupt rows and the migration up/down on SQLite; provider binding, facade access after boot and the database store as default.
