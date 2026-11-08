# 068. Quote constraint and index columns

Date: 2026-11-07

## Problem

The schema grammars quote a column in its definition (`` `key` VARCHAR(255) ``) but join the columns of a primary key, unique constraint, fulltext index or plain index as bare names. The cache package's `caches` migration declares `table.string("key").primary()`, so MySQL 8.0 compiles `CONSTRAINT caches_key_primary PRIMARY KEY (key)` and rejects it with error 1064, because `KEY` is a reserved word there. The migration therefore cannot run on MySQL, and `DatabaseStore` reads the `key` column, so renaming it is not an option.

Every grammar has the same gap. Postgres, SQLite and MSSQL accept `key`, but a column named `order`, `user` or `group` fails in their constraint and index clauses the same way. The platform tests asserted the bare names, and nothing ran a migration against MySQL, so it never showed.

## Alternatives

1. **Rename the column.** This breaks `DatabaseStore` and existing `caches` tables.
2. **Quote only MySQL's primary key.** This fixes the cache migration, but leaves every other reserved word in every other clause and grammar broken.
3. **Quote every constraint and index column with the grammar's own `wrap_column`.**

## Decision

Option 3. `Platform.wrap_columns(columns, separator)` wraps each name with the grammar's `get_column_string()`: backticks on MySQL, double quotes on Postgres and SQLite, brackets on MSSQL. Each grammar uses it for the column list of `PRIMARY KEY`, `UNIQUE`, `FULLTEXT` and `CREATE INDEX`, both in `CREATE TABLE` and in `ALTER TABLE`. Constraint and index names, and the `_`-joined names derived from columns, are unchanged, so existing migrations keep their constraint names.

The column lists that SQLite copies when it rebuilds a table are left as they are, because they do not compile constraints. Quoting them is a separate change.

## Validation

- `tests/masoniteorm/schema/platforms/test_reserved_word_columns.py` compiles a primary key, a unique constraint and an index on the reserved-word column `key`, for both create and alter, on MySQL, Postgres, SQLite and MSSQL, and asserts that the column is quoted.
- `tests/masoniteorm/mysql/test_mysql_caches_migration.py` runs the cache package's `CreateCachesTable` migration against MySQL 8.0 from `docker-compose.yml`, then writes and reads a `caches` row by `key`. MySQL 8.0's default `caching_sha2_password` authentication needs `cryptography`, which is added to the dev dependencies.
- The platform tests now expect quoted constraint and index columns.
- The full framework suite passes with coverage at or above the threshold.
