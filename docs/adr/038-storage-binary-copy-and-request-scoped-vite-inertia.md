# 038. Storage binary reads and relative copy; request-scoped Vite and Inertia state

Date: 2026-10-25

## Problem

Storage (`storage/drivers/local.py`, `s3.py`):

- `LocalDriver.copy` passed its arguments straight to `shutil.copyfile`, so `Storage.copy("a.txt", "b.txt")` resolved against the process working directory instead of the disk root and raised `FileNotFoundError`.
- `LocalDriver.get` opened files in text mode and `S3Driver.get` decoded the body as UTF-8, so reading a binary file such as a `.png` raised `UnicodeDecodeError`. No driver offered a bytes-returning read.
- `S3Driver.append` built the combined content but uploaded only the new `content`, so every append replaced the object.

Vite (`vite/vite.py`):

- `use_script_tag_attributes`, `use_style_tag_attributes` and `use_preload_tag_attributes` wrapped a dict as `attributes = lambda *_: attributes`. The lambda closes over the rebound name, so it returned itself and `dict.update` raised `TypeError`. Passing a dict, as documented, never worked.
- The CSP nonce and preloaded-asset map were instance attributes on the single `vite` container binding. A nonce set while handling one request was used by every concurrent request.

Inertia (`inertia/inertia.py`):

- `Inertia.set_root_view` and `Inertia.version` always wrote to the process-wide `ResponseFactory`. Called inside a request, they changed the root view and version for every concurrent and later request. ADR 007 already gives each request an `InertiaRequestState`; these two setters ignored it.

## Alternatives

Binary reads:

1. Change `get` to always return `bytes`. Breaks every caller and test that expects text.
2. Add only a `get_bytes` method. Keeps `get` crashing on binary files.
3. `get` reads bytes and returns `str` when the content is valid UTF-8, otherwise the raw `bytes`; plus a `get_bytes` that always returns `bytes`.

Per-request Vite state:

1. Create a `Vite` instance per request. Every template global and facade would need a request-aware lookup.
2. Keep the nonce and preloaded assets in bare `ContextVar`s. A value set in a child task never reaches the parent. A dict created lazily in an outer context (boot, warm-up, CLI) is inherited by every later request task, which brings the leak back. A `BaseHTTPMiddleware` that reads after `call_next` sees nothing, because the endpoint runs in a child task. A nonce set during lifespan, which uvicorn runs in its own task, never reaches requests.
3. Give each task its own state, the way `Cache.memo` does (ADR 029). This removes the leak, but a middleware reading after `call_next` still sees nothing, and a nonce set at startup still does not act as a default.
4. Open an explicit request scope in a small ASGI middleware. The scope holds the state object for that request and shares it with every child task of the request. Outside a scope, the instance-level values act as process-wide defaults.

## Decision

- `LocalDriver.copy` resolves both paths through `get_path`, like `move`. Absolute paths still work because `os.path.join` keeps them.
- Binary reads take option 3 on both the local and S3 drivers. `get_bytes` returns `None` for a missing file, the same as `get`. `decode_text` in `storage/helper.py` is shared. `StorageManager` and the `Storage` facade proxy `get_bytes`. Reading in binary mode means `get` no longer converts `\r\n` to `\n`.
- `get` only decodes UTF-8. A text file in another encoding (for example latin-1 `caf\xe9`) is not valid UTF-8, so `get` returns it as `bytes`. Callers that need a fixed type use `get_bytes` and decode it themselves.
- `S3Driver.append` uploads the existing content followed by the new content, and returns the new content like `LocalDriver.append`.
- Vite turns non-callable attributes into a resolver through `_as_resolver`, which binds the value instead of the name. Dicts and `False` (to skip preloads) now work.
- Vite takes option 4. `Vite.request_scope()` is a context manager. It sets a fresh `ViteRequestState` (nonce and preloaded assets) in a per-instance `ContextVar` and resets it on exit. A nested scope reuses the outer state. Inside a scope, `use_csp_nonce` sets the request nonce and `csp_nonce` returns it, falling back to the process-wide default. `preloaded_assets` and `flush` act on the request dict. Outside a scope, they act on the instance-level default nonce and dict, the same as before this change. So a nonce set at startup or in lifespan is the default for every request.
- `ViteMiddleware` is a pure ASGI middleware. It wraps each `http` and `websocket` scope in `vite.request_scope()` and passes `lifespan` through unchanged. It takes `vite=` or resolves `vite` from the container on first use. `ViteProvider.boot` registers it when FastAPI is installed. Because it is pure ASGI, the endpoint and any inner `BaseHTTPMiddleware` share the same state object, so a Link-header middleware inside it can read `preloaded_assets()` after `call_next`. Middleware added with `app.add_middleware` after providers boot sits outside the provider's `ViteMiddleware`. If such a middleware reads preloaded assets, add `ViteMiddleware` again after it. The outer instance opens the scope, and the inner one reuses it.
- The manifest cache stays shared, because it is keyed by path and does not depend on the request.
- `ResponseFactory.set_root_view` and `set_version` write to the current `InertiaRequestState` when one exists, and to the global defaults otherwise, the same as `share` and `set_encrypt_history`. A version set during a request is resolved immediately and wins over the middleware's version for that request.

## Validation

- Local driver: relative `copy`, a UTF-8 `get`, a binary `get` and `get_bytes`, and a missing file through `get_bytes`. The S3 driver gets matching tests plus `append` with and without existing content, and a `Storage.fake` test covers the facade.
- Vite: dict attributes for script, style and preload tags, and `False` for preloads. `tests/vite/test_request_scope.py` covers the following:
  - An outer render followed by two concurrent requests: each request sees only its own key.
  - Three concurrent requests with a default nonce: two override it, and one keeps the default.
  - A nonce set in a separate startup task reaches requests.
  - An inner `BaseHTTPMiddleware` reads the preloaded assets after `call_next`.
  - An outer `ViteMiddleware` wraps middleware added after the provider's.
  - Lifespan passes through, nested scopes are reused, container resolution works, and the provider registers the middleware.
- Inertia: two concurrent requests through `InertiaMiddleware` each set a root view and version, then wait on a shared barrier. Each response returns its own values, and the global defaults are unchanged. Outside a request, the setters still configure the defaults.
- All new tests fail on the old code.
