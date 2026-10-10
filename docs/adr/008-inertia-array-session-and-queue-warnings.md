---
title: Inertia in-memory session and warnings for queued session data
date: 2026-10-09
---

## Why

Inertia state that must reach the next page (validation errors, the preserve-fragment flag, and later flash data and history flags) lives in the request session. Testing those features needs a real session middleware and cookies, and a request that queues data with no session currently fails with a `RuntimeError`, which stops the handler. Omega ships an `ArraySession` for this, a plain in-memory store.

## How

- `inertia/session.py` adds `ArraySession`, a `dict` subclass. Starlette exposes `request.session` as `scope["session"]`, and a dict satisfies everything the package reads and writes, so no adapter is needed. It is for tests and single-process use only: it is not shared across processes, and it is not per-user.
- `InertiaMiddleware(app, session=None)` takes an optional session. When one is given and the scope has no `session`, the middleware sets it for the request. Passing the same instance on every request lets a test follow data from one request to the next. The default is `None`, so production apps with `SessionMiddleware` see no change, and an app without a session never gets a shared in-memory store by accident.
- Queueing session data without a session (`Inertia.back_with_errors`, `Inertia.preserve_fragment`) no longer raises. It emits `InertiaSessionWarning` (a `UserWarning` subclass) naming the data that was dropped and the two fixes (add `SessionMiddleware`, or pass a session to `InertiaMiddleware`), and the request continues without storing the data. A missing request context (no middleware at all) still raises `RuntimeError`, because no page can be built without it.

## Alternatives

- Keep raising: makes the missing-session case fail the request instead of only losing the flash.
- Fall back to an in-memory session automatically: silently shares state between users in production.
- Store queued data on `request.state`: nothing reads it on the next request, so it would not reach the next page.

## Validation

`tests/inertia/test_session.py` covers the middleware session option (data follows across requests), the warning with no session for errors and preserved fragments, and that no warning is raised when a session is present. Existing back-with-errors tests are updated from the old `RuntimeError` expectation.
