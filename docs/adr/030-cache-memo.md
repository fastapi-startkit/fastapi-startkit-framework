---
title: Request-scoped cache memoization with Cache.memo()
date: 2026-10-21
---

## Problem

A request or job often reads the same cache key several times (for example settings or the current tenant). With the file, database or Redis store each read is I/O and unpickling. Laravel solves this with `Cache::memo()`, a repository that remembers values read from the underlying store for the rest of the request. The framework has no request object to hang that state on, and the cache API is async, so state must follow the running task without leaking between concurrent requests.

## Alternatives

- **Process-wide dict.** Shared by every request, so one request sees values another request cached and never sees later writes from other workers. Rejected.
- **Middleware that opens a scope per request.** Needs FastAPI wiring in the cache provider, does nothing for queue jobs or console commands, and a memo used outside the middleware would fall back to something else anyway. Rejected.
- **`ContextVar` holding a dict, created on first use.** Simple, but a dict created in a parent context (lifespan, a test fixture, a worker loop) is inherited by every child task, so all requests would share it. Rejected on its own.
- **`ContextVar` holding a dict tagged with the task that created it.** A task that finds a dict owned by another task starts a fresh one. Chosen.

## Decision

- `cache/memo_store.py` adds `MemoStore(store)`, a `Store` that wraps another store. `get` returns the memoized value for the key when present, otherwise reads the inner store and memoizes the result, including `MISSING`, so repeated misses are free too. `put` and `forget` write through and drop the memoized key, so the next `get` re-reads the store. `flush` flushes the inner store and clears this store's memo.
- Memo state lives in one module `ContextVar` holding `(weakref to owning task, {MemoStore: {key: value}})`. On access, when there is no state or the owner is not `asyncio.current_task()`, a new dict is created and set for the current context. Each request, job or `asyncio` task therefore starts empty, and a dict is never shared with a sibling task. Child tasks (`asyncio.gather`, `create_task`) start their own memo; they still read through to the same store.
- Memoized values ignore TTL for the rest of the task: a value that expires in the store mid-request stays visible to that request, matching Laravel. Values are kept as the same object, so mutating a memoized value mutates what later reads in the task see.
- `CacheManager.memo(name=None)` returns a `Repository` over `MemoStore(store(name).store)` with the same prefix, cached per store name, so `Cache.memo()` uses the default store and `Cache.memo("file")` a named one. Every repository method (`get`, `put`, `remember`, the decorator, ...) works through it.
- The facade reaches `memo` through the manager; the `.pyi` stub adds `memo(name=None) -> Repository`.

## Usage

```python
from fastapi_startkit.facades import Cache

settings = await Cache.memo().get("settings")
settings = await Cache.memo().get("settings")  # no store hit

tenant = await Cache.memo("redis").remember("tenant", 600, load_tenant)
```

## Validation

`tests/cache/test_memo_store.py` (unittest): a repeated `get` reads the inner store once; a miss is memoized; `put`/`forget` invalidate the memoized key and write through; `flush` clears the memo and the inner store; separate `asyncio` tasks do not share memo state, including when state already exists in the parent context; two stores keep separate memos; the manager returns one memo repository per store with the configured prefix.
