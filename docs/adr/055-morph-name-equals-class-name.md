# 055 — Morph relations accept the class name as the morph name

- Date: 2026-10-31
- Status: Accepted

## Problem

`Lexeme.with_("media")`, where `media` is a `MorphMany` on `Lexeme` and the morph name is `"Lexeme"`, raised `ValueError: Could not find the record type key for the <Lexeme> class`. `load("media")` raised the same error. `MorphOne` behaved the same way. `MorphTo` was not affected.

`MorphMany.get_record_key_lookup` and `MorphOne.get_record_key_lookup` asked `Registry.get_morph_name(cls)` for the parent's morph name. `get_morph_name` falls back to `cls.__name__`, so the method read "morph name equals the class name" as "model not registered" and raised. That guess is wrong. `Model.__init_subclass__` calls `Registry.register(cls)`, which stores the class name as every model's default morph name. Any model without a `Registry.morph_map` alias, and any model mapped to its own class name, always took the error branch. A model can never be missing from the registry, so the check never caught a real problem.

`MorphMany.get_related` and `MorphOne.get_related` also dropped their `eagers` argument. Nested eager loads such as `with_("media.lexeme")` therefore did not load the inner relation, while `HasMany`/`HasOne` forward it with `with_(eagers)`.

## Alternatives

1. **Keep the guard, but check `Registry._reverse_map` membership.** Every `Model` subclass is in the reverse map, so the guard would never fire. This is dead code that still reads `Registry` internals.
2. **Require an explicit `morph_map` entry.** Breaks the default the registry already provides, and the class name stored in `record_type` is a normal choice (Laravel stores the class when there is no morph map).
3. **Return `Registry.get_morph_name(cls)` as-is.** Chosen. `morph_map` aliases still win because `Registry.morph_map` overrides the reverse map.

## Decision

- `get_record_key_lookup` on `MorphMany` and `MorphOne` returns `Registry.get_morph_name(relation.__class__)`. The class-name default is a valid morph name.
- `MorphMany.get_related` and `MorphOne.get_related` build the polymorphic query with `.with_(eagers or [])`, so nested eager loads reach the related model.

## Consequences

- Models without a morph-map alias work with `MorphMany`/`MorphOne` eager (`with_`) and lazy (`load`) loading. They write and read the class name in the morph type column.
- `test_get_record_key_lookup_raises_for_unknown` in `test_morph_one.py` asserted the old error for an unmapped model. It now asserts the class-name default.
- `MorphTo` and `MorphToMany` already resolved class names through `Registry.get_morph_model` and are unchanged.

## Validation

`tests/masoniteorm/sqlite/relationships/test_morph_name_equals_class_name.py` uses a `Lexeme` parent and a `LexemeMedia` child with no morph-map alias (morph name `"Lexeme"`). It covers:

- the morph name lookup returns `"Lexeme"`;
- `MorphMany` eager load on a collection and on `first()`, with rows matched to the right parent;
- `MorphMany` and `MorphOne` lazy `load`;
- `MorphOne` eager load on a collection;
- `MorphTo` eager load back to `Lexeme`;
- nested eager loads `media.lexeme` and `first_medium.lexeme`.

Without the fix, every case except `MorphTo` failed with the `ValueError` above. The full suite runs with `uv run pytest --ignore=tests/masoniteorm/postgres --cov`.
