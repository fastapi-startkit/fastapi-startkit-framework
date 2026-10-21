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
| MSSQL | `ALTER COLUMN ... DEFAULT` is not valid T-SQL. Out of scope here. |

## Alternatives

1. Make Postgres change only the attributes that were explicitly called. This needs per-modifier tracking on `Column` and would behave differently from MySQL, where `MODIFY` always replaces the full definition.
2. Treat `.change()` as a full redefinition on every platform, the way Laravel does: the column ends up exactly as declared, and any modifier left out (nullable, default) is reset.
3. Introspect the current column and merge. This adds a database round trip and a lot of complexity.

## Decision

Option 2. Postgres now emits, for each changed column, in one `ALTER TABLE` statement:

- `ALTER COLUMN c TYPE t USING c::t`, where the length comes from `create_column_length`, so integer and text types get no length
- `ALTER COLUMN c SET NOT NULL` or `DROP NOT NULL`
- `ALTER COLUMN c SET DEFAULT v`, with defaults rendered like `CREATE` (quoted strings, raw defaults, `current`/`now`/`null` mappings), or `DROP DEFAULT` when no default is declared
- for enums, `DROP CONSTRAINT IF EXISTS {table}_{column}_check, ADD CONSTRAINT {table}_{column}_check CHECK(...)`. Postgres auto-names the inline check from `CREATE` with this same name.

MySQL and SQLite are unchanged. SQLite always applies `.change()` by rebuilding the table.

## Implementation

- `PostgresPlatform.change_column_clauses` and `PostgresPlatform.change_default`, plus a new `modify_column_string`.
- `PRIMARY KEY` is no longer emitted for changed columns on Postgres; primary keys are managed with constraints.

## Validation

- Platform SQL tests for Postgres (length, nullable, default quoting, premapped defaults, no-length types, enum checks) and MySQL (length, nullable, default).
- SQLite integration test against a real database: changing type, nullable and default keeps the existing rows and the untouched columns.
- Existing schema tests and adding columns without `.change()` are unaffected.
