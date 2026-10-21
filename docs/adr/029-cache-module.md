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

- Package `fastapi_startkit.cache` with `CacheConfig` (`default`, `prefix`, `stores`) and one config dataclass per driver: `ArrayStoreConfig`, `FileStoreConfig(path)` and `DatabaseStoreConfig(connection, table)`. Env names follow the original sketch: `CACHE_CONNECTION` (default `database`), `CACHE_PREFIX` (default `cache`), `CACHE_FILE_PATH`, `DB_CACHE_CONNECTION` (default: the default database connection) and `DB_CACHE_TABLE` (default `caches`). The provider reads it with `resolve_config`, so a plain dataclass of the same shape works (ADR 027).
- Store contract (async): `get(key)` returns a `MISSING` sentinel on a miss so that a cached `None` is a hit; `put(key, value, seconds | None)`, `forget(key)` and `flush()` return `bool`.
- Stores: `ArrayStore` (in-process dict of `(expires_at, value)`, values kept as-is), `FileStore` (one pickled `(expires_at, value)` file per key under `<sha1[:2]>/<sha1[2:4]>/<sha1>` inside the configured path, atomic write through a temp file and `os.replace`, file I/O in `asyncio.to_thread`) and `DatabaseStore` (masoniteorm table `key` primary key, `value` text holding base64 pickle, `expiration` integer; upsert on put; migration stub published by the provider). Pickle allows arbitrary Python values; the cache is trusted storage.
- `Repository` wraps one store and adds the key prefix (`<prefix>:<key>` when a prefix is set) and the public API: `get(key, default=None)` where a callable default is called (and awaited when it returns an awaitable) only on a miss, `put(key, value, ttl=None)`, `has`, `forget`, `flush`, and `remember(key, ttl, factory)`.
- TTL is seconds or a `timedelta`; `None` stores forever; zero or less forgets the key and returns `False`. Expiry is an absolute epoch timestamp checked lazily on read, and expired entries are deleted when read.
- `remember(key, ttl)` without a factory returns a decorator. The decorated function becomes async; the cache key is `key` alone for a call without arguments, otherwise `key:` plus a SHA-256 prefix of the pickled `(args, sorted kwargs)` (falling back to `repr` for unpicklable arguments).
- `CacheManager` resolves a `Repository` per store name, caches it, delegates unknown attributes to the default store, and supports `extend(driver, factory)` for custom stores. `CacheProvider` merges config under `cache`, binds the manager as `cache` and publishes `config/cache.py`. The `Cache` facade defines `remember` on the facade class so decorating at import time does not resolve the container; resolution happens per call. A `.pyi` stub types the facade.
- Out of scope: request memoization, tags and atomic locks (the sketch's lock settings were dropped until locks land).

## Delivery

Shipped as small PRs into the `feature/caches` integration branch: (1) this ADR, config and readme; (2) store contract, `ArrayStore`, `Repository` and `CacheManager`; (3) the `remember` decorator; (4) provider, facade and stub; (5) `FileStore`; (6) `DatabaseStore` and migration.

## Validation

Tests under `fastapi_startkit/tests/cache/`: config defaults and env overrides; per store: miss/hit, cached `None`, expiry, forever, non-positive TTL, forget, flush; `get` with sync and async callable defaults; `remember` runs the factory once and awaits async factories; decorator keys differ per argument set and the function runs once per key; provider binding and facade access after boot.
