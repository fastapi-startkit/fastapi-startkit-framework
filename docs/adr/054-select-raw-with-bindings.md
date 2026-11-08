# 054. `select_raw` and `add_select_raw` with bound parameters

Date: 2026-10-31

## Problem

The query builder could not express a grouped or aggregate selection such as `SELECT site_id, count(*) AS opens, sum(pages) AS pages ... GROUP BY site_id`. `select()` splits its argument on commas and wraps every piece as a quoted column, so `select("count(*) as total")` renders `"users"."count(*)" AS total`. `SelectExpression` already had a `raw` flag and `process_columns` already emitted raw expressions verbatim, inherited from Masonite ORM, but no builder method created one and a raw column could not carry bindings. Applications fell back to `DB.select` and lost model hydration, scopes, eager loading and pagination.

Three related gaps block the same queries:

- `having()` prefixes its column with the table (`HAVING "users"."total" > '1'`) and inlines its value, so it cannot filter on an aggregate or an alias and cannot bind a value.
- `_compile_select` collected bindings while evaluating the format arguments in the order `columns, table, joins, wheres, ..., order_by, group_by, having`. Bindings from `ORDER BY` were therefore placed before those from `GROUP BY` and `HAVING`, although the SQL renders them after.
- `paginate()` counted with a fresh builder that copied only the wheres and joins. With `GROUP BY` the total was the number of rows, not the number of groups.

## Alternatives

1. **Accept raw SQL in `select()`.** Detecting expressions by parsing column strings is fragile, and a column list cannot carry bindings.
2. **A `Raw` expression object passed to `select()`/`add_select()`.** `expressions.Raw` exists but has no bindings, and every grammar method that touches columns would need to recognise it. Laravel users expect `selectRaw`.
3. **`select_raw(expression, bindings)` and `add_select_raw(expression, bindings)` that append a raw `SelectExpression` with its own bindings**, plus `having_raw(expression, bindings)`, binding order fixed in `_compile_select`, and a grouped count in `paginate()`.

## Decision

Option 3.

- `SelectExpression` takes `bindings`. `process_columns` emits a raw expression verbatim and adds its bindings, in column order, before every other clause.
- `QueryBuilder.select_raw(expression, bindings=())` appends the expression to the selection, like `select()` (which also appends). `add_select_raw(expression, bindings=())` first selects `{table}.*` when nothing is selected, as `add_select()` does for subqueries, so the model's columns survive. Bindings must be a list or tuple, else `ValueError`, matching `where_raw`.
- `QueryBuilder.having_raw(expression, bindings=())` appends a raw `HavingExpression`. Several `having` entries are joined with `AND` inside one `having_string()` instead of repeating `HAVING`, so the per-dialect `having_equality_string()` hook (identical in every grammar) is removed. `having()` keeps its current rendering.
- `_compile_select` evaluates its clauses in SQL order (`columns, table, joins, wheres, group_by, having, order_by, limit, offset, lock`), so positional bindings line up on every grammar. MSSQL renders `TOP n` before the columns, but it carries no binding.
- `paginate()` counts groups when the query has `GROUP BY` or `HAVING`: it compiles a copy of the query without ordering, limit and offset and runs `SELECT COUNT(*) AS aggregate FROM (<query>) AS aggregate_table` with the copy's bindings. Without grouping the existing count is unchanged.
- `Model.select_raw`, `Model.add_select_raw` and `Model.having_raw` proxy to a new query, like `Model.select`.

Raw expressions use `?` placeholders on every grammar. The connection rewrites each `?` to a named SQLAlchemy parameter, which the driver renders in its own style (`$n` for asyncpg, `%s` for aiomysql, `?` for aiosqlite). Values are never interpolated into the SQL. A literal `?` in a raw expression (for example the Postgres `jsonb ?` operator) is still read as a placeholder, as it already is for `where_raw`.

Aliased columns hydrate like any other: `Model.hydrate` stores every returned key as an attribute, so `row.total` reads the aggregate.

`add_select_raw`, `add_select({alias: subquery})` and the pagination count respect a table alias set with `table(name, alias)`: the default selection is `{alias}.*` and the count query keeps the alias, so wheres and groups written against the alias still resolve.

### Known limits

- **`?::type` on Postgres.** `Connection.sql_alchemy_bindings` rewrites each `?` to `:pN`, so `?::text` becomes `:p0::text`, which SQLAlchemy does not read as a parameter, and asyncpg raises a syntax error. This predates this ADR and affects `where_raw` the same way. Write `CAST(? AS text)` instead.
- **Grouped pagination wraps the query in a derived table.** Every selected column becomes a derived-table column, so MSSQL rejects an unnamed expression (`COUNT(*)` without `AS`), and MySQL rejects duplicate column names, for example `*` over a join where both tables have an `id`. Name every expression and select explicit columns. Laravel's `getCountForPagination` has the same limits.
- **`having()` still inlines its value** (`HAVING "users"."id" > '1'`) and puts the table name in front of its column. Binding it would change the SQL that existing callers and tests get, so it is left as a follow-up. Use `having_raw` for aggregates, aliases and user input.

## Validation

- `tests/masoniteorm/query/grammars/test_select_raw_grammar.py` snapshots `to_qmark()` and the bindings on SQLite, MySQL, Postgres and MSSQL for `select_raw`, `add_select_raw`, raw bindings combined with joins, wheres, `group_by_raw`, `having_raw` and `order_by`, and the bindings validation.
- `tests/masoniteorm/sqlite/builder/test_sqlite_select_raw.py` runs on SQLite: `group_by` with `count`/`sum` aggregates and a bound parameter, `having_raw`, a join, an eager load on grouped rows, `paginate` and `simple_paginate` over grouped rows, and the `Model` class methods.
- The full framework suite passes with coverage at or above the threshold.
