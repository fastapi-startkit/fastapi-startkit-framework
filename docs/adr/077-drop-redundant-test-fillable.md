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
