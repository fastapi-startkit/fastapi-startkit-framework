# 007: Inertia request-scoped state and middleware protocol fixes

Date: 2026-10-09
Status: Accepted

## Problem

`InertiaMiddleware.dispatch` changed the process-wide `ResponseFactory` singleton on every request:

- `Inertia.share(self.share(request))` wrote each request's validation errors into the global `shared_props`. Concurrent requests could then render another user's errors.
- `Inertia.version(lambda: self.version(request))` replaced any version configured in a provider's `boot()`.
- `Inertia.set_root_view(self.root_view(request))` reset a configured root view to `index.html`.

The middleware also broke parts of the Inertia protocol:

- It overwrote the `Vary` header.
- It never called `on_empty_response`.
- It ran the handler before checking the version, so a stale client still triggered side effects and used up the session errors.
- Its 409 response did not include `X-Inertia-Version`.
- It did not treat `201 + Location` as a redirect when checking for fragments.
- It converted redirects to 409 responses for prefetch requests too.

The `inertia()` template helper escaped only `<` in the page JSON.

## Alternatives

- **Copy the factory per request.** This needs a factory for every request, and code that holds a reference to `Inertia.instance()` would miss per-request changes.
- **Store per-request data on `request.state`.** `ResponseFactory.render` has no request argument, so it would still have to look up the request through the context variable.
- **Add a request-scoped context variable next to `current_request` (chosen).** The middleware already sets a `ContextVar` for the request. A second one holds an `InertiaRequestState`, and the factory reads it while handling a request.

## Decision

`inertia/context.py` adds `InertiaRequestState(shared_props, root_view, version)` and a `current_state` context variable. The middleware sets the context variable for the duration of each request.

- **Sharing:** `ResponseFactory.share()` writes to the request state while a request is active. Outside a request, such as in a provider's `boot()`, it writes to the global props. `ResponseFactory.shared()` / `Inertia.shared()` return the global props merged with the request props. `render()` saves a snapshot of these merged props, and props passed to `render()` still override them.
- **Version:** a configured `Inertia.version()` value or callable wins. A callable is evaluated each time the version is read. Without a configured version, the request state uses `InertiaMiddleware.version(request)`, which returns the Vite manifest hash.
- **Root view:** `InertiaMiddleware._root_view` defaults to `None`. A subclass that sets `_root_view` or overrides `root_view()` provides a value for that request. Otherwise the factory uses `Inertia.set_root_view()`, with `index.html` as the default. `InertiaResponse.with_root_view()` still wins for its own response.
- **Order of steps in the middleware:** set the context variables, then check the version. On a GET Inertia request with a different version, it reflashes the session and returns 409 with `X-Inertia-Location` and `X-Inertia-Version`. Otherwise it shares the request props and calls the handler. After the handler, it reflashes on redirects. For Inertia requests it then handles:
  - an empty 200 (`Content-Length: 0`), which becomes a redirect back to the Referer or `/`
  - a 302 after PUT/PATCH/DELETE, which becomes a 303
  - a fragment redirect (3xx, or 201 with a Location header), which becomes a 409 with `X-Inertia-Redirect`, except when the request has `Purpose: prefetch`.
- **Vary:** the middleware appends `X-Inertia` to any existing `Vary` values and skips it if it is already listed (case-insensitive).
- **HTML-safe JSON:** `inertia/encoding.py` provides `html_safe_json()`, which escapes `<`, `>`, `&`, U+2028 and U+2029 as `\uXXXX`. The `inertia()` helper uses it.

`on_version_change(request)` no longer takes a `response`, because it runs before the handler.

## Validation

- Concurrency test: two interleaved requests with different session errors each get only their own errors. Shares made at boot time still appear, and props passed to render override them.
- Tests for each case: version from boot, Vite hash fallback, and a callable version. The 409 response has both headers, and flash data survives it.
- Root view tests: the view set at boot, a subclass override, and `with_root_view()`.
- Tests for an empty response with and without `X-Inertia`, 303 after PUT, `201 + Location#frag`, a prefetch request that keeps its redirect, and `Vary` values that are kept without duplicates.
- A page JSON containing `</script>`, `&`, `>` and U+2028 contains no raw `<>&` and parses back to the same value.
- The full framework suite, the coverage threshold, ruff and basedpyright all pass.
