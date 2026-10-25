# 039. Default relationship keys and working database scaffolding

Date: 2026-10-25

## Problem

Three defects stop a fresh application from getting past its first model.

1. **Default relationship keys.** A relationship declared without keys, such as `HasMany("Media")`, `BelongsTo("Post")` or `BelongsToMany["Tag"]()`, only filled its keys in `set_keys`, and `set_keys` ran only on instance access. Eager loading (`with_`), `where_has` and `attach` all reach the relationship through the class (`getattr(Model, name)`), so they saw `None` keys. The results were `TypeError: attribute name must be string` and `no such column posts.None`. The defaults were also wrong where they existed:
   - `HasOne`/`HasMany` used `{attribute}_id` instead of the owner's foreign key.
   - `BelongsTo` defaulted `local_key` to `"id"`.
   - `BelongsToMany` assigned pivot keys in alphabetical table order, which swapped them for `Post → Tag`.
   - `HasOneThrough` defaulted every key to `"id"`, and its select alias overwrote the distant model's `id`.
2. **Published database config.** The `database` stub set `default="pgsql"` but defined only a `sqlite` connection, so the first query raised `ValueError: Connection 'pgsql' not found`.
3. **Generators.** `db:make:model` defaulted to `app/`, not `app/models/`, and created the parent of its target directory instead of the directory itself. `db:make:migration` and the `seed` generator never created their directories either. As a result, `db:make:model Post -m` failed with `FileNotFoundError` in a new application.

## Alternatives

For the keys:

1. Infer keys inside `access` when the owner is `None`. This is not possible. `Model.__init__` reads class attributes while building casts, so inferring there instantiates models while they are being constructed and recurses.
2. Infer keys eagerly in `__set_name__`. This is also not possible: string targets and later-declared classes are not resolvable yet.
3. Make the keys lazy data descriptors that infer on first read.

For the config, either keep `pgsql` and add a Postgres connection, or read `DB_CONNECTION` and define every connection the installer can write.

## Decision

- **Keys.** I chose alternative 3, `RelationshipKey`.
  - Each key is a data descriptor on the relationship class. On first read, after `__set_name__` has set `owner_class`, it fills every unset key from `default_keys()`.
  - Explicit keys always win.
  - The defaults follow Laravel:
    - `HasOne`/`HasMany`: the owner's primary key, and `singular(owner_table)_pk` on the related model.
    - `BelongsTo`: `{attribute}_{related_pk}`, and the related primary key.
    - `BelongsToMany`: the pivot table is the two singular table names sorted and joined with `_`; the keys are each side's foreign key and each side's primary key.
    - `HasOneThrough`: the owner pk, `singular(owner_table)_pk` on the intermediate model, the intermediate pk, and `singular(intermediate_table)_pk` on the distant model.
  - Table names come from `__table__` or `tableize(class_name)`, so no model is instantiated.
  - The four duplicated alphabetical pivot blocks in `BelongsToMany` are removed.
  - `HasOneThrough` selects its join key as the fixed alias `m_through_key`.
- **Config.**
  - `default` is now `env("DB_CONNECTION", "sqlite")`.
  - The stub defines `sqlite`, `mysql` and `postgres`, the values the installer writes.
- **Generators.**
  - `db:make:model` defaults to `app/models` and creates that directory.
  - `db:make:migration` and `seed` create their target directories.
  - `-m` already calls `db:make:migration`, and the model stub already imports `fastapi_startkit.masoniteorm.models`. Both stay as they are.

## Validation

- `tests/masoniteorm/sqlite/relationships/test_default_relationship_keys.py` declares every relationship type with no keys, in both generic and string form. It checks:
  - the inferred keys on class access;
  - eager loads in both directions;
  - `HasOneThrough` loading and missing rows;
  - `where_has` with and without callbacks.
- The database config tests check that the default resolves to a defined connection, and that each `DB_CONNECTION` value selects one.
- The make-command tests no longer pre-create directories. They also import a generated model through the package.
- In a temporary application, publishing the config, then running `db:make:model Post -m` and `db:migrate`, creates `app/models/Post.py` and the migration, and migrates on sqlite.
