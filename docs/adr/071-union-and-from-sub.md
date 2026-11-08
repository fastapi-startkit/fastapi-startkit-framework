# 071. `union`, `union_all` and `from_sub` on the query builder

Date: 2026-11-08

## Problem

The builder cannot combine rows from several tables or select from a derived table. A report that counts distinct users per day across `review_logs`, `plays` and `conversation_messages` needs `SELECT day, COUNT(DISTINCT user_id) FROM (... UNION ALL ...) AS events GROUP BY day`. The distinct has to run over the combined rows, because one user can appear in more than one table on the same day, so it cannot be split into one grouped query per table. Without `union` or a subquery source, apps write the whole statement with `DB.select`, or run one `count()` with `or_where_exists` per day and skill, which is hundreds of queries for a 90-day range.

## Alternatives

1. **Keep `DB.select`.** Apps keep full SQL, with positional bindings counted by hand, and the statement is not portable between Postgres and the SQLite test databases.
2. **A `from_raw(sql, bindings)` source.** It removes the derived table but keeps the union as SQL text.
3. **Laravel's `union`, `unionAll` and `fromSub`.** Each takes a builder, so every member and the derived table are compiled by the grammar, bindings included.

## Decision

Option 3.

- `union(query)` and `union_all(query)` append a `("UNION" | "UNION ALL", builder)` pair to `_unions`. `from_sub(subquery, alias)` stores the builder in `_from_sub` and sets the alias. All three take a builder or a callable that receives a fresh builder, through `_resolve_subquery`, as `select_sub` and `where_in` do, and raise the same `TypeError` for anything else. `Model` proxies all three.
- `get_grammar()` passes `from_sub` and `unions` to the grammar.
- `process_from_table(qmark)` renders `(<subquery>) AS <alias>` when `from_sub` is set. Columns, `where`, `group_by` and `order_by` on the outer query are prefixed with the alias, as for `table(name, alias)`. A builder with only a `from_sub` and no table still compiles a `FROM` clause.
- After the select is compiled, `process_unions(qmark)` wraps the base query and every member with the grammar's `union_member_string()` and joins them with `UNION` or `UNION ALL`:

| Grammar | member |
|---|---|
| Postgres, MySQL | `(<query>)` |
| SQLite | `SELECT * FROM (<query>)` |
| MSSQL | `SELECT * FROM (<query>) AS [temp_table]` |

  SQLite rejects a parenthesised compound member and MSSQL needs a derived-table alias, which is how Laravel compiles them too. Each member keeps its own `order_by` and `limit`.
- Bindings follow SQL order: outer columns, the `from_sub` subquery, the outer joins, wheres and having, then each union member in turn.
- `count()` and the other aggregates on a builder with unions run over `from_sub(<the union>, "aggregate_table")`, so they count the union's rows, not the base query's. `paginate()` counts the same way, and a paginated `from_sub` keeps its subquery in the count.

Out of scope: an `order_by` or `limit` over the whole union (wrap it in `from_sub` and order the outer query), `GROUPING SETS`, and `INTERSECT`/`EXCEPT`. `group_by` on the outer query prefixes the alias, so a computed column such as a local day is selected inside each member, where it becomes a real column of the subquery.

## Validation

- `tests/masoniteorm/query/grammars/test_union_from_sub_grammar.py` checks `union`, `union_all`, `from_sub`, a `from_sub` over a union with bound fragments in the members and the outer query, callables, `to_sql()` and the `TypeError` on all four grammars, with bindings in SQL order.
- `tests/masoniteorm/sqlite/builder/test_sqlite_union_from_sub.py` runs `union_all` and `union` rows, `count()` over a union, distinct users per day over `from_sub(union_all)`, bound fragments, `paginate()` over a `from_sub` and the `Model` proxies against SQLite.
- `tests/masoniteorm/postgres/test_postgres_union_from_sub.py` counts distinct users per local day across two tables with a bound `AT TIME ZONE` fragment in each member.
- The full framework suite passes.
