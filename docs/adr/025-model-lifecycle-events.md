# 025. Fire creating, updating, deleting and deleted model events

- Date: 2026-10-20
- Status: Accepted

## Problem

`Model.save()` fired only `saving`, `created`, `updated` and `saved`. Observers that defined `creating`, `updating` or `deleting` were never called, so an observer that set a column in `creating()` had no effect. The model also had no instance `delete()`: `user.delete()` went through `__getattr__` to `get_attribute("delete")` and returned `None`. So neither `deleting` nor `deleted` could fire.

`observe_events` called each handler synchronously and swallowed every `AttributeError`. An `async def` observer method returned an un-awaited coroutine, and an `AttributeError` raised inside a handler was silently dropped.

## Alternatives

1. **Fire the events in the existing sync `observe_events`.** Smallest diff, but async observers still never run.
2. **Make `observe_events` async and await awaitable results.** All call sites are already inside async model methods. Sync and async handlers both work.
3. **Use a separate dispatcher or event bus.** More moving parts than the observer API needs.

For the built-in timestamp observers (see below):

- **A. Laravel-style auto timestamps.** `CreatedAtObserver.creating` and `UpdatedAtObserver.updating` write `created_at`/`updated_at` on every model with the default `__timestamps__ = True`. **Rejected for now; follow-up.** It changes behaviour for downstream apps whose tables have no timestamp columns. 33 existing tests fail on tables such as `articles` and `stores`, and on the `touch()` test that expects `updated_at` to be `None` after create. It also depends on `DateCast.set`, which returns a string that asyncpg rejects for `timestamp` parameters. That cast has to be fixed first.
- **B. Keep the built-in timestamp observers inert.** Chosen.

## Decision

Option 2 with B.

- Order on insert: `saving` → `creating` → INSERT → `created` → `saved`.
- Order on update: `saving` → `updating` → UPDATE → `updated` → `saved`. `updating` fires only when the model is dirty, and the dirty set is computed after it, so observer changes are written.
- `Model.delete()`: returns `False` for a model that was never saved. Otherwise it runs `deleting` → DELETE by primary key → `deleted` and marks the model as not existing.
- `observe_events` is async. It skips observers without the handler and awaits awaitable results. Exceptions raised inside a handler now propagate.

`CreatedAtObserver` and `UpdatedAtObserver` are still registered by `CreatedAtField`/`UpdatedAtField`, but they no longer define `creating`/`updating`. They were dead code: before this change those events never fired. `UpdatedAtObserver.updating` also appended to `model.builder._updates`, an API the model no longer has, so it would have raised once called. With no handlers, both observers stay inert explicitly instead of relying on events that never fire.

## Query-builder paths

- `QueryBuilder.create`, `first_or_create` and `update_or_create` go through `Model.save()`/`Model.update()`, so they fire the full event sequence.
- `QueryBuilder.update(values)`, `QueryBuilder.delete()` and `insert()` run mass SQL without loading models, so they fire no model events. This matches Laravel, where mass updates and deletes skip model events. They are unchanged.

## Validation

- `tests/masoniteorm/sqlite/models/test_observers.py` asserts the exact event order for insert, update, a clean save (no `updating`) and delete. It also checks that changes made in `creating`/`updating` are persisted, and that `deleting` runs while the row still exists.
- The same file checks that `delete()` on an unsaved model does nothing, that `without_events()` silences observers, and that async observer methods are awaited.
- A regression test creates and updates a default-timestamps model on the `articles` table, which has no timestamp columns. `created_at`/`updated_at` stay `None`.
- The existing suite passes with no changes to existing tests or fixtures.
