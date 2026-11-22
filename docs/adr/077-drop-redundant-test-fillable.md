# 077. Drop redundant `__fillable__` from typed test models

- Date: 2026-11-09
- Status: Accepted

## Problem

Three test models (`Article` in `tests/masoniteorm/sqlite/builder/test_sqlite_json_path_where.py`, `VecDocument` in `tests/masoniteorm/postgres/test_postgres_vector.py`, `PjArticle` in `tests/masoniteorm/postgres/test_postgres_json_path_where.py`) set `__fillable__ = [...]` next to typed field annotations. `Model.__init_subclass__` always replaces `cls.__fillable__` with the names of the declared annotations and field descriptors, so those lines never take effect. They suggest that `__fillable__` is still a hand-maintained list, which it is not.

## Alternatives

- **Keep the lines.** Harmless at runtime, but misleading to readers who copy test models as examples.
- **Make `__init_subclass__` respect an explicit `__fillable__`.** A framework behaviour change outside the scope of a test clean-up.
- **Delete the dead assignments.** (chosen)

## Decision

Remove the `__fillable__` assignment from each of the three models. The fillable list keeps coming from the annotations, so behaviour is unchanged.

## Implementation

A search of `fastapi_startkit/tests/` and `example/` found no other model that assigns `__fillable__` (`application/` does not exist on `main`). The remaining references are assertions in `tests/masoniteorm/models/test_model.py` and `tests/masoniteorm/models/test_model_attributes.py` that check the derived list; they stay.

## Validation

Run the affected SQLite and Postgres test files, the model tests that assert the derived list, and `ruff check` on the changed files.

## 2026-11-21: `fill()` no longer filters by `__fillable__`

### Problem

`Model.fill()` dropped every key that was not in the derived `__fillable__`. Because that list only holds annotated and descriptor fields, `model.update(...)` and `Model.update_or_create(...)` silently skipped real table columns that a model never declared (for example `title` on a model that annotates only `published_date`, or every column on a model with no annotations). `Model.create(...)` writes every key, so inserts and updates disagreed.

### Alternatives

- **Respect an explicit `__fillable__` / `__guarded__` declared in the class body.** Restores Masonite's opt-in guard, but adds a new mass-assignment API and makes the derived list behave differently depending on how a model was written.
- **Keep filtering and require every column to be annotated.** Keeps the silent data loss for untyped models.
- **Assign every key in `fill()`.** (chosen)

### Decision

`fill()` sets every given attribute. This matches Masonite ORM's default (`__fillable__ = ["*"]`, `__guarded__ = []`) and what `create()` already does. The derived `__fillable__` stays as the list of declared fields for typing and introspection; it is no longer a write filter. Input should be validated before it reaches the model (for example through a `FormRequest`).

### Consequences

- **Class-body `__fillable__` is still discarded.** `Model.__init_subclass__` overwrites any `__fillable__` written in the class body with the derived list. This predates this change and is not fixed here; whether an explicit `__fillable__` / `__guarded__` should act as a write guard is a follow-up pending the user's decision.
- **Behaviour change for typed models.** On a typed model, `update()` and `update_or_create()` now persist keys that are not annotated on the model. Before, those keys were silently dropped. Callers that relied on the derived list to strip unknown input must now filter that input themselves.
- **Related, from the same change set: `Decimal` on SQLite.** The SQLite connection binds `Decimal` values as text. A `DECIMAL` column has NUMERIC affinity, so stored values and column comparisons stay numeric, but comparisons without column affinity (for example `where_raw` arithmetic on a bound parameter) compare as TEXT. SQLite NUMERIC storage keeps no precision or scale: values become INTEGER or REAL, so digits beyond double precision are lost and trailing zeros are not preserved.

### Validation

`tests/masoniteorm/sqlite/models/test_sqlite_model_update_undeclared_columns.py` covers `update()` on a partly annotated model, on a model with no annotations, and `update_or_create()` on an existing row.
