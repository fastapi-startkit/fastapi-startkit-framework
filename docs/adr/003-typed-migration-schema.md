---
title: Typed Migration.schema and Blueprint column methods
date: 2026-10-06
---

## Why

`Migration.__init__(self, connection=None, schema=None)` left `self.schema` inferred as `None`, so `async with await self.schema.create("x") as table:` in a user migration raised `reportOptionalMemberAccess` / `reportUnknownMemberType` under basedpyright. `Schema.create`/`table` already returned `Blueprint`, but the Blueprint column methods had unannotated `column`/`length`/`nullable` parameters, so every `table.string(...)` call stayed partially unknown in strict mode.

## How

- `Migration` declares `connection: str` and `schema: Schema` at class level; the constructor is unchanged, so the `Migrator` still injects both at runtime.
- Public `Blueprint` methods annotate their parameters (`column: str`, `length: int`, `nullable: bool`, `index: str | list[str]`, ...).
- `Column.name` is declared `str` so `unique`/`index`/`primary`/`fulltext` narrow cleanly; the loop variable in `morphs` was renamed to stop shadowing the typed `column` parameter.
- Annotating `foreign_uuid(column: str)` exposed `foreign_id_for` passing the possibly-`None` `column` instead of the resolved `clm`; it now passes `clm`, matching the integer-key branch.
- `Schema.drop(table: str)` is annotated as returning `Coroutine[Any, Any, None]` (it stays a plain method delegating to `drop_table`, so runtime is unchanged); it was `*args, **kwargs`, which left `await self.schema.drop(...)` in the `make:migration` stub unknown. `get_all_tables` returns `list[Any]`.
- `test_blueprint.py` gains `foreign_id_for` regression tests for int/uuid primary keys with explicit and implicit column names.
- The `database-app` example `create_users.down` now awaits `schema.drop("users")` (it was a sync, un-awaited call on the wrong table, surfaced by the new types).

## Verification

basedpyright (strict) on a sample migration using `create`, `increments`, `string`, `integer`, `timestamps` reports 0 errors, as do `masoniteorm/schema` and `masoniteorm/migrations`; the pytest suite passes; `db:migrate` and `db:migrate:rollback` run against sqlite in `example/database-app`.
