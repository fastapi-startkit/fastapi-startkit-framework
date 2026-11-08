# 070. JSON path columns in the query builder

Date: 2026-11-08

## Problem

The builder has no way to filter on a key inside a JSON column. `where("settings->>headline", "like", pattern)` is quoted as one identifier, `"posts"."settings->>headline"`, and Postgres rejects it with `UndefinedColumnError`. Apps that search a JSON key fall back to `where_raw("settings->>'headline' ILIKE ?", ...)`, which repeats dialect SQL in app code and keeps raw fragments in their query layer.

## Alternatives

1. **Keep `where_raw`.** It works, but every app writes dialect SQL by hand, and none of it is portable between Postgres and SQLite test databases.
2. **A dedicated `where_json_path(column, path, operator, value)`.** This adds a method per clause (`or_where_json_path`, `order_by_json_path`, selects), and duplicates the operator handling of `where`.
3. **Laravel's arrow syntax in column names.** `where("settings->headline", ...)` compiles `settings->headline` as a JSON path wherever a column is compiled, so `where`, `or_where`, `order_by` and selects all get it, with values still bound.

## Decision

Option 3. `BaseGrammar._table_column_string` splits a column on `->`: the first part is compiled as the usual table-qualified column, and the remaining keys go to the grammar's `json_path_string(column, keys)`:

| Grammar | `settings->meta->headline` |
|---|---|
| Postgres | `"posts"."settings"->'meta'->>'headline'` |
| SQLite | `json_extract("posts"."settings", '$."meta"."headline"')` |
| MySQL | ``json_unquote(json_extract(`posts`.`settings`, '$."meta"."headline"'))`` |
| MSSQL | `json_value([posts].[settings], '$."meta"."headline"')` |

Every dialect returns the value as text, so comparisons and `like` behave the same on each. On Postgres, `like` still compiles to `ILIKE`. The alias and separator follow the expression. Order-by columns that contain `->` compile through the same path instead of being quoted bare.

Keys are written into the SQL text, so a key that is not letters, digits or underscores raises `ValueError`. Values are never interpolated; they stay bindings.

Array indexes (`tags->0`) and JSON containment (`where_json_contains`) are out of scope.

## Validation

- `tests/masoniteorm/query/grammars/test_json_path_where_grammar.py` checks the compiled expression on all four grammars, the table prefix, the alias and separator, key validation, the bound values of `where` and `or_where`, and `order_by`.
- `tests/masoniteorm/sqlite/builder/test_sqlite_json_path_where.py` runs `where`, nested keys, `or_where` and a quote-bearing value against SQLite.
- `tests/masoniteorm/postgres/test_postgres_json_path_where.py` runs case-insensitive `like`, nested keys, `or_where` and `order_by` against a `jsonb` column.
- The full framework suite passes.
