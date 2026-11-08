# 059. Subqueries in `where_in`/`where_not_in`, `where_not_exists` and `add_select_exists`

Date: 2026-10-31

## Problem

Dashboard queries filter on membership in another query (`WHERE user_id IN (SELECT ...)`), exclude rows that have related records (`WHERE NOT EXISTS (...)`) and return a per-row flag (`SELECT ..., EXISTS (...) AS has_orders`). The builder could not express any of these:

- `where_in(column, values)` and `where_not_in(column, values)` call `list(values)`, so a builder raises `TypeError: 'QueryBuilder' object is not iterable`. `where(column, "IN", builder)` is rejected because `IN` is not an accepted operator.
- `where_exists` and `or_where_exists` exist, but there is no negated form. Every grammar already defines `where_not_exists_string()` and `process_wheres` already handles a `NOT EXISTS` equality; no builder method creates one.
- A boolean `EXISTS` column needs `select_raw` with hand-compiled SQL, which loses the subquery's bindings and global scopes.

Applications fell back to `DB.select` with hand-written SQL and lost model hydration, scopes, eager loading and pagination.

## Alternatives

1. **Raw SQL with `where_raw`/`select_raw`.** Works today, but the caller has to compile the inner builder, copy its bindings in the right position and quote identifiers per grammar.
2. **New methods `where_in_sub`/`where_not_in_sub`.** Explicit, but Laravel's `whereIn` accepts a builder or a closure, and callers would have to know two names for one clause.
3. **Let `where_in`/`where_not_in` accept a subquery, add `where_not_exists`/`or_where_not_exists` and `add_select_exists(alias, query)`,** reusing `SubSelectExpression` for wheres and `SubGroupExpression` for the selection, the way `where(column, op, builder)` and `select_sub` already do.

## Decision

Option 3.

- A *subquery* is a `QueryBuilder`, or a callable that receives a fresh table-less builder and returns one, as for `select_sub`. A shared `_resolve_subquery(subquery, method)` resolves it for every method and raises `TypeError("<method>() expects a QueryBuilder subquery or a callable returning one.")` otherwise.
- `where_in(column, values)` and `where_not_in(column, values)` render `column IN (subquery)` / `column NOT IN (subquery)` when `values` is a builder or a callable. Iterables (lists, tuples, generators, `Collection`) behave as before.
- `where_exists` and `or_where_exists` also accept a callable. `where_not_exists(query)` and `or_where_not_exists(query)` render `NOT EXISTS (subquery)` joined with `AND`/`OR`.
- `add_select_exists(alias, query)` appends `EXISTS(subquery) AS alias` to the selection and, like `add_select`/`add_select_raw`, first selects `{table}.*` (or `{alias}.*` for an aliased table) when nothing is selected, so the model's columns survive. `SubGroupExpression` gains an `exists` flag, and `process_columns` wraps the subquery with the grammar's new `select_exists_string()`. SQL Server does not allow a bare predicate in a select list, so `MSSQLGrammar` renders `CASE WHEN EXISTS(subquery) THEN 1 ELSE 0 END`.
- `Model` proxies `where_not_exists`, `or_where_not_exists` and `add_select_exists`, and the existing `where_in`, `where_not_in`, `where_exists` and `or_where_exists` proxies take the wider types.

Each subquery is compiled with `to_qmark()` when the outer query compiles, so later changes to the inner builder still apply and its values stay bound parameters. `_compile_select` already evaluates clauses in SQL order, so an `EXISTS` column's bindings come with the selection, before joins, and a where subquery's bindings sit at its position among the wheres, before `GROUP BY`, `HAVING`, `ORDER BY` and pagination. `paginate()` needs no change: its count copies the wheres, and copies the selection only when it wraps a grouped query.

### Known limits

- **`EXISTS` column types differ.** Postgres returns `True`/`False`; SQLite, MySQL and SQL Server return `1`/`0`. Both are truthy as expected; declare the attribute or cast it when a strict `bool` matters.
- **`NOT IN` with a `NULL` in the subquery matches nothing**, per SQL three-valued logic. Use `where_not_exists` with a correlated subquery, or filter `NULL`s out of the subquery.
- The subquery must select one column for `IN`; the builder does not check this, and the database reports the error.

## Validation

- `tests/masoniteorm/query/grammars/test_subquery_where_grammar.py` snapshots `to_qmark()` and the bindings on SQLite, MySQL, Postgres and MSSQL for `where_in`/`where_not_in` with a builder and a callable, `where_not_exists`/`or_where_not_exists`, `add_select_exists`, the binding order when all of them are combined with `select_raw`, a join, wheres, `group_by`, `having_raw`, `order_by` and limit/offset, and the `TypeError` for a non-builder.
- `tests/masoniteorm/sqlite/builder/test_sqlite_subquery_where.py` runs the same shapes on SQLite through `Model`, including a correlated `where_not_exists` and `add_select_exists`, a bound value that is never interpolated, `paginate()` and eager loading.
- A throwaway Postgres container runs the same queries to check `IN (subquery)`, `NOT EXISTS` and the boolean `EXISTS` column with asyncpg parameters.
- The full framework suite passes with coverage at or above the threshold.
