# 025. Model lifecycle events, automatic timestamps and datetime casts

- Date: 2026-10-20
- Status: Accepted

## Problem

`Model.save()` fired only `saving`, `created`, `updated` and `saved`. Observers that defined `creating`, `updating` or `deleting` were never called, so an observer that set a column in `creating()` had no effect. The model also had no instance `delete()`: `user.delete()` went through `__getattr__` to `get_attribute("delete")` and returned `None`. So neither `deleting` nor `deleted` could fire.

`observe_events` called each handler synchronously and swallowed every `AttributeError`. An `async def` observer method returned an un-awaited coroutine, and an `AttributeError` raised inside a handler was silently dropped.

Related timestamp and cast defects:

1. `DateCast.set` returned a formatted string. asyncpg rejects strings for `timestamp`/`timestamptz` parameters, so writing any datetime column on Postgres failed with `DataError`. Returning an aware datetime instead is not enough on its own: asyncpg's default `timestamp` (without time zone) encoder rejects aware values, while its `timestamptz` encoder reads naive values as client-local time.
2. Automatic timestamps never ran. `CreatedAtObserver`/`UpdatedAtObserver` listened to `creating`/`updating`, which never fired, and `UpdatedAtObserver.updating` wrote to `model.builder._updates`, an API the model no longer has. `updated_at` never moved on update. `created_at` was only set when the column had a database default.
3. `Caster.build_casts` called `get_type_hints` without `include_extras`, so `Annotated[Carbon, MyCast]` lost its metadata and a column could not override its inherited cast. `Attribute.__casts__` was declared but never read.
4. `Caster.casts` had no annotation, so type checkers inferred it from the first assignment.

## Alternatives

Event dispatch:

1. **Fire the events in the existing sync `observe_events`.** Smallest diff, but async observers still never run.
2. **Make `observe_events` async and await awaitable results.** All call sites are already inside async model methods. Sync and async handlers both work.
3. **Use a separate dispatcher or event bus.** More moving parts than the observer API needs.

Built-in timestamp observers:

- **A. Laravel-style auto timestamps.** `creating` fills `created_at`/`updated_at` when they are not supplied. `updating` moves `updated_at` unless the caller changed it. `__timestamps__ = False` disables both.
- **B. Keep the built-in observers inert.** This avoids a behaviour change, but it leaves `updated_at` frozen and `created_at` dependent on a column default, which is the reported bug.

Datetime binding:

- **Return a string from `DateCast.set` and let Postgres parse it.** asyncpg does not do this for untyped parameters.
- **Return a datetime from `DateCast.set` and convert per driver where needed.** aiomysql accepts aware datetimes. asyncpg accepts them for `timestamptz` but not for `timestamp`. sqlite3 (Python 3.12+ has no default datetime adapter) needs a string.
- **Bind naive UTC datetimes everywhere.** This fixes `timestamp`, but asyncpg treats a naive value bound to `timestamptz` as client-local time, so the stored instant shifts whenever the client time zone is not UTC.
- **Register an asyncpg codec for `timestamp` only.** Its encoder converts aware values to naive UTC and passes naive values through. `timestamptz` keeps asyncpg's own codec.

## Decision

Option 2 with A, plus datetime binding converted per driver.

Events:

- Order on insert: `saving` → `creating` → INSERT → `created` → `saved`.
- Order on update: `saving` → `updating` → UPDATE → `updated` → `saved`. `updating` fires only when the model is dirty, and the dirty set is computed after it, so observer changes are written.
- `Model.delete()`: returns `False` for a model that was never saved. Otherwise it runs `deleting` → DELETE by primary key → `deleted` and marks the model as not existing.
- `observe_events` is async. It skips observers without the handler and awaits awaitable results. Exceptions raised inside a handler now propagate.

Timestamps:

- `CreatedAtObserver.creating` sets `created_at` to `pendulum.now(tz)` when the attribute is `None`. A supplied value is kept.
- `UpdatedAtObserver.creating` does the same for `updated_at`. `UpdatedAtObserver.updating` sets `updated_at` unless it is already dirty.
- Both skip models with `__timestamps__ = False`. Values go through the normal attribute setter, so they are cast and tracked as dirty.

Casts and binding:

- `DateCast.set` returns a `pendulum.DateTime` in UTC. A value that does not parse to a datetime raises `ValueError`.
- `Connection.prepare_binding(value)` is applied to every parameter in `sql_alchemy_bindings`. The base implementation returns the value unchanged, so Postgres and MySQL receive the datetime.
- `PostgresConnection` listens to the engine `connect` event and registers a `pg_catalog.timestamp` codec in asyncpg's `tuple` format (microseconds since 2000-01-01). The encoder converts aware values to naive UTC and passes naive values through. The decoder returns a naive datetime, as asyncpg did. `datetime.max`/`datetime.min` map to `infinity`/`-infinity`, as in asyncpg. `timestamptz` is untouched, so aware values keep their instant and naive values keep asyncpg's default behaviour.
- `SQLiteConnection.prepare_binding` turns a datetime into a naive UTC `YYYY-MM-DD HH:MM:SS[.ffffff]` string and a date into ISO format. `DateCast.get` reads it back as the same instant.
- `build_casts` uses `get_type_hints(model, include_extras=True)`. For `Annotated[T, ...]`, the first metadata item that is a `BaseCast` subclass or instance becomes the column's cast. Other metadata, including duck-typed objects with `get` and `set`, is ignored and the cast is derived from `T` as before.
- `Attribute.__casts__` is removed. `Caster.casts` is annotated `dict[str, Any]`.

## Query-builder paths

- `QueryBuilder.create`, `first_or_create` and `update_or_create` go through `Model.save()`/`Model.update()`, so they fire the full event sequence and get timestamps.
- `QueryBuilder.update(values)`, `QueryBuilder.delete()` and `insert()` run mass SQL without loading models, so they fire no model events and set no timestamps. This matches Laravel. They are unchanged.

## Downstream changes

- Models with the default `__timestamps__ = True` now write `created_at` and `updated_at`. Models on tables without those columns must set `__timestamps__ = False`.
- `DateCast.set` returns a UTC datetime instead of a formatted string. Code that compared the cast result or dirty values to a string must compare to a datetime.

## Validation

- `tests/masoniteorm/sqlite/models/test_observers.py` asserts the exact event order for insert, update, a clean save (no `updating`) and delete. It also checks that changes made in `creating`/`updating` are persisted, that `deleting` runs while the row still exists, that `delete()` on an unsaved model does nothing, that `without_events()` silences observers, and that async observer methods are awaited.
- The same file checks automatic timestamps on a table with no column defaults: both are set on create, a supplied `created_at` with an offset and microseconds is kept, update moves `updated_at` and keeps `created_at`, and `__timestamps__ = False` writes neither. A SQLite binding test writes a `-04:00` datetime and reads back the naive UTC string and the same instant.
- `tests/masoniteorm/postgres/models/test_model.py` stores a supplied `created_at` exactly and checks that update and `touch()` move `updated_at`. Both fail with the old string cast. It also writes aware (`-04:00`) and naive inputs to a `timestamp` column (`email_verified_at`) and a `timestamptz` column (`created_at`) and reads back the same instant through raw SQL and the model, binds raw parameters to `timestamp`/`timestamptz` casts, and round-trips `infinity`. The `timestamp` writes fail with `DataError` without the codec.
- `tests/masoniteorm/models/test_caster.py` covers `Annotated` with a cast class, a cast instance, and non-cast metadata, including duck-typed objects.
- The test fixtures add `timestamps()` to `articles` and `stores`. Four existing tests change only their asserted contract (datetime instead of string, `updated_at` now written).
- The full suite runs on SQLite, MySQL and Postgres, and the `database-app` and `agents` examples run unchanged.
