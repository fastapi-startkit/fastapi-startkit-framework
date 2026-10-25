# 039. Default relationship keys and working database scaffolding

Date: 2026-10-25

## Problem

Four defects stop a fresh application from getting past its first model.

1. **Default relationship keys.** A relationship declared without keys, such as `HasMany("Media")`, `BelongsTo("Post")` or `BelongsToMany["Tag"]()`, only filled its keys in `set_keys`, and `set_keys` ran only on instance access. Eager loading (`with_`), `where_has` and `attach` all reach the relationship through the class (`getattr(Model, name)`), so they saw `None` keys. The results were `TypeError: attribute name must be string` and `no such column posts.None`. The defaults were also wrong where they existed:
   - `HasOne`/`HasMany` used `{attribute}_id` instead of the owner's foreign key, and `HasOne` defaulted `local_key` to `"id"` even when `__primary_key__` was custom.
   - Foreign keys and pivot names came from the singularized table name, so `Media` became `medium_id` and `__table__ = "blog_tags"` became `blog_tag_id`.
   - A relationship declared on a base model kept the base class as its owner, so a subclass inferred `base_item_id`.
   - `BelongsTo` defaulted `local_key` to `"id"`.
   - `BelongsToMany` assigned pivot keys in alphabetical table order, which swapped them for `Post → Tag`.
   - `HasOneThrough` defaulted every key to `"id"`, and its select alias overwrote the distant model's `id`.
2. **Published database config.** The `database` stub set `default="pgsql"` but defined only a `sqlite` connection, so the first query raised `ValueError: Connection 'pgsql' not found`.
3. **Generators.** `db:make:model` defaulted to `app/`, not `app/models/`, and created the parent of its target directory instead of the directory itself. `db:make:migration` and the `seed` generator never created their directories either. As a result, `db:make:model Post -m` failed with `FileNotFoundError` in a new application.
4. **Migrating a fresh application.** Running `db:migrate` right after `provider:publish --provider=database` failed with `unable to open database file`, because `databases/` did not exist. Once that directory existed, it failed again with `FileNotFoundError`, because `databases/migrations` did not exist either.

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
    - A model's foreign key is `snake(ClassName)_pk`, like Laravel's `getForeignKey()`. It is taken from the class name, so neither `__table__` nor singularization affects it (`Media` gives `media_id`).
    - `HasOne`/`HasMany`: the owner's primary key, and the owner's foreign key on the related model.
    - `BelongsTo`: `{attribute}_{related_pk}`, and the related primary key.
    - `BelongsToMany`: the pivot table is the two snake class names sorted and joined with `_` (`media_tag`). The keys are each side's foreign key and each side's primary key.
    - `HasOneThrough`: the owner pk, the owner's foreign key on the intermediate model, the intermediate pk, and the intermediate's foreign key on the distant model.
  - Inferred keys are cached separately from explicit ones. Reading a relationship through a subclass returns a copy bound to that subclass and cached on the descriptor. The copy keeps the explicit keys and infers the rest from the subclass, matching Laravel, where `$this` is the concrete model.
  - The table-based `BelongsToMany.get_pivot_table_name` fallback is removed, because `_table` is always inferred.
  - The four duplicated alphabetical pivot blocks in `BelongsToMany` are removed.
  - `HasOneThrough` selects its join key as the fixed alias `m_through_key`.
- **Config.**
  - `default` is now `env("DB_CONNECTION", "sqlite")`.
  - The stub defines `sqlite`, `mysql` and `postgres`, the values the installer writes.
- **Generators.**
  - `db:make:model` defaults to `app/models` and creates that directory.
  - `db:make:migration` and `seed` create their target directories.
  - `-m` already calls `db:make:migration`, and the model stub already imports `fastapi_startkit.masoniteorm.models`. Both stay as they are.
- **Fresh migrate.**
  - `SQliteConnection` creates the parent directory of a file database. In-memory and `file:` URIs are skipped.
  - `Migrator.migration_files()` returns an empty list when the migrations directory is missing, so `db:migrate` creates the tracking table and reports nothing to migrate. Laravel behaves the same way.
- **Out of scope.** `HasManyThrough` default keys and the `m_through_key` alias are follow-ups.

## Validation

- `tests/masoniteorm/sqlite/relationships/test_default_relationship_keys.py` declares every relationship type with no keys, in both generic and string form. It checks:
  - the inferred keys on class access;
  - class-name keys for `Media`, for a custom `__table__` and for the `BelongsToMany` pivot;
  - a custom `__primary_key__` on `HasOne`, `HasMany` and `BelongsTo`;
  - an inherited relationship binding to the subclass;
  - eager loads in both directions;
  - `HasOneThrough` loading and missing rows;
  - `where_has` with and without callbacks.
- The database config tests check that the default resolves to a defined connection, and that each `DB_CONNECTION` value selects one.
- The make-command tests no longer pre-create directories. They also import a generated model through the package.
- A sqlite connection to a file in a missing directory runs a query and creates the file. A `Migrator` with a missing migrations directory migrates nothing and leaves only the tracking table.
- In a fresh temporary application, `provider:publish --provider=database` followed by `db:migrate` reports nothing to migrate and creates `databases/sqlite.db`.
- In a temporary application, publishing the config, then running `db:make:model Post -m` and `db:migrate`, creates `app/models/Post.py` and the migration, and migrates on sqlite.
