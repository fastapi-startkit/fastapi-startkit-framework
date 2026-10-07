---
title: Laravel-style Redis component on redis.asyncio
date: 2026-10-07
---

## Why

Applications need Redis for caching, counters, locks and pub/sub, and the framework had no first-class integration. Users coming from Laravel expect `config('redis')` named connections, a `Redis` facade proxying commands to the default connection, and `Redis::connection()`, `command()`, `pipeline()`, `transaction()`, `publish()`, `subscribe()`, `psubscribe()` and `eval()`. FastAPI is async, so every call must be awaitable.

## How

- New `fastapi_startkit.redis` package: `RedisConfig`, `RedisManager`, `Connection`, `RedisProvider`. Built on `redis.asyncio` (redis-py >= 5) and shipped as the optional extra `fastapi-startkit[redis]`. `redis` is imported lazily inside the connector, so importing the package, the provider or the facade never fails; resolving a connection without the package raises `RedisNotInstalledError` with the install hint.
- Config mirrors Laravel's `database.redis` block: `client` (`REDIS_CLIENT`, default `redis`), `options` (`cluster`, `prefix` from `REDIS_PREFIX`, default `slug(APP_NAME, "_") + "_database_"`) and named connections `default` and `cache` built from `REDIS_URL`, `REDIS_HOST`, `REDIS_USERNAME`, `REDIS_PASSWORD`, `REDIS_PORT`, `REDIS_DB` / `REDIS_CACHE_DB`. Python dataclasses cannot hold arbitrary sibling keys, so connections live under `connections` (the same deviation `DatabaseConfig` already makes). Per-connection `options` override the global ones; unknown connection keys are passed to `redis.asyncio.Redis` (e.g. `ssl`, `socket_timeout`); `decode_responses` defaults to `True` so values come back as `str`, like Laravel.
- `RedisProvider` binds the manager as `redis`, merges config under `redis`, publishes `config/redis.py`, and registers a FastAPI shutdown handler calling `manager.disconnect()`.
- `RedisManager.connection(name=None)` resolves and caches one `Connection` per name (default `default`); an unknown name raises `ValueError("Redis connection [x] not configured.")` (Laravel throws `InvalidArgumentException`). `extend(client, factory)` registers custom client factories (Laravel's `Redis::extend`), used by tests to plug in fakeredis. `purge(name)` / `disconnect()` close clients. Unknown attributes on the manager proxy to the default connection, and on a connection proxy to the redis-py client, so `Redis.get/set/hgetall/publish/eval/...` work through the facade.
- `Connection.command(method, params)` calls the client method (or `execute_command` for commands redis-py lacks). `pipeline(callback=None)` and `transaction(callback=None)` return a redis-py pipeline (non-transactional / MULTI-EXEC) for `async with`, or, given a sync/async callback, queue the commands and return the executed results, like Laravel. `subscribe(channels, callback)` / `psubscribe(patterns, callback)` loop over a `PubSub` and call `callback(message, channel)` until cancelled.
- Key prefix: redis-py has no native prefix (phpredis `OPT_PREFIX`), so the connector wraps the client's and each pipeline's `execute_command` and prefixes key arguments using a per-command key-position table (first key, all keys, all-but-timeout, interleaved MSET, EVAL/EVALSHA `numkeys`, ...). Commands not in the table and pub/sub channels are left unprefixed, which keeps behaviour predictable instead of guessing key positions.
- Facade `fastapi_startkit.facades.Redis` (key `redis`) with a `.pyi` stub describing the manager/connection API and common commands.

## Verification

Tests under `fastapi_startkit/tests/redis/` use `fakeredis[lua]` (dev dependency) through `extend`: config defaults/env overrides, separate cached clients per connection, unknown connection error, missing-package error, prefixing across command shapes and pipelines, command/pipeline/transaction with sync and async callbacks, publish/subscribe/psubscribe, eval, provider binding and facade access after boot, and shutdown disconnect. Full suite and coverage threshold pass.
