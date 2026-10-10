# ADR 010: Inertia page errors as an always prop

Date: 2026-10-10
Status: Accepted

## Problem

`errors` was a lazy shared prop that read and cleared the flashed validation errors from the session on every resolution. A partial reload that did not request `errors` never resolved it, so the errors were not cleared there. A partial reload that did request `errors` (or any reload that resolved it first) consumed them, so the page lost its errors on the next request.

## Alternatives

- Keep `errors` lazy and read the flash without popping. The errors would then survive reloads, but a full visit would never clear them after the user had moved on.
- Store errors in the page props on the client. This moves state out of the server and breaks the redirect-based flow.
- Make `errors` an always prop that reads from a session key holding the page's errors. Partial reloads keep the key, and full visits replace or clear it.

## Decision

`share()` returns `Inertia.always(...)` for `errors`. Flashed errors are copied into `_inertia_page_errors` (`session.PAGE_ERRORS`) the first time they are seen. On a full visit with no new flash the key is cleared. On a partial reload the key is kept and returned without being popped. `with_all_errors` and the `X-Inertia-Error-Bag` header still shape the value per request.

## Implementation

- `inertia/session.py`: `PAGE_ERRORS` and `page_error_bags(request, *, partial)`.
- `inertia/middleware.py`: `share()` wraps the errors resolver in `Inertia.always`. `resolve_validation_errors` passes whether the request is a partial reload.
- Tests: `tests/inertia/test_inertia_session_features.py` covers a partial reload that does not request `errors` and a full visit without new errors. The middleware test reads the wrapped prop through `.value()`.

## Validation

- `uv run pytest --ignore=tests/masoniteorm/postgres` (2752 passed).
- `ruff check`, `ruff format --check` and `basedpyright` on the inertia package.
