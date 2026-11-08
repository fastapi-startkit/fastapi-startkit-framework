# 072. `insert_or_ignore` and `upsert` on MySQL

Date: 2026-11-08

## Problem

ADR 069 adds `insert_or_ignore` and `upsert` to the query builder and renders them with `ON CONFLICT` on Postgres and SQLite. MySQL has no `ON CONFLICT`, so its grammar raises `NotImplementedError` for both methods, and an application on MySQL still writes the statement by hand.

## Alternatives

1. **Keep raising on MySQL.** Applications on MySQL keep hand-written SQL.
2. **Select, then insert or update.** Two concurrent callers both miss the row, which is the race ADR 069 removes.
3. **MySQL's own forms, `INSERT IGNORE` and `ON DUPLICATE KEY UPDATE`**, as Laravel compiles them.

## Decision

Option 3.

- `MySQLGrammar.compile_insert_or_ignore` renders `INSERT IGNORE INTO ...`.
- `MySQLGrammar.compile_upsert` renders `INSERT INTO ... ON DUPLICATE KEY UPDATE `word` = VALUES(`word`)` for each update column.
- MySQL picks the conflicting unique index itself, so `unique_by` is not rendered. `upsert` still needs it, to choose the default update columns.

### Known limits

- MySQL's `INSERT IGNORE` also downgrades other errors, such as truncation, to warnings, as in Laravel.
- MySQL 8.0.20 deprecates `VALUES(col)` in `ON DUPLICATE KEY UPDATE` but still runs it; the row alias form can replace it later.
- MySQL counts an updated row as 2 affected rows, so `upsert` counts are driver specific.

## Validation

- `tests/masoniteorm/mysql/test_mysql_insert_or_ignore.py` runs against MySQL 8.0 from `docker-compose.yml` with a unique `(slug, language)` index. It checks that `insert_or_ignore` keeps the first row for a key and that `upsert` inserts and then updates the named columns.
- The full framework suite passes with coverage at or above the threshold.
