# 049. `select_raw` and `join_sub` on the query builder

- Date: 2026-10-30
- Status: Accepted

## Problem

Downstream listings need two Laravel query-builder features that the ORM lacks, so they fall back to hand-written SQL:

- **A raw select expression with bindings.** `select()` splits its argument on `,`, so an expression such as `COALESCE((SELECT s.status FROM statuses s WHERE s.lexeme_id = lexemes.id AND s.type = ?), 'pending') AS ocr` is cut into broken columns, and there is no way to pass the `?` value.
- **A join against a subquery.** `join()` only takes a table name, so `LEFT JOIN (SELECT ... GROUP BY ...) AS due ON due.lexeme_id = lexemes.id` cannot be expressed.

Both add bindings outside the `WHERE` clause. The grammar collects `_bindings` while it compiles, and the order it collects them in has to match the order of the `?` placeholders in the final SQL. `_compile_select` compiled `ORDER BY` before `GROUP BY`, which is the wrong order as soon as both carry bindings. `process_joins` built the `ON` clause before the joined table, which would be wrong once the joined table is a subquery with bindings.

`paginate()` counts with a fresh builder that copies the wheres and joins, so a subquery join has to keep its bindings there. `count()` kept the selected columns and the order by next to `COUNT(*)`, which Postgres rejects (`column "lexemes.id" must appear in the GROUP BY clause`) once columns or an order by are present.

## Alternatives

- **Accept `Raw` objects in `select()`.** `select()` would still split plain strings, and bindings would need a second channel. Rejected in favour of Laravel's explicit `selectRaw`.
- **Let callers write the subquery as a raw table name in `join()`.** The table would be quoted as an identifier and bindings would have nowhere to go. Rejected.
- **Collect bindings per clause (Laravel's `bindings['select'|'join'|'where'|...]`).** It is the most robust design, but it touches every compile path, including update and delete. The grammar already compiles in a single pass, so compiling the clauses in SQL order gives the same result with a much smaller change. Chosen for now.

## Decision

- `QueryBuilder.select_raw(expression, bindings=())` appends the expression unchanged as a raw `SelectExpression` carrying its bindings. It is never split on commas. As in Laravel, if nothing else is selected only the raw expression is selected; callers add `table.*` themselves.
- `QueryBuilder.join_sub(query, alias, column1, equality, column2, bindings=(), clause="inner")` joins `(query) AS alias ON column1 equality column2`. `query` is a `QueryBuilder`, whose own bindings are used, or a raw SQL string with `bindings`. Passing `bindings` with a builder raises `TypeError`. `left_join_sub(...)` is `join_sub(..., clause="left")`.
- `_compile_select` compiles clauses in SQL order: columns, joins, wheres, group by, having, order by. Limit and offset are inlined integers and carry no bindings.
- `process_joins` compiles the joined table (and its subquery bindings) before the `ON` clause.
- `aggregate()` (and so `count()`, `sum()`, `max()`, `min()`, `avg()`, `exists()`) compiles an ungrouped query without the selected columns and the order by, and without their bindings. It no longer leaves the aggregate on the builder. Laravel drops the columns the same way. Dropping the order by goes further than Laravel's `aggregate()` but matches its pagination count: Postgres rejects `SELECT COUNT(*) ... ORDER BY due.due_day`, and ordering cannot change an ungrouped aggregate. A query with `group_by` or `having` keeps its columns and order by, because they are the group keys and pick which group `select_one` returns; the existing `select("user_id").group_by("user_id").min("salary")` tests rely on that.

## Implementation

- `masoniteorm/expressions/expressions.py`: `SelectExpression` takes `bindings`; new `SubqueryJoinClause(JoinClause)` holds the subquery (builder or string), its alias and bindings.
- `masoniteorm/models/builder.py`: `select_raw`, `join_sub`, `left_join_sub`; `aggregate()` compiles ungrouped queries with the columns and order by cleared and restores the builder state afterwards. `paginate()` already copies `_joins`, so subquery joins and their bindings are part of the count query, and the raw select columns are not.
- `masoniteorm/query/grammars/BaseGrammar.py`: raw select bindings are added in `process_columns`; `process_joins` renders `SubqueryJoinClause` as `(<sql>) AS <alias>`, using `to_qmark()` and the builder's bindings in qmark mode and `to_sql()` otherwise; `_compile_select` compiles in SQL order.

## Validation

- Grammar tests for all four dialects: `select_raw` with bindings, `join_sub` with a builder, `left_join_sub` with raw SQL and bindings, and the combined listing query (select raw bindings, join bindings, `where_raw` bindings, `BETWEEN`, order by, limit and offset), for both `to_qmark()` with its bindings and `to_sql()`.
- Grammar tests for `count()` on an ungrouped query (columns, raw columns and order by dropped) and on a grouped query (unchanged).
- SQLite and Postgres execution tests: the combined query returns the expected rows, `count()` on a builder with `select_raw` and `join_sub`, and `paginate()` returns the right total and page.
- `uv run pytest tests/masoniteorm`, ruff and basedpyright.
