---
title: Inertia preserve_fragment across the next redirect
date: 2026-10-09
---

## Why

After a redirect, the Inertia client normally drops the URL fragment (`#section`), so a form that redirects back to its page loses the user's place on the page. Inertia v3 lets the server ask the client to keep the fragment by setting `preserveFragment` on the page object. Omega exposes this as a flag the handler sets before redirecting. This package has no way to set it.

## How

- `Inertia.preserve_fragment()` queues the flag in the request session under `preserveFragment`, for the next page render. It returns nothing, so a handler calls it and then returns its redirect, as with `back_with_errors`.
- `InertiaResponse.to_response` pulls the flag from the session (`pop`), so it reaches exactly one page, and emits `preserveFragment` as a boolean on every page object, with `false` when nothing was queued. The client only reads the flag on the page it receives.
- The flag is set on the request that redirects, and consumed on the first rendered page afterwards, so it survives the redirect through the session cookie.
- With no session, `preserve_fragment()` emits `InertiaSessionWarning` and the flag is dropped (see ADR 008).

## Alternatives

- Put the flag on the redirect response as a header: Inertia reads the page object, not a response header, for this behaviour.
- Put the flag in `_flash`: `_flash` is reflashed on every redirect and is not consumed by the page render, so it would persist across redirects.

## Validation

`tests/inertia/test_preserve_fragment.py` covers: the flag set on a redirecting request appears as `preserveFragment: true` on the next page, is gone on the page after that, is `false` by default, and emits the no-session warning when no session is present.
