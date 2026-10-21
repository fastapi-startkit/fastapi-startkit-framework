# Cache

Every operation that touches a store is async. `Cache.store()` only selects a store and is sync.

## Configuration

```python
from dataclasses import dataclass, field

from fastapi_startkit.cache import ArrayStoreConfig, DatabaseStoreConfig, FileStoreConfig
from fastapi_startkit.environment import env


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

## Reading and writing

```python
from fastapi_startkit.facades import Cache

value = await Cache.get("key")
value = await Cache.get("key", "default")
value = await Cache.get("key", lambda: compute_default())

await Cache.put("key", "value", 600)
await Cache.put("key", "value")
await Cache.forget("key")
await Cache.flush()
```

`ttl` is a number of seconds or a `timedelta`. `None` stores the value forever, and a ttl of zero or less removes the key. A cached `None` counts as a hit.

## Multiple stores

```python
value = await Cache.store("file").get("key")

await Cache.store("array").put("bar", "baz", 600)
```

## Remember

`remember` returns the cached value, or calls the factory on a miss, stores its result and returns it. The factory may be sync or async.

```python
users = await Cache.remember("users", 600, lambda: DB.table("users").get())
```

Used without a factory, `remember` is a decorator. The cache key is the given key plus a hash of the call arguments, so each distinct call is cached separately. The decorated function is always async.

```python
@Cache.remember("users", 600)
async def users_by_role(role: str):
    return await DB.table("users").where("role", role).get()
```

A `with Cache.remember(...)` block is not possible: a `with` block cannot skip its body or produce a value, so the factory and decorator forms cover that use.

## Planned

Request-scoped memoization (`Cache.memo()`), tags (`Cache.tags([...])`) and atomic locks (`Cache.lock(name, seconds)`) are not implemented yet.
