# 050 — Has-one-of-many derived from a HasMany (POC)

- Date: 2026-10-31
- Status: Proposed (proof of concept, draft PR)

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
4. **Correlated subquery on the primary key** — `t.id = (SELECT o.id FROM t AS o WHERE o.fk = t.fk ORDER BY o.col DESC, o.id DESC LIMIT 1)`. Chosen.

## Decision

- `HasMany.latest_of_many(column="created_at")`, `oldest_of_many(column="created_at")` and `of_many(column="id", aggregate="max"|"min")` return a new `HasOneOfMany`, a `HasOne` subclass that reuses the parent's related model and keys. Any other aggregate raises `ValueError`.
- `HasOneOfMany` overrides only `get_builder` and `get_exists_builder`. Both add `table.pk = (correlated subquery)`. The subquery orders by the column, then by the primary key in the same direction, so ties are deterministic (`max` → latest pk wins, `min` → earliest pk wins). The inherited `HasOne` eager (`where_in`), lazy (`load`), `where_has` and `register_related` code paths then work unchanged and always see at most one row per parent.
- `relationship` (in `relationships/relationship.py`) is a decorator that returns a `RelationshipMethod` descriptor. On first access from an owner class it calls the decorated function with the **class** as its argument, so `self.statuses` is the class-level `HasMany` descriptor, not a loaded collection. The resulting relation is named after the method and cached per owner class. Instance access goes through the relation's normal `access` (loaded value or `LazyLoadingViolation`). `@relationship @classmethod` is also accepted.
- Typing: `relationship(fn: Callable[[Any], R]) -> R`, so the method's return annotation decides the type. `User.due_date` is `HasOne[Status]` and `user.due_date` is `Status | None`.

## Known limitations / open questions

- basedpyright reports `self.statuses.latest_of_many()` as an error, because instance access types `statuses` as `Collection[Status]`. The `@relationship @classmethod def due_date(cls)` form type-checks cleanly. Choosing one canonical form is still open.
- Eager callbacks (`with_({"due_date": cb})`) and `where_has` callbacks filter the selected row ("the latest status, if it is done"), not the candidate set. Laravel's `ofMany(..., closure)` inner constraints are not implemented.
- Global scopes on the related model run on the correlated subquery's builder too. Scopes that hard-code the table name instead of using the builder's alias are not covered by this POC.
- Performance relies on an index on `(fk, column, pk)`. Only SQLite is tested.

## Validation

`tests/masoniteorm/sqlite/relationships/test_has_one_of_many.py` covers: latest, oldest and `of_many` max/min with pk tie-breaks, parents without children (`None`), eager loading in one query (counted through `Connection.select`), lazy `load` on a model and on a collection, `where_has` with and without a callback, the classmethod form, unchanged `HasMany`, and rejection of unknown aggregates. The full suite (excluding Postgres) and basedpyright on `masoniteorm/relationships` pass.
