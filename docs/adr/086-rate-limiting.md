# 086. Laravel-style rate limiting

- Date: 2026-11-18
- Status: Accepted

## Problem

The framework has no rate limiting. `facades/RateLimiter.py` is a stub bound to a `rate` key that nothing registers, and its `.pyi` describes an API that does not exist. `ThrottleRequestsException` (429) exists but nothing raises it. Applications that need to limit logins, API calls or expensive actions have to hand-roll counters.

Laravel 13 offers `RateLimiter::for('login', fn (Request $r) => Limit::perMinute(5)->by($r->email.$r->ip()))`, the low-level `RateLimiter::attempt/hit/tooManyAttempts/remaining/availableIn/clear` API backed by the cache, and the `throttle:<name>` middleware that answers 429 with `Retry-After` and `X-RateLimit-*` headers.

## Alternatives

- **Port Laravel's limiter onto the existing cache `Repository`.** (chosen) Counters live in whichever cache store the app already configured (array, file, database, redis), so limits are shared between workers when the store is shared. No new dependency.
- **`slowapi` / `fastapi-limiter`.** Different API (decorators keyed by strings like `"5/minute"`), their own storage backends, and no named limiters or `Limit` objects. Does not match the Laravel API the framework mirrors.
- **A separate store abstraction for counters.** Duplicates the cache stores. Only needed when no cache is configured, which an `ArrayStore`-backed `Repository` already covers.
- **ASGI middleware instead of a dependency.** Middleware runs before routing, so it cannot be attached per route or per router the way `throttle:<name>` is. A FastAPI dependency can be added to a route, a `Router(dependencies=[...])` or the whole app.

## Decision

```python
from fastapi import Depends
from fastapi_startkit.facades import RateLimiter
from fastapi_startkit.rate_limiting import Limit, throttle

RateLimiter.for_("login", lambda request: Limit.per_minute(5).by(request.client.host))
RateLimiter.for_("uploads", lambda request: [Limit.per_minute(10).by(ip(request)), Limit.per_day(100).by(ip(request))])

router.post("/login", login, dependencies=[Depends(throttle("login"))])
api = Router(dependencies=[Depends(throttle(max_attempts=60, decay_minutes=1))])

if await RateLimiter.too_many_attempts(key, 5):
    seconds = await RateLimiter.available_in(key)
await RateLimiter.attempt(key, 5, send_message, decay_seconds=60)
```

- `for` is a Python keyword, so the registration method is `for_(name, callback)`, the same trailing-underscore convention `with_` uses in Socialite. It returns the limiter for chaining. `limiter(name)` returns the callback and raises `LimiterNotDefinedException` (a `ValueError`) for an unknown name.
- `Limit` is a dataclass `(max_attempts, decay_seconds=60, key="", response_callback=None)` with `per_second(n, decay_seconds=1)`, `per_minute(n, decay_minutes=1)`, `per_minutes(decay_minutes, n)`, `per_hour(n, decay_hours=1)`, `per_day(n, decay_days=1)`, fluent `by(key)` and `response(callback)`, and `Limit.none()` returning `Unlimited`, which the throttle skips. Callbacks may be sync or async and may return one `Limit` or a list.
- `RateLimiter(cache)` takes a zero-argument callable returning a cache `Repository`, resolved on first use so provider order does not matter. Methods are async because the cache is: `attempt(key, max_attempts, callback, decay_seconds=60)` (returns the callback result or `True` when that result is falsy, as Laravel's `?: true`, so only a limited attempt returns `False`), `too_many_attempts`, `hit`, `increment(key, decay_seconds=60, amount=1)`, `decrement`, `attempts`, `reset_attempts`, `remaining`, `retries_left`, `available_in`, `clear`.
- Storage mirrors Laravel: `key` holds the hit count and `key:timer` the integer unix time the window ends; both are written with the window's remaining TTL. The window is judged from the stored timer against `int(time.time())`, not from cache expiry, so an expired window resets even on stores that keep stale entries. `time.time` is the clock the cache stores already use, so tests move both with one `mock.patch("time.time")`; `pendulum.travel` was rejected because it needs pendulum's optional `test` extra and would not move store expiry. The `Repository` has no atomic increment, so every read-modify-write runs under the store's own lock (`Repository.lock`, implemented by the array, file, database and redis stores) named `key:lock`: `increment`/`hit` take it around the count update, and `attempt` holds it across the check and the hit. `attempt` records the hit before running the callback and outside the lock, as Laravel does, so a callback that raises still consumes an attempt and a slow callback does not block other requests. `locked(*keys)` acquires the locks in sorted order to avoid deadlock between overlapping key sets. Before each store lock it takes a per-key `asyncio.Lock` (held in a `WeakValueDictionary`), so requests in one process queue locally and only one per key polls the store; without it, 60 requests polling a database store kept the pool busy and starved the holder past the timeout. The store lock still serializes separate processes, which the tests simulate with two limiters on one store. The store lock polls every 10 ms (`lock_sleep`) and gives up with `LockTimeoutError` after `lock_seconds` (10), which is also the lock TTL so a crashed holder cannot wedge a key.
- Drivers are the cache stores, as in Laravel (`cache.limiter`): the limiter has no driver of its own. `RateLimiterProvider` (key `rate_limiter`) merges `RateLimiterConfig(store=env("RATE_LIMITER_STORE", None))`, publishes it as `config/rate_limiter.py`, and binds `rate_limiter`. `store` names a store in `config/cache.py` (`array`, `file`, `database`, `redis`, or any custom one); unset means the cache default store. With a `cache` binding it uses `cache.store(store)`. Without one, an unset `store` falls back to a private `Repository(ArrayStore())`, and a named `store` raises a `RuntimeError` asking for `CacheProvider` instead of silently counting in memory. A separate driver setting was rejected because it would duplicate the cache store configuration (paths, tables, redis connections, prefixes).
- The `RateLimiter` facade now uses key `rate_limiter`; its `.pyi` describes the real API. The old stub had no working implementation, so no caller breaks.
- `throttle(name=None, max_attempts=60, decay_minutes=1, prefix="")` returns a FastAPI dependency. A named limiter evaluates its callback with the request; each limit's cache key is `md5(prefix + name + decay + limit.key)`, so limits sharing a `by` key count separately only when their decays differ; two limits with the same decay and key share one counter. Without a name, one limit keyed by the client host is used. It holds the locks of all its limits while it checks every limit and then hits them, so a concurrent burst admits exactly `max_attempts`; the 429 response, including a `response` callback, is built after the locks are released. A rejected request consumes none of the limits (Laravel hits earlier limits in the list before a later one rejects). On success it sets `X-RateLimit-Limit` and `X-RateLimit-Remaining` on the response (from the last limit, as Laravel does). When limited it raises `ThrottleRequestsException` with `Retry-After`, `X-RateLimit-Reset`, `X-RateLimit-Limit` and `X-RateLimit-Remaining: 0`; when the limit has a `response` callback, the callback gets `(request, headers)` and its returned `Response` is raised in the new `HttpResponseException`, which `HTTPExceptionHandler.render` returns as is and `report` skips, so a custom 5xx throttle response is not reported as a server error.

## Validation

- Unit tests for `Limit` factories, `by`, `response`, `none` and the limiter API with a patched `time.time` for window expiry, independent keys, `attempt`, `decrement`, `clear` and unknown limiter names.
- The same limiter scenarios (limit, window reset, independent keys, clear) run against `ArrayStore`, `FileStore`, `DatabaseStore` (sqlite) and `RedisStore` (fakeredis).
- Concurrency regressions on every store: `asyncio.gather` of 10 hits counts exactly 10, 20 concurrent `attempt` calls against 5 admit exactly 5, the same across two limiters sharing one store (they fail with the store lock disabled), three concurrent bursts of 20 through `throttle` with layered limits admit exactly 5 per window, and three concurrent bursts in one window admit exactly 5 in total. The `DatabaseStore` runs on file-backed SQLite with the real `SQLiteConfig.engine_options()` (ADR 089).
- Provider tests: binding, cache-store selection via config and `RATE_LIMITER_STORE`, fallback without `CacheProvider`, the error for a named store without it, the published config, facade access.
- `HttpTestCase` integration tests hitting throttled routes: headers on success, 429 with `Retry-After` and `X-RateLimit-*`, per-key independence, multiple limits, `Limit.none()`, async callbacks, custom responses and the unnamed throttle.
- `uv run pytest --ignore=tests/masoniteorm/postgres --cov` stays at or above 80%.
