# 016. Skip eager loading when the parent result set is empty

- Date: 2026-10-18
- Status: Accepted

## Problem

Eager-loading a relationship through `with_()` on a query that matches no rows fails for some relation types:

- `MorphMany` and `MorphOne` raise `ValueError: Could not find the record type key for the None class`. `get_related` looks up the morph key of `relation.first()`, and that is `None` for an empty Collection.
- `MorphTo` and `MorphToMany` raise `AttributeError: 'list' object has no attribute 'items'`. `Collection.group_by` on an empty Collection returns a Collection that falls back to a list.

`HasOne`, `HasMany`, `BelongsTo`, `BelongsToMany`, `HasOneThrough` and `HasManyThrough` happen to survive. Each of them still runs a `WHERE ... IN ()` query that cannot match anything.

## Alternatives

- **Guard each `get_related`.** This takes six edits in four classes, and every new relation type has to repeat the check. Rejected.
- **Make `group_by` return a mapping when empty.** This fixes `MorphTo` and `MorphToMany` but not the `ValueError` in `MorphMany`/`MorphOne`. It is also a broader change to the support `Collection`. #280 does this separately. It doesn't address this bug on its own.
- **Return early from `EagerLoadMixin._load_eagers` when there are no parent models (chosen).** With no parents there is nothing to attach related records to. One check covers every relation type and drops the useless queries. `Collection.load` already returns early on an empty Collection, so both eager entry points now behave the same.

## Decision

`_load_eagers` returns immediately when `models` is empty. `with_(...).get()` returns an empty Collection and `with_(...).first()` returns `None`, whatever the relation type.

## Implementation

- `masoniteorm/query/EagerLoadMixin.py`: `if not models: return` at the top of `_load_eagers`.

## Validation

- `tests/masoniteorm/sqlite/relationships/test_eager_load_empty_parents.py` runs `with_().get()` and `with_().first()` on an empty parent set for `MorphMany`, `MorphOne`, `MorphTo`, `MorphToMany`, `BelongsTo`, `HasOne`, `HasMany`, `HasManyThrough`, `BelongsToMany` and `HasOneThrough`. Without the fix, the four morph relations fail.
- `uv run pytest --ignore=tests/masoniteorm/postgres --cov`, basedpyright and ruff.
