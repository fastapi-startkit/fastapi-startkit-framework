# 069. `insert_or_ignore` and `upsert` on the query builder

Date: 2026-11-08

## Problem

An application that must keep one row per natural key under concurrency, such as one lexeme per `(slug, language)`, needs the database to settle a duplicate insert. The builder offers `insert`, `insert_get_id`, `first_or_create` and `update_or_create`. The last two select and then create, so two concurrent callers both miss the row and the second insert fails on the unique index. Applications fell back to `DB.statement('INSERT ... ON CONFLICT ... DO NOTHING')` and `DO UPDATE SET ... = EXCLUDED...`, hand-quoting columns and losing the builder.

## Alternatives

1. **Catch the unique violation in `first_or_create`.** This needs a savepoint around the insert, because a failed statement aborts the Postgres transaction. It also only covers one row and gives no update form.
2. **One `insert(values, on_conflict=...)` option.** Fewer names, but a stringly mode mixes two different statements and their arguments.
3. **`insert_or_ignore(values, unique_by=None)` and `upsert(values, unique_by, update=None)`**, as in Laravel's `insertOrIgnore()` and `upsert()`.

## Decision

Option 3.

- `QueryBuilder.insert_or_ignore(values, unique_by=None)` and `QueryBuilder.upsert(values, unique_by, update=None)` take a dict or a list of dicts and return the affected row count through a new `Connection.affecting_statement`, which `Connection.update` and `Connection.delete` now delegate to. Every value is a bound parameter. Rows are reordered to the first row's columns, so their bindings line up with the column list. Every row must have the same column set as the first row; a row with an extra or a missing column raises `ValueError` instead of silently dropping values or failing with a bare `KeyError`.
- `unique_by` and `update` take a column name or a list of names. `upsert` updates every column outside `unique_by` when `update` is `None`, falls back to `insert_or_ignore` when nothing is left to update, and raises `ValueError` without a `unique_by` column or when `update` names a column that is not inserted, since `EXCLUDED.col` and `VALUES(col)` would then overwrite it with its default. Empty values run nothing and return `0`.
- `Model.insert_or_ignore` and `Model.upsert` proxy to a new query, like `Model.insert`.
- Rendering:
  - Postgres and SQLite: `INSERT ... ON CONFLICT ("slug", "language") DO NOTHING`, or `ON CONFLICT DO NOTHING` without `unique_by`, and `ON CONFLICT (...) DO UPDATE SET "word" = EXCLUDED."word"`. SQLite needs 3.24 or later.
  - MySQL: `INSERT IGNORE INTO ...` and `... ON DUPLICATE KEY UPDATE `word` = VALUES(`word`)`. MySQL picks the conflicting unique index itself, so `unique_by` is not rendered.
  - MSSQL: both raise `NotImplementedError`. A `MERGE` translation is left for a separate change.

### Known limits

- MySQL's `INSERT IGNORE` also downgrades other errors, such as truncation, to warnings, as in Laravel.
- MySQL 8.0.20 deprecates `VALUES(col)` in `ON DUPLICATE KEY UPDATE` but still runs it; the row alias form can replace it later.
- MySQL counts an updated row as 2 affected rows, so `upsert` counts are driver specific.
- Timestamps are not filled in, as with `insert`.

## Validation

- `tests/masoniteorm/query/grammars/test_insert_or_ignore_grammar.py` snapshots the SQL and bindings on SQLite, MySQL and Postgres: with and without `unique_by`, several rows in another key order, `upsert` with default and named columns, the fallback when nothing is left to update, empty values, a missing `unique_by`, rows with extra or missing columns, and `update` columns that are not inserted. It also checks that MSSQL raises for both methods.
- `tests/masoniteorm/sqlite/builder/test_sqlite_insert_or_ignore.py`, `tests/masoniteorm/postgres/test_postgres_insert_or_ignore.py` and `tests/masoniteorm/mysql/test_mysql_insert_or_ignore.py` run against a unique `(slug, language)` index. They check that the first row is kept, that a batch inserts only its new rows, and that `upsert` inserts and then updates.
- On Postgres, a second transaction's `insert_or_ignore` waits for an open transaction that inserted the same key, then returns `0` and leaves one row. A plain `insert` fails this test with a unique violation.
- The full framework suite passes with coverage at or above the threshold.
