# 026. Observer stub matches model lifecycle events

- Date: 2026-10-21
- Status: Accepted

## Problem

`observer.stub`, rendered by `MakeObserverCommand`, imports `Model` from `masoniteorm.models`, a package that is not installed with the framework, so any generated observer that is imported fails with `ModuleNotFoundError`. It stubs `booted`, `booting`, `hydrating` and `hydrated`, which the model never dispatches, and every method carries a Google-style docstring, which the coding standards forbid. ADR 025 defined the events that are dispatched (`saving`, `creating`, `updating`, `created`, `updated`, `saved`, `deleting`, `deleted`) and awaits async handlers.

## Alternatives

1. **Fix only the import.** Smallest change, but users keep getting handlers that never fire, plus the docstrings.
2. **Import the generated model class for the type hint.** More precise typing, but the model module and its path are not known to the command, and the observer would fail to import when the model does not exist yet.
3. **Import `Model` from `fastapi_startkit.masoniteorm.models` and stub exactly the dispatched events as async methods.** Always importable, and the handlers match what fires.

## Decision

Option 3. The stub imports `Model` from `fastapi_startkit.masoniteorm.models` and defines `async def <event>(self, <model>: Model) -> None` for the eight lifecycle events in dispatch order. It has no docstrings or comments. Handlers are async because the ORM is async-first and `observe_events` awaits them, so a handler can query the database. Sync handlers still work for users who prefer them.

## Implementation

- `masoniteorm/commands/stubs/observer.stub` is rewritten; `MakeObserverCommand` is unchanged.
- `model.stub` has the same outdated `masoniteorm.models` import and is left for a separate change.

## Validation

- `tests/masoniteorm/commands/test_make_commands.py` checks the import line, the async typed signature, and that the file has no docstrings or comments. It also loads the generated file with `importlib`, asserts that its handlers are exactly the eight events in order, and dispatches each event through `observe_events` on a `Model` subclass.
- In a project created with `uvx fastapi-startkit init`, running the command against the local build generated `app/observers/OrderObserver.py`, and it imported and handled all eight events.
