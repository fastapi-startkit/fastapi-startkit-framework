---
title: Inertia validation errors, error bags and back redirects
date: 2026-10-09
---

## Why

Forms that fail validation need to send the user back with the errors on the next page, as Laravel's `redirect()->back()->withErrors($errors, $bag)` does. Inertia's client expects `props.errors` as a flat `{field: message}` object, or as `{bag: {field: message}}` when the request names an error bag in `X-Inertia-Error-Bag`. The package already shares `errors` from the session and writes validation errors there, but it stores a flat dict with lists, has no bag support, no way to write errors from a handler or a response, and no `Inertia.back()`.

## How

- `inertia/errors.py` adds `ValidationErrors`, a `{field: [messages]}` helper with `add`, `has`, `get`, `first`, `merge` and `to_dict`. `ValidationErrors.from_validation_error(exc)` converts anything with a pydantic-style `errors()` (pydantic `ValidationError` and FastAPI's `RequestValidationError`), dropping the `body`/`query`/`path`/`header`/`cookie` location segment. There is no form-request class in this repo, so no conversion is added for one.
- Session storage is keyed by bag: `session["errors"] = {bag: {field: [messages]}}`, default bag `"default"`. `ValidationExceptionHandler` writes to the default bag, so the old flat session shape is replaced.
- Shaping for the page (`shape_error_bags`): the default bag's fields are top-level; a named bag is nested under its name. Each field becomes its first message unless `Inertia.with_all_errors(True)` is set, in which case it is the full list, matching Laravel's default `first` behaviour.
- `InertiaResponse.with_errors(errors)` and `with_errors_in(bag, errors)` add errors to the rendered page. Without an explicit bag, the bag is `X-Inertia-Error-Bag` from the request, or the default bag. Explicit bags always win over the header.
- `Inertia.back_with_errors(errors, bag=None)` stores errors in the session under the same bag rule, then returns a redirect to the `Referer` (or `/`). `Inertia.back()` is that redirect without errors. The middleware already turns 302 into 303 for PUT, PATCH and DELETE Inertia requests.
- The middleware keeps popping session errors on the next request and reflashing `_flash` on redirects.

## Alternatives

- Keep the flat session shape and add a separate session key for bags: two readers and two writers for the same data.
- Put error bags only on the response: loses the redirect flow that validation failures use.
- Expose `with_errors` as a static `Inertia` method: a static method has no response to chain onto, so it is an instance method instead.

## Validation

Tests in `fastapi_startkit/tests/inertia/test_errors.py` cover `ValidationErrors` behaviour, conversion from pydantic and `RequestValidationError` shapes, first-versus-all message shaping, header nesting, explicit bags, and back redirects with flashed errors. The exception handler tests and the middleware session test are updated to the bag-keyed session shape. The full suite and coverage threshold must pass.
