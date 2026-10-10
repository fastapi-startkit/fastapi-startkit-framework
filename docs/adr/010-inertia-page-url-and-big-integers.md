---
title: Inertia page URL resolver and big integer encoding
date: 2026-10-09
---

## Why

Behind a reverse proxy or under a path prefix, the request path the app sees is not the URL the browser uses, so `page.url` is wrong and the client navigates to the wrong place. Separately, JavaScript numbers lose precision above 2^53 - 1, so integer IDs and counters in props arrive corrupted. Inertia's protocol handles the second case with a marker object that the client revives as a `BigInt`, and it signals the choice with `page.preserveBigIntegers`.

## How

- `Inertia.url_resolver(resolver)` sets a global callable `(request) -> str`. The page's `url` uses it when set, and falls back to the path and query otherwise. It is global only, because the URL describes the deployment, not one response.
- `encode_big_integers(value)` (in `inertia/bigint.py`) walks dicts, lists and tuples and replaces every `int` outside `[-(2^53 - 1), 2^53 - 1]` with `{"$bigint": "<decimal>"}`. Other values pass through unchanged, and it runs on the resolved props, after callables are evaluated.
- Encoding is controlled by `Inertia.preserve_big_integers(enabled=True)` globally, and per response by `InertiaResponse.preserve_big_integers(enabled=True)`, which overrides the global value for that response. The page object always carries `preserveBigIntegers` as a boolean, so the client knows whether to revive markers.

## Alternatives

- Encode unconditionally: changes the wire format for every app, including clients that do not revive markers.
- Serialise big integers as strings: loses the numeric type on the client, and the protocol already defines the marker.
- Per-request URL resolver in the response: the URL prefix is a deployment fact, so a per-response option adds surface without a use case.

## Validation

`tests/inertia/test_page_options.py` covers the boundaries of the safe range, nested encoding, the global and per-response switches, the `preserveBigIntegers` field, and the URL resolver receiving the request and setting `page.url`.
