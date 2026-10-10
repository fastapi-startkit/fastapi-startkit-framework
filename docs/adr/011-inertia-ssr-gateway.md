---
title: Inertia SSR gateway with httpx, excepted paths and dev hot mode
date: 2026-10-09
---

## Why

Server-side rendering calls the Inertia Node render server from inside the FastAPI event loop. `_render_ssr` runs `urllib.request.urlopen` in `asyncio.to_thread`, which holds a worker thread for the whole render and cannot be cancelled cleanly on timeout. The SSR configuration is also a bare URL and timeout, so there is no way to turn SSR off for a path, disable it without clearing the URL, check whether the render server is up, or follow the Vite dev server during development.

## How

- `inertia/ssr.py` defines a `SSRGateway` protocol with two async methods: `render(page) -> Optional[dict]` and `healthy() -> bool`. Any object with those methods can be plugged in.
- `HttpSSRGateway(url, timeout, render_path="/render", health_path="/health", transport=None)` posts the page as JSON with `httpx.AsyncClient` and validates the response: it must be a dict with a string `body`, and `head` defaults to `[]`. Any exception, timeout or invalid payload returns `None`, so the page falls back to client rendering. `healthy()` returns true only for a 2xx from `health_path`. The optional `transport` lets tests inject `httpx.MockTransport`.
- `ViteHotFileGateway(hot_file, timeout)` reads the Vite dev server origin from the `hot` file on every call, so restarting Vite is picked up without restarting the app. It delegates to an `HttpSSRGateway` for that origin with `render_path="/__inertia_ssr"`, the endpoint the Inertia Vite plugin serves. A missing hot file means no SSR, and its `healthy()` is true when the file exists.
- `ResponseFactory` holds `ssr_gateway`, `ssr_enabled` and `ssr_except_paths` instead of `ssr_url` and `ssr_timeout`. `InertiaResponse` receives the gateway only when SSR is enabled, and skips it when `request.url.path` matches an except pattern (`fnmatch`, so `/admin/*` matches everything below it). The check runs only for initial HTML visits, as before.
- Facade: `Inertia.ssr(url=..., timeout=1.0, enabled=True, except_paths=())` keeps the existing default URL and sets `HttpSSRGateway`. `url=None` disables SSR. `Inertia.ssr_hot(hot_file, timeout=1.0, enabled=True, except_paths=())` configures the dev gateway. `Inertia.ssr_healthy()` is async and returns false when no gateway is set, so apps can call it from their own `/health` route.
- `httpx` is declared in the `fastapi` extra, since the gateway is only used with FastAPI.

## Alternatives

- Keep `urllib` and make it cancellable: still blocks a thread per render and needs timeout handling that httpx already provides.
- Use a long-lived shared `AsyncClient` on the factory: better connection reuse, but it needs an application lifespan hook to close it. Per-render clients keep the first version simple, and the gateway can own a client later without changing the protocol.
- Read the hot file once at configuration time: fails when Vite restarts on a different port, which is the common dev case.
- Put the except list in config files only: the facade is how the framework is configured today, and the list is per-application, so the same facade method suits it.

## Validation

`tests/inertia/test_ssr.py` covers the httpx render through `MockTransport` (path, payload, head default, invalid payloads, timeouts and connection errors falling back to `None`), health checks, the hot-file gateway (origin read, missing file, restart pickup), and the response path: disabled flag, except patterns, XHR requests never contacting the gateway, and the `page.ssr` shape. The older `urlopen` tests in `tests/inertia/test_inertia_response.py` move to the new gateway, and `tests/inertia/test_inertia.py` covers the facade.
