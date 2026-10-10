# ADR 010: Inertia page errors as an always prop

Date: 2026-10-10
Status: Accepted

## Problem

`errors` was a lazy shared prop that read and cleared the flashed validation errors from the session on every resolution. A partial reload that did not request `errors` never resolved it, so the errors were not cleared there. A partial reload that did request `errors` (or any reload that resolved it first) consumed them, so the page lost its errors on the next request.

## Alternatives

- Keep `errors` lazy and read the flash without popping. The errors would then survive reloads, but a full visit would never clear them after the user had moved on.
- Keep a sticky per-page copy of the errors in the session. A successful resubmit with a partial reload still showed the old errors, and a partial reload for a different component could receive them.
- Make `errors` an always prop that consumes only the flashed errors, and return an empty value on partial reloads that bring no new errors. The client keeps its own form errors, as Laravel does.

## Decision

`share()` returns `Inertia.always(...)` for `errors`, so it is included on every response. The value is the flashed errors pulled from the session, shaped by `with_all_errors` and the `X-Inertia-Error-Bag` header. A partial reload with no newly flashed errors returns `{}`. A partial reload whose `X-Inertia-Partial-Component` names a different component than the one being rendered returns `{}` and leaves the flash in the session for the page it was meant for.

To make the second rule possible, `InertiaResponse.to_response` records the rendered component on the per-request state (`InertiaRequestState.component`) before resolving props.

## Implementation

- `inertia/middleware.py`: `share()` wraps the errors resolver in `Inertia.always`. `is_partial_for_other_component` compares the partial header with the rendered component.
- `inertia/inertia.py`: `to_response` stores the component on the request state.
- `inertia/context.py`: `InertiaRequestState.component`.
- `inertia/session.py`: unchanged `pull_error_bags`; no sticky store.
- Tests in `tests/inertia/test_inertia_session_features.py`:
  - a partial reload without new errors returns `{}`;
  - a successful partial resubmit clears previous errors;
  - a partial reload for another component does not consume the flash, and a later full visit still shows it;
  - a full visit after a redirect shows errors, and a full visit without new errors clears them.

## Validation

- `uv run pytest --ignore=tests/masoniteorm/postgres`.
- `ruff check`, `ruff format --check` and `basedpyright` on the inertia package.
