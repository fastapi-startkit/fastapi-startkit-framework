# 058. Common table expressions (`with_query`) and a subquery source (`from_sub`)

Date: 2026-10-31

## Problem

Dashboard queries that rank, deduplicate or pre-aggregate rows need either a `WITH name AS (...)` clause or a `FROM (subquery) AS alias` source. The query builder had neither: `table()` only takes a table name, and subqueries could only appear in the selection (`select_sub`), in a where (`where_exists`, `where(col, op, builder)`) or in an `ORDER BY`. Applications fell back to `DB.select` with hand-written SQL and lost model hydration, eager loading and pagination.

## Alternatives

1. **Raw SQL in `table()`** (`table("(SELECT ...) AS t")`). `process_table` quotes the string piece by piece, and a raw string cannot carry bindings.
2. **Name the CTE method `with_`**, as Laravel's `withExpression` package does not, but the name is taken: `with_` eager-loads relations.
3. **`with_query(name, query)` and `from_sub(query, alias)`** taking a builder, or a callable that receives a fresh builder, like `select_sub`. Both compile the inner builder with `to_qmark()` and add its bindings in SQL order.

## Decision

Option 3.

- `QueryBuilder.with_query(name, query)` appends a CTE. Several calls render `WITH "a" AS (...), "b" AS (...)` in call order. The name is quoted like a table, so the outer query reads it with `table(name)`, `join(name, ...)` or a where subquery.
- `QueryBuilder.from_sub(query, alias)` replaces the `FROM` source with `(query) AS "alias"` and sets the builder alias, so columns, wheres, joins, `add_select_raw` and the default `{alias}.*` resolve against the derived table. On a model query the rows still hydrate as the model.
- Both reuse `SubGroupExpression(builder, alias)`, and `select_sub`, `with_query` and `from_sub` share one subquery resolver, so a non-builder argument raises the same `TypeError`.
- The grammar takes `ctes` and `from_sub`. `_compile_select` compiles the CTEs before the select, so their bindings come first, then the selection, then the derived table, then joins, wheres, `GROUP BY`, `HAVING` and `ORDER BY`, matching the SQL on every grammar. Values are bound, never interpolated.
- `paginate()` copies the CTEs and the subquery source into its count query, in both the plain and the grouped count.
- `Model.with_query` and `Model.from_sub` proxy to a new query, like `Model.select_raw`.

All four grammars emit the same syntax. SQLite (3.8.3+), Postgres, MySQL 8+/MariaDB 10.2+ and SQL Server support it, so there is no grammar to reject. A server too old for CTEs reports its own syntax error, since the grammar cannot see the server version.

### Known limits

- **No recursive CTEs.** `WITH RECURSIVE` needs a `UNION` between an anchor and a recursive member, and the builder has no `union`. Adding a `recursive` flag without it would only serve raw SQL, so it waits for a union API.
- **Selects only.** `update()` and `delete()` ignore CTEs and the subquery source.
- **Global scopes run on the outer query.** A scope column such as `deleted_at` is prefixed with the `from_sub` alias, so the subquery must select it, or the query calls `without_global_scopes()`.
- **SQL Server** rejects `ORDER BY` inside a CTE or derived table without `TOP`/`OFFSET`, and rejects a CTE nested inside a subquery.

## Validation

- `tests/masoniteorm/query/grammars/test_cte_from_sub_grammar.py` snapshots `to_qmark()` and the bindings on SQLite, MySQL, Postgres and MSSQL for a CTE, several CTEs, `from_sub`, a CTE read through `from_sub`, and both combined with `select_raw`, joins, wheres, `group_by`, `having_raw`, `order_by` and limits, plus the `TypeError` for a non-builder.
- `tests/masoniteorm/sqlite/builder/test_sqlite_cte_from_sub.py` runs on SQLite: a CTE joined to a model table, a CTE read with `table()`, a CTE read inside a `where_exists` subquery, `from_sub` with aggregates, `paginate` over both, the `Model` proxies and eager loading on rows from a derived table.
- A throwaway `postgres` docker container runs the same live queries on asyncpg.
- The full framework suite passes with coverage at or above the threshold.
