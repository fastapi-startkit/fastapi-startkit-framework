# 009: Inertia redirects, flash, error bags, history flags and in-memory session

Date: 2026-10-09
Status: Accepted

## Problem

The Inertia adapter was missing several server-side helpers from the Inertia v3 protocol:

- external redirects (`location`)
- `back()` redirects
- one-time `page.flash` data
- validation error bags
- `encryptHistory` / `clearHistory`
- `preserveFragment`

`InertiaMiddleware.reflash()` rewrote the session value it had just read, so it never did anything. Every feature that carries data to the next page needs a session, but tests had no lightweight session, and data queued without a session was silently lost.

## Alternatives

- **Laravel-style flash aging (flash, age, reflash).** This needs a session lifecycle the framework does not have. The adapter would have to mark data as new or old on every request.
- **Queue data in request state and write it to the session when the response ends.** This needs a step after the response that knows which responses rendered a page. It also cannot see data consumed inside a streaming response.
- **Write to the session immediately and take the value when a page renders (chosen).** Data stays in the session until a page renders and removes it. So it survives any number of redirects and 409 version reloads without a reflash step, and it appears exactly once.

## Decision

`inertia/session.py` owns the session keys and the queue helpers:

| Key | Holds |
|-----|-------|
| `_flash` | flash data |
| `_inertia_errors` | error bags: `{bag: {field: [messages]}}` |
| `_inertia_clear_history` | the clear-history flag |
| `_inertia_preserve_fragment` | the preserve-fragment flag |

- **Writing:** when the request has a Starlette session, helpers write to `request.session`. Otherwise they write to a per-request fallback dict on `InertiaRequestState` and log a warning. Data in the fallback is still visible to a render in the same request.
- **In-memory session for tests:** `fastapi_startkit.inertia.testing.FakeSessionMiddleware(app, session=None)` puts one dict into `scope["session"]` for every request, so tests can work with a session without signed cookies. Every client shares that dict, so it is test-only: it is not exported from `fastapi_startkit.inertia`, and keying storage per client was rejected because a real app should use a cookie-backed session.
- **Flash:** `Inertia.flash(key | dict, value=None)` queues flash data. `InertiaResponse.flash()` adds flash data to that response only. Rendering takes the queued flash, merges in the response flash, and sends the result as `page.flash` (left out when empty). `reflash()` is removed, and the middleware no longer calls it.
- **Errors:** `ValidationErrors` (`inertia/errors.py`) offers `add`, `has`, `first`, `get`, `merge`, `all` and `make`. `make` accepts a mapping, `ValidationErrors`, a pydantic `ValidationError` or a FastAPI `RequestValidationError`; for the FastAPI error it drops the `body`/`query` part of the location, matching `ValidationExceptionHandler`.
  - `Inertia.with_errors(errors)` and `Inertia.with_errors_in(bag, errors)` merge errors into a bag. The default bag is `default`.
  - The legacy `session["errors"]` written by `ValidationExceptionHandler` is read as the `default` bag.
- **Resolving errors (`InertiaMiddleware.resolve_validation_errors`)**, following Laravel. The middleware shares `errors` as a lazy prop, so bags are taken out of the session only when a page renders. Redirect hops keep them, and errors added during the request show on the page that request renders.
  - Each field gets its first message, or the full list when the middleware sets `with_all_errors = True`.
  - The `default` bag is nested under the `X-Inertia-Error-Bag` header when present, and returned flat otherwise.
  - Without a `default` bag, all bags are returned keyed by name.
- **Redirects:**
  - `InertiaRedirect(RedirectResponse)` adds chainable `with_errors`, `with_errors_in`, `flash`, `clear_history` and `preserve_fragment`, which queue data straight away.
  - `Inertia.redirect(url, status_code=302)` returns an `InertiaRedirect`.
  - `Inertia.back(status_code=302)` returns an `InertiaRedirect` to the Referer, or `/` if there is none.
  - `fastapi_startkit.fastapi.referer.same_origin_referer()` validates the Referer for `back()`, the middleware's empty-response redirect, and `ValidationExceptionHandler`. Behind a TLS-terminating proxy, the proxy headers middleware must be configured so `request.base_url` matches the browser's origin; otherwise absolute same-site Referers fall back to `/`. Relative paths starting with a single `/`, and absolute URLs with the request's scheme and host, are followed. Anything else (another host, `//host`, `javascript:`, bare relative paths) falls back to `/`, so neither can be used as an open redirect.
  - Converted redirects (an empty response redirected back, a 302 turned into a 303, a fragment redirect turned into a 409) keep queued flash data and errors without a reflash step, because nothing renders a page that would take them out of the session.
  - `Inertia.back_with_errors(errors, bag=None)` does the same and also stores the errors.
  - The 302 → 303 conversion after PUT/PATCH/DELETE in the middleware still applies.
- **Location:** `Inertia.location(url)` returns 409 with `X-Inertia-Location` for an Inertia request, and a 302 otherwise.
- **History:**
  - `Inertia.encrypt_history(enabled=True)` sets the global default outside a request, or a per-request override during one.
  - `InertiaResponse.encrypt_history(enabled=True)` overrides it for one response.
  - `Inertia.clear_history()` queues the clear-history flag.
  - `page.encryptHistory` and `page.clearHistory` are always included as booleans.
- **Fragment:** `Inertia.preserve_fragment()` queues the flag, and `page.preserveFragment` is sent only when it is true.

## Validation

All tests use `FakeSessionMiddleware` with the FastAPI TestClient, with and without `X-Inertia`:

- `location` returns 409 for Inertia visits and 302 otherwise.
- `back` follows the Referer and falls back to `/`. `back_with_errors` errors appear on the next render, nested under the error bag when the header is set.
- `with_all_errors` returns lists, while the default returns the first message.
- Errors survive a plain redirect hop before the page renders.
- Flash queued before a redirect appears once, then disappears. Flash set in the same request appears on that page. Flash survives a 409 version reload.
- `encryptHistory` is set when enabled globally or for one response. `clearHistory` and `preserveFragment` appear on the next page only.
- Queueing without a session logs a warning.
- The full suite, the coverage threshold, ruff and basedpyright all pass.
