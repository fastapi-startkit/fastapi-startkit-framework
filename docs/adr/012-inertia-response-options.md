# ADR 012: Inertia response options: view data, root id, URL resolver, big integers, headers and per-response SSR

Date: 2026-10-10
Status: Accepted

## Problem

The Inertia response could not be adjusted beyond its props:

- The root template received only `page`, so per-page values such as a `<title>` or meta tags had to go through props, where they are sent to the client and kept in history. The `inertia()` helper always mounted on `id="app"`, so a second Inertia root or an existing layout with another id was impossible.
- `page.url` was the request path and query. Behind a reverse proxy or under a path prefix, the client then navigates to the wrong URL.
- Integers above 2^53 - 1 lose precision in JavaScript. Inertia v3 sends them as `{"$bigint": "<decimal>"}` and sets `page.preserveBigIntegers` so the client revives them as `BigInt`.
- A handler could not add headers (cache control, `Link`, custom) to an Inertia response, and could not skip SSR for a single page whose markup depends on the browser.

## Alternatives

- View data through `with_` props marked hidden: leaks template-only data to the client page object.
- `root_id` as a helper argument only (`inertia(page, "admin")`): the id must match the client's `createInertiaApp({ id })`, which is a deployment setting, so a global setting avoids repeating it in every template. The helper still reads it at call time, so it follows a runtime change.
- A URL resolver per response: the prefix is a property of the deployment, not of one page, so only a global resolver is added, as in inertia-omega.
- Encode big integers always: changes the wire format for clients that do not revive markers. Strings instead of markers: lose the numeric type, and the protocol already defines the marker.
- Add headers through a FastAPI `Response` parameter: does not reach `InertiaResponse`, which builds its own response lazily.

## Decision

Mirror inertia-omega:

- `InertiaResponse.with_view_data(key, value)` (or a dict) adds variables to the root template context next to `page`. They never reach the page object or the JSON response.
- `Inertia.root_id(id)` sets the mount element id (default `app`). The `inertia()` template helper uses it for both `data-page` and the `div` id.
- `Inertia.resolve_url_using(resolver)` sets a callable `(request) -> str` whose result becomes `page.url`. `None` restores the default, the path plus query.
- `Inertia.preserve_big_integers(enabled=True)` globally, and `InertiaResponse.preserve_big_integers(enabled=True)` per response, encode every `int` (not `bool`) outside `[-(2^53 - 1), 2^53 - 1]` in the resolved props and flash data as `{"$bigint": "<decimal>"}`. `page.preserveBigIntegers` is `true` only when enabled and is otherwise omitted.
- `InertiaResponse.with_header(name, value)` and `with_headers(dict)` set headers on the final HTML or JSON response.
- `InertiaResponse.without_ssr()` skips the SSR call for that response, so the client renders it. `_ssr_gateway_for` (ADR 011) returns no gateway when it is set, after the `X-Inertia` check and before the except-path check.

## Implementation

- `inertia/encoding.py`: `encode_big_integers` walks dicts, lists and tuples.
- `inertia/inertia.py`: `ResponseFactory` holds `root_id`, `url_resolver` and `preserve_big_integers_enabled` and passes the last two to `InertiaResponse`. The response keeps `view_data`, `extra_headers`, `ssr_allowed` and `preserve_big_integers_enabled`, builds the page with the resolver, encodes props and flash when enabled, and applies the headers to the JSON or template response. The `Inertia` facade gains `root_id`, `resolve_url_using` and `preserve_big_integers`.
- `inertia/provider.py`: the `inertia()` helper reads `Inertia.instance().root_id`.

## Validation

- `tests/inertia/test_response_options.py` uses the FastAPI `TestClient` with and without `X-Inertia`: view data in the template context and absent from the page; root id in the helper markup; resolver output in `page.url` and the default path plus query; big integer boundaries, nesting, `bool` passthrough, global and per-response switches, and the flag omitted when off; headers on HTML and JSON responses; `without_ssr` never calling the SSR server.
- `uv run pytest`, `ruff check`, `ruff format --check` and `basedpyright` on the inertia package.
