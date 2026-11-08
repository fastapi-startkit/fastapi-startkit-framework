# 050 — Has-one-of-many derived from a HasMany

- Date: 2026-10-31
- Status: Accepted (merged in #331; post-merge review fixes in a follow-up PR). The open questions below are pending a user decision.

## Problem

A model often needs "the latest/oldest row" of a has-many relation, e.g. the latest status of a user:

```python
@relationship
def due_date(self) -> HasOne["Status"]:
    return self.statuses.latest_of_many()
```

The ORM had no way to express this. `HasOne` eager-loads every child with `where_in` and `register_related` keeps the first row in undefined order, so it cannot stand in for "latest of many". There was also no method-style `@relationship` decorator: relationships are class-level descriptors, and attribute access on a descriptor (`BaseRelationship.__getattr__`) is forwarded to a fresh query builder.

## Alternatives

1. **Pick in Python** — load every child and keep the max per parent. Rejected: loads N rows to keep one and breaks `where_has`.
2. **Window function** — `id IN (SELECT id FROM (SELECT id, ROW_NUMBER() OVER (PARTITION BY fk ORDER BY col DESC, id DESC) rn FROM t) WHERE rn = 1)`. Works on SQLite ≥ 3.25, PostgreSQL and MySQL 8, but the builder has no derived-table source, so it needs hand-written SQL in `where_raw`, and without pushing the parent filter inside the window it ranks the whole table.
3. **Laravel's join to an aggregate subquery** (`JOIN (SELECT MAX(col), fk … GROUP BY fk)`, with a second aggregate on the pk for ties). Needs `join_sub` (PR #330) and two nested aggregates for the tie-break.
4. **Correlated subquery on the primary key** — `t.id = (SELECT o.id FROM t AS o WHERE o.fk = t.fk AND o.col IS NOT NULL ORDER BY o.col DESC, o.id DESC LIMIT 1)`. Chosen.

## Decision

- `HasMany.latest_of_many(column="created_at")`, `oldest_of_many(column="created_at")` and `of_many(column=None, aggregate="max"|"min")` return a new `HasOneOfMany`, a `HasOne` subclass that reuses the parent's related model and keys. `aggregate` is typed `Literal["max", "min"]`, and any other value raises `ValueError` at runtime. `column=None` means the related model's `__primary_key__`, so models with a custom primary key work.
- `HasOneOfMany` overrides only `get_builder` and `get_exists_builder`. Both add `table.pk = (correlated subquery)`. The subquery orders by the column and then by the primary key in the same direction, so ties are deterministic (`max` → latest pk wins, `min` → earliest pk wins). When the column is the primary key, it is ordered once. The inherited `HasOne` eager (`where_in`), lazy (`load`), `where_has` and `register_related` code paths then work unchanged and always see at most one row per parent.
- NULLs: the subquery adds `column IS NOT NULL`, which gives `MAX`/`MIN` semantics on every database (NULLs are ignored), instead of each database's own NULL sort position. Without it, PostgreSQL's `DESC` and SQLite/MySQL's `ASC` would put NULL rows first. A parent whose children all have a NULL column gets `None`.
- `HasOneOfMany` runs `HasOne.__init__`, so `_model_name` and `fn` are set the usual way, and `related_model()` resolves through the parent relation. It raises `TypeError` when the parent `HasMany` has neither an explicit `foreign_key` nor an attribute name to derive one from, instead of silently using `None_id`.
- `relationship` (in `relationships/RelationshipMethod.py`, still exported as `fastapi_startkit.masoniteorm.relationship` and `fastapi_startkit.masoniteorm.relationships.relationship`) is a decorator that returns a `RelationshipMethod` descriptor. The implementation moved out of `relationship.py` because the exported function shadowed that module and its name was close to `models/relationship.py`. `relationships/relationship.py` stays as a re-export so the v0.71.0 import path `fastapi_startkit.masoniteorm.relationships.relationship` keeps working, and the package imports through it so the package attribute stays bound to the function. On first access from an owner class, the decorator calls the decorated function with the **class** as its argument, so `self.statuses` is the class-level `HasMany` descriptor, not a loaded collection. The result must be a new, unnamed `BaseRelationship`. Returning an existing descriptor (`return self.statuses`) or a builder raises `TypeError`, because naming it would rename the shared descriptor. The relation is named after the method and cached per owner class, so subclasses resolve their own. Instance access goes through the relation's normal `access` (loaded value or `LazyLoadingViolation`). Both the plain-function form and `@relationship @classmethod` are supported.
- Typing: `relationship(fn: Callable[[Any], R]) -> R`, so the method's return annotation decides the type. `User.due_date` is `HasOne[Status]` and `user.due_date` is `Status | None`.

## Caveats

- MySQL rejects writes through the relation, e.g. `User.due_date.where(...).update()` / `.delete()`, with error 1093 (the target table appears in a subquery). Reads are fine. Write through the `HasMany` or the related model instead.
- A relationship method named `latest` or `oldest` overrides `Model.latest()`/`Model.oldest()` (basedpyright `reportIncompatibleMethodOverride`). Pick another name.
- `where_column` emits unquoted identifiers (pre-existing behaviour), and now every of-many query uses it, so mixed-case table names on PostgreSQL would break.
- Global scopes on the related model also run on the correlated subquery's builder. Scopes that hard-code the table name instead of using the builder's alias are not handled.
- `@classmethod @relationship` (reversed order) is not supported.
- Performance relies on an index on `(fk, column, pk)`.

## Open questions (pending user decision)

- Canonical form: basedpyright reports `self.statuses.latest_of_many()` as an error, because instance access types `statuses` as `Collection[Status]`. The `@relationship @classmethod def due_date(cls)` form type-checks cleanly. Both forms are kept until the user chooses.
- Default column: `latest_of_many`/`oldest_of_many` keep `created_at`, matching `Model.latest()`/`oldest()`. Laravel defaults to the key.
- Eager callbacks (`with_({"due_date": cb})`) and `where_has` callbacks filter the selected row ("the latest status, if it is done"), not the candidate set. Laravel's `ofMany(..., closure)` inner constraints are not implemented.

## Validation

`tests/masoniteorm/sqlite/relationships/test_has_one_of_many.py` covers:
- latest, oldest and `of_many` max/min with pk tie-breaks
- parents without children (`None`)
- eager loading in one query (counted through `Connection.select`)
- lazy `load` on a model and on a collection
- `where_has` with and without a callback
- the classmethod form and an unchanged `HasMany`
- rejection of unknown aggregates, existing descriptors, builders and unresolvable foreign keys
- `related_model()` and the v0.71.0 import path
- NULL columns ignored for latest and oldest
- the `of_many()` default on a custom primary key, ordered once
- a subclass of the owner
- a self-referencing table, eager and `where_has`

SQL snapshots are in `tests/masoniteorm/mysql/builder/test_mysql_has_one_of_many_sql.py` and `tests/masoniteorm/postgres/grammar/test_postgres_has_one_of_many_sql.py`. Neither needs a live server. The full suite (excluding Postgres), basedpyright and ruff all pass.
