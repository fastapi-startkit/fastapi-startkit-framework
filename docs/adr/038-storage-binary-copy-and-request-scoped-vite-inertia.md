# 038. Storage binary reads and relative copy; request-scoped Vite and Inertia state

Date: 2026-10-25

## Problem

Storage (`storage/drivers/local.py`, `s3.py`):

- `LocalDriver.copy` passed its arguments straight to `shutil.copyfile`, so `Storage.copy("a.txt", "b.txt")` resolved against the process working directory instead of the disk root and raised `FileNotFoundError`.
- `LocalDriver.get` opened files in text mode and `S3Driver.get` decoded the body as UTF-8, so reading a binary file such as a `.png` raised `UnicodeDecodeError`. No driver offered a bytes-returning read.

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
2. Keep the nonce on a `ContextVar`. Each asyncio task (each request under Starlette) sees its own value without any change to callers.

## Decision

- `LocalDriver.copy` resolves both paths through `get_path`, like `move`. Absolute paths still work because `os.path.join` keeps them.
- Binary reads take option 3 on both the local and S3 drivers. `get_bytes` returns `None` for a missing file, the same as `get`. `decode_text` in `storage/helper.py` is shared. `StorageManager` and the `Storage` facade proxy `get_bytes`. Reading in binary mode means `get` no longer converts `\r\n` to `\n`.
- Vite turns non-callable attributes into a resolver through `_as_resolver`, which binds the value instead of the name. Dicts and `False` (to skip preloads) now work.
- Vite stores the nonce and the preloaded-asset map in `ContextVar`s owned by the instance. `use_csp_nonce`, `csp_nonce`, `preloaded_assets` and `flush` keep their signatures. The manifest cache stays shared, because it is keyed by path and does not depend on the request.
- `ResponseFactory.set_root_view` and `set_version` write to the current `InertiaRequestState` when one exists, and to the global defaults otherwise, the same as `share` and `set_encrypt_history`. A version set during a request is resolved immediately and wins over the middleware's version for that request.

## Validation

- Local driver: relative `copy`, a UTF-8 `get`, a binary `get` and `get_bytes`, and a missing file through `get_bytes`. The S3 driver gets matching tests, and a `Storage.fake` test covers the facade.
- Vite: dict attributes for script, style and preload tags, `False` for preloads, and two concurrent tasks that each set a different nonce and render tags. The test checks that each task sees only its own nonce and that the outer context stays unset.
- Inertia: two concurrent requests through `InertiaMiddleware` each set a root view and version, then wait on a shared barrier. Each response returns its own values, and the global defaults are unchanged. Outside a request, the setters still configure the defaults.
- All new tests fail on the old code.
