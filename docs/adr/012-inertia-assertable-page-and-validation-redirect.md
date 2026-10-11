# ADR 012: Inertia AssertablePage test helpers and validation redirects

Date: 2026-10-10
Status: Accepted

## Problem

Tests of Inertia endpoints decode the page by hand. The initial visit embeds the page in `<script data-page="app" type="application/json">` and an `X-Inertia` visit returns it as JSON, so every test repeats parsing and dictionary digging, and failures read as bare `KeyError`s or `assert False`.

`ValidationExceptionHandler` picks JSON when the request sends `Content-Type: application/json`. The Inertia client posts JSON with `X-Inertia: true`, so an Inertia form that fails validation receives a 422 the client cannot show as page errors. It also writes the legacy `errors` session key and ignores `X-Inertia-Error-Bag`.

## Alternatives

- Helpers as free functions (`assert_component(response, "Users/Index")`). Each call reparses the response and chaining is impossible.
- A fluent `AssertablePage` built once from a response, like Laravel's `assertInertia`. Chosen.
- For validation, a separate Inertia exception handler registered by `InertiaProvider`. It would duplicate the error flattening and rely on provider order to override the FastAPI provider.
- Detect `X-Inertia` inside the existing `ValidationExceptionHandler` and flash through the Inertia session helpers. Chosen.

## Decision

`fastapi_startkit.inertia.testing` gains `AssertablePage` and `assert_inertia(response)`. The page is read from JSON when the response has `X-Inertia: true` or a JSON content type, otherwise from the `data-page` script tag, or from a `data-page` attribute for custom root templates. The assertions are `component`, `url`, `version`, `has`, `has_count`, `missing`, `equals`, `deferred(group, props)` and `flash(key, value)`. `has`, `has_count`, `missing` and `equals` take dot paths into `props`, with numeric segments indexing lists. Each returns the page for chaining and raises `AssertionError` naming the path and the actual value.

For `X-Inertia` requests `ValidationExceptionHandler` returns a 303 to the same-origin referer (or `/`) and flashes the errors into the bag named by `X-Inertia-Error-Bag`, or `default`. A named bag is stored under its own name, so the page receives `{bag: {...}}` whether or not the follow-up request repeats the header. Other requests keep the 422 JSON or legacy redirect behaviour.

## Implementation

- `inertia/session.py`: `put_errors(request, errors, bag)` holds the bag merge; `with_errors` calls it with the active request, so the exception handler does not depend on the middleware context.
- `fastapi/exceptions.py`: `ValidationExceptionHandler.render` branches on `X-Inertia` before content negotiation and returns an `InertiaRedirect` with status 303.
- `inertia/testing.py`: `AssertablePage`, `assert_inertia`.
- Tests: `tests/inertia/test_assertable_page.py` covers HTML and JSON responses, every assertion and their failure messages; `tests/inertia/test_validation_redirect.py` posts with `X-Inertia`, follows the redirect and checks `props.errors`, including a named error bag, the root fallback, and the unchanged 422 for JSON clients.

## Validation

- `uv run pytest` from `fastapi_startkit/`.
- `ruff check`, `ruff format --check` and `basedpyright`.
