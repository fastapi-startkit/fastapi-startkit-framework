# ADR 026: Altering existing columns with `.change()`

- Date: 2026-10-20
- Status: Accepted

## Problem

Migrations need to change an existing column's type, length, nullability and default:

```python
async with await schema.table("users") as table:
    table.string("name", 100).nullable().change()
    table.integer("age").default(0).change()
```

`Blueprint.change()` already moves the column from `added_columns` to `TableDiff.changed_columns`, and every platform compiles `changed_columns`. An audit of the generated SQL found:

| Platform | Result |
|---|---|
| MySQL | `MODIFY` redefines the full column (type, length, null, quoted default). Correct. |
| SQLite | Rebuilds the table (temp copy, drop, create with the new definition, copy rows back). Correct. |
| Postgres | Broken: string defaults unquoted (`SET DEFAULT x`), types without a length rendered `TEXT(None)`, an omitted default never dropped, no `USING` cast so incompatible conversions (`varchar` → `integer`) failed, and enum `CHECK` and `PRIMARY KEY` inlined into `ALTER COLUMN ... TYPE`, which Postgres rejects. |
| MSSQL | Broken: `ALTER COLUMN ... DEFAULT` is not valid T-SQL, several columns were joined after a single `ALTER COLUMN` (T-SQL allows one per statement), and an existing default constraint blocks type changes. |

## Alternatives

1. Make Postgres change only the attributes that were explicitly called. This needs per-modifier tracking on `Column` and would behave differently from MySQL, where `MODIFY` always replaces the full definition.
2. Treat `.change()` as a full redefinition on every platform, the way Laravel does: the column ends up exactly as declared, and any modifier left out (nullable, default) is reset.
3. Introspect the current column and merge. This adds a database round trip and a lot of complexity.

## Decision

Option 2. Postgres now emits, for each changed column, in one `ALTER TABLE` statement:

- `ALTER COLUMN c TYPE t USING c::t`, where the length comes from `create_column_length`, so integer and text types get no length
- `ALTER COLUMN c SET NOT NULL` or `DROP NOT NULL`
- `ALTER COLUMN c SET DEFAULT v`, with defaults rendered like `CREATE` (quoted strings, raw defaults, `current`/`now`/`null` mappings), or `DROP DEFAULT` when no default is declared
- for enums, `DROP CONSTRAINT IF EXISTS "{table}_{column}_check", ADD CONSTRAINT "{table}_{column}_check" CHECK(...)`. Postgres auto-names the inline check from `CREATE` with this same name. The name is double-quoted with embedded `"` doubled.

MSSQL emits separate statements for each changed column:

1. Drop the current default constraint, whatever its name. Its name is looked up in `sys.default_constraints` joined to `sys.columns` and dropped through `sp_executesql`. This always runs, because a bound default blocks `ALTER COLUMN`, and an omitted default must be removed. The dynamic `ALTER TABLE` target is built server-side from `QUOTENAME(OBJECT_SCHEMA_NAME(...)) + '.' + QUOTENAME(OBJECT_NAME(...))`, so the table name is never inlined into the dynamic string; the lookup passes `OBJECT_ID(N'[table]')` as an escaped string literal.
2. `ALTER TABLE [t] ALTER COLUMN [c] type(length) NULL|NOT NULL`
3. `ALTER TABLE [t] ADD CONSTRAINT [DF_<table>_<column>] DEFAULT v FOR [c]`, only when a default is declared

MSSQL identifiers in these statements are bracketed with `]` escaped as `]]`, so names containing quotes, hyphens, spaces or dots are safe.

MySQL and SQLite are unchanged. SQLite always applies `.change()` by rebuilding the table.

## Implementation

- `PostgresPlatform.change_column_clauses` and `PostgresPlatform.change_default`, plus a new `modify_column_string`.
- `MSSQLPlatform.change_column_statements`, `MSSQLPlatform.drop_default_constraint_string` and `MSSQLPlatform.change_default`. The default rendering is duplicated from Postgres instead of moved to `Platform`, to keep the change small. Enum check constraints are not rewritten on MSSQL, because inline checks there have generated names.
- `PRIMARY KEY` is no longer emitted for changed columns on Postgres or MSSQL; primary keys are managed with constraints.

## Consequences

- Because `.change()` is a full redefinition, a Postgres `serial`/`bigserial` column that is changed without a default loses its `nextval(...)` default (`DROP DEFAULT`), and new inserts no longer get generated ids. Changing an auto-increment column requires redeclaring the default explicitly, e.g. a raw `nextval('<table>_<column>_seq')` default, or leaving the column out of `.change()`. MSSQL identity columns are unaffected, since identity is not a default constraint.

## Validation

- Platform SQL tests for Postgres (length, nullable, default quoting, premapped defaults, no-length types, enum checks), MySQL (length, nullable, default) and MSSQL (drop default lookup, one `ALTER COLUMN` per column, `DF_` default constraints), plus identifier escaping for table names with a quote, hyphen, space, dot and `]`.
- Live Postgres integration test: `varchar` → `integer` cast keeps the rows, an omitted default is dropped, and the enum check is replaced.
- SQLite integration test against a real database: changing type, nullable and default keeps the existing rows and the untouched columns.
- Existing schema tests and adding columns without `.change()` are unaffected.
