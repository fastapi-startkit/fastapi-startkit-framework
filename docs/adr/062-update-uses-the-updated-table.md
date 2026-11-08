# 062. `update()` compiles against the updated table

Date: 2026-11-01

## Problem

`QueryBuilder.update()` built its grammar with `self.grammar()`, so the grammar kept its default table, `users`. MySQL and MSSQL prefix every `SET` and `WHERE` column with the grammar table, so an update of any other table rendered against `users`: `UPDATE [queues] SET [users].[status] = ? WHERE [users].[id] = ?`. The statement fails, or on MySQL updates the wrong columns when a `users` table is joined. Postgres and SQLite do not prefix update columns and were unaffected. The existing MySQL test only covered the `users` table, so it never showed.

## Alternatives

1. **Build the grammar through `get_grammar()`.** It passes the whole builder state, including limit, order and lock, which `_compile_update` does not use. That is a larger change than the bug needs.
2. **Pass the table to the grammar: `self.grammar(table=self._table)`.**

## Decision

Option 2. `update()` builds its grammar with `table=self._table`, so the column prefix matches the `UPDATE` target. Nothing else changes: `update()` still returns the row count.

A claim on a work queue does not need `UPDATE ... RETURNING`. It reads the matching rows with a lock inside a transaction, iterates them and updates each by key, so the caller already knows which rows it claimed.

## Validation

- `tests/masoniteorm/query/grammars/test_update_table_grammar.py` snapshots an update of the `queues` table on SQLite, MySQL, Postgres and MSSQL, with a plain where and with a `where_in` subquery, and checks the bindings.
- The full framework suite passes with coverage at or above the threshold.
