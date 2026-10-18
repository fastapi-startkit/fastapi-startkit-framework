---
title: Inertia SSR gateway with httpx, except paths, health check and dev hot mode
date: 2026-10-10
---

## Why

Server-side rendering calls the Inertia Node render server from inside the FastAPI event loop. `InertiaResponse._render_ssr` runs `urllib.request.urlopen` in `asyncio.to_thread`, which holds a worker thread for the whole render and cannot be cancelled cleanly on timeout. The SSR configuration is a bare URL and timeout, so there is no way to turn SSR off for some paths, disable it without clearing the URL, check whether the render server is up, follow the Vite dev server during development, or plug in a different renderer. An unfinished attempt (`task/inertia-ssr-gateway-wip`, d7bb3355) was written before the request-state, prop pipeline and session refactors (ADR 007-010) and cannot be rebased as a whole; its SSR module is kept and integrated with the current response code.

## Alternatives

- Keep `urllib` and make it cancellable: still blocks a thread per render and duplicates the timeout handling httpx provides.
- One long-lived `AsyncClient` on the factory: better connection reuse, but it needs an application lifespan hook to close it. A client per call keeps this change self-contained, and a gateway can own a client later without changing the protocol.
- Read the hot file once at configuration time: breaks when Vite restarts on another port, the common dev case.
- Put the gateway behind the container instead of the facade: Inertia is configured through the `Inertia` facade today, so SSR stays there.

## Decision

`inertia/ssr.py` defines a runtime-checkable `SSRGateway` protocol with `async render(page) -> Optional[dict]` and `async healthy() -> bool`. Any object with those methods can be configured.

- `HttpSSRGateway(url, timeout=1.0, render_path="/render", health_path="/health", transport=None)` posts the page as JSON with `httpx.AsyncClient`. The response must be a dict with a string `body`; `head` defaults to `[]`. HTTP errors, timeouts, non-2xx responses and invalid payloads return `None`. `healthy()` is true only for a 2xx from `health_path`. `transport` lets tests inject `httpx.MockTransport`.
- `ViteHotFileGateway(hot_file, timeout=1.0, transport=None)` reads the Vite dev server origin from the `hot` file on every call and delegates to an `HttpSSRGateway` with `render_path="/__inertia_ssr"`, the endpoint served by the Inertia Vite plugin. A missing or empty hot file means no SSR and unhealthy; otherwise health is the HTTP check against that origin.
- `ResponseFactory` holds `ssr_gateway`, `ssr_enabled` and `ssr_except_paths` instead of `ssr_url` and `ssr_timeout`, and passes the gateway to `InertiaResponse` only when SSR is enabled. The response renders through the gateway only for non-Inertia (initial HTML) requests whose path does not match an except pattern (`fnmatch`, so `/admin/*` matches everything below it). Any exception from the gateway, including a custom one, is logged and the page is sent without `ssr`, so the client renders it.
- Facade: `Inertia.ssr(url="http://127.0.0.1:13714", timeout=1.0, enabled=True, except_paths=())` (`url=None` disables SSR), `Inertia.ssr_hot(hot_file, timeout=1.0, enabled=True, except_paths=())`, `Inertia.ssr_gateway(gateway, enabled=True, except_paths=())`, and async `Inertia.ssr_healthy()`, which is false when SSR is off, so apps can call it from their own health route.
- `httpx` is declared in the `fastapi` extra.

## Validation

`tests/inertia/test_ssr.py` mocks the HTTP client with `httpx.MockTransport` and covers the render request (path, payload, head default), invalid payloads, non-2xx, timeouts and connection errors returning `None`, health checks, the hot-file gateway (origin read, missing or empty file, origin change between calls), except-path matching, and the response path: disabled flag, except patterns, Inertia XHR requests never contacting the gateway, a raising custom gateway falling back to client rendering, and the `page.ssr` shape. `tests/inertia/test_inertia.py` covers the factory and facade. The urllib tests in `tests/inertia/test_inertia_response.py` are replaced.
