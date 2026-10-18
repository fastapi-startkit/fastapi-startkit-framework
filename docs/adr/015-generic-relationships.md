---
title: Generic (subscriptable) ORM relationships
date: 2026-10-17
---

## Why

Relationship descriptors (`BelongsTo`, `HasOne`, `HasMany`, `BelongsToMany`, `HasOneThrough`, `HasManyThrough`, `MorphOne`, `MorphMany`, `MorphTo`, `MorphToMany`) take the related model as a string so models can reference each other without circular imports. Because of that, a type checker has no idea what `word.lexeme` is: the unannotated `__get__` infers to `Self | Any`, so attribute access on a related model is unchecked and has no completion.

Users want to state the related model once, with the model imported only for the type checker:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .lexeme import Lexeme


class Word(Model):
    lexeme = BelongsTo["Lexeme"](local_key="word_id", foreign_key="id")
```

`Lexeme` does not exist at runtime, so the subscript has to stay a string forward reference and must not be evaluated. At runtime the model is resolved from the subscript through the registry (see "Inferring the related model from the subscript").

## Alternatives

- **Annotate the attribute (`lexeme: "Lexeme | None" = BelongsTo("Lexeme")`).** Rejected: it needs a `pyright: ignore` on every relationship (the descriptor is not assignable to the annotation), and class access `Word.lexeme` would be typed as the model instead of the relationship.
- **A `.pyi` stub per user model.** Rejected: it puts the burden on every application and drifts from the model.
- **Overloads on every relationship class.** Rejected: pyright requires an implementation next to each overload set, so each of the ten classes would need its own `__get__` wrapper with three overloads.
- **`BaseRelationship` generic over the related model and the instance-access result.** Chosen: one overloaded `__get__` in the base, each subclass only names its result shape.

## Decision

- `BaseRelationship(Generic[TModel, TResult])`. `TModel` is bound to `Model` and defaults to `Model`; `TResult` defaults to `Any`. Defaults come from `typing_extensions.TypeVar` (PEP 696) because Python 3.12 is supported; `typing-extensions` becomes an explicit dependency (it was already installed through pydantic).
- Single relationships subclass `BaseRelationship[TModel, SingleResult[TModel]]`, many relationships subclass `BaseRelationship[TModel, ManyResult[TModel]]`. Each relationship is therefore generic over exactly one parameter, the related model.
- `BaseRelationship.__get__` has three overloads:
  1. class access (`instance: None`) returns `Self`, so `Word.lexeme` is `BelongsTo[Lexeme]`;
  2. `self: BaseRelationship[Model, Any]` returns `Any`. `TModel` is invariant, so only an unsubscripted relationship (whose `TModel` falls back to the `Model` default) matches; its typing stays exactly as loose as before;
  3. otherwise `TResult`.
- The base `__get__` delegates to `access(instance, owner)`. The six classes that had their own `__get__` (through and morph relations) now override `access` instead, so they inherit the typed descriptor without repeating overloads. Runtime behaviour is unchanged.
- Subscripting is `typing.Generic.__class_getitem__`: it builds a `_GenericAlias` holding a `ForwardRef("Lexeme")`, never evaluates it, and calling the alias instantiates the class normally.

### Instance-access result shape

At runtime, instance access returns the stored value when the relationship is eager-loaded (`with_`, `load`) and an awaitable query when it is not (`await word.lexeme`). Python typing cannot express "value or awaitable of value" usefully: a `T | Awaitable[T]` union makes both `word.lexeme.name` and `await word.lexeme` errors. The shape lives in two aliases in `BaseRelationship.py`:

| Option | `SingleResult[T]` | `ManyResult[T]` | Outcome |
|---|---|---|---|
| A. Loaded | `T \| None` | `Collection[T]` | **Chosen.** Matches eager-loaded access, which is the access pattern the framework wants to encourage. |
| B. Awaitable | `Awaitable[T \| None]` | `Awaitable[Collection[T]]` | Rejected: eager-loaded `word.lexeme.name` is reported as an unknown attribute of an awaitable, and awaiting an eager-loaded value fails at runtime because models and collections are not awaitable. |

Unsubscripted relationships are `Any`, exactly as loose as before.

An explicit `BelongsTo["Model"]` (or any relationship subscripted with the base `Model`) is indistinguishable from an unsubscripted one: `TModel` is the same `Model` the default fills in, so overload 2 matches and instance access is `Any`. Subscript with the concrete related model to get a typed result.

### Lazy loading is disabled (breaking change)

Option A types `word.lexeme` as the loaded value, so the lazy path (`await word.lexeme`) would be a type error that still works at runtime. Rather than typing a path the framework does not want used, lazy loading is removed: accessing a relationship on a loaded model that was not eager-loaded raises `LazyLoadingViolation`. Its message names the model and the relationship and points to `with_()` and `load()`. Enforcement is the default, not an opt-in, because an opt-in would leave every non-opted application with types that disagree with runtime.

Supporting changes:

- `Model.load(*relations) -> Self` eager-loads relationships onto one model (it delegates to `Collection.load`), so `(await word.load("lexeme")).lexeme` is typed.
- `Collection.load` and eager loading register relationships that have no related records: `None` for single relationships and an empty `Collection` for many relationships. Previously these were left unregistered, which would now raise, or set to `None`, which contradicts `Collection[T]`.
- `Collection.group_by` returns a dict-backed collection even when there is nothing to group, so a lookup on an empty result (including a `NULL` foreign key) misses instead of indexing a list. `HasMany` wraps each group in a `Collection`, so a non-empty many relationship is a `Collection` rather than a `list`.
- `Collection.load` passes the owner's builder to `get_related`, which `BelongsToMany` needs to resolve its pivot table; `MorphToMany` gains `map_related` so it can be loaded.

Migration:

| Before | After |
|---|---|
| `lexeme = await word.lexeme` | `await word.load("lexeme")` then `word.lexeme` |
| `for word in words: await word.lexeme` | `words = await Word.with_("lexeme").get()` or `await words.load("lexeme")` |
| empty eager-loaded many relationship is `None` | it is an empty `Collection` |

Query-side relationship APIs are unchanged: class access (`Word.lexeme.attach(...)`, `where_has`, `with_`) still works, and `apply_query`/`get_related` remain available for explicit queries.

### Linters

Ruff's F401 only reads strings in annotation positions, so an import used only by `BelongsTo["Lexeme"]` is reported as unused and `ruff --fix` would delete it. Such `TYPE_CHECKING` imports carry `# noqa: F401`.

### Inferring the related model from the subscript

Passing both a subscript and a model argument names the model twice (`BelongsTo["Lexeme"]("Lexeme", ...)`), and nothing checks that the two agree. The subscript is therefore the source of the model:

```python
if TYPE_CHECKING:
    from app.models.lexeme import Lexeme  # noqa: F401

class Word(Model):
    lexeme = BelongsTo["Lexeme"](local_key="word_id", foreign_key="id")
```

Alternatives considered:

- **Real classes only (`BelongsTo[Lexeme]`).** The subscript is evaluated along with the class body, so the class must be imported at runtime. Models that reference each other then hit circular imports. This form is supported, but it can't be the only one.
- **An attribute annotation (`lexeme: BelongsTo[Lexeme] = BelongsTo(...)`).** Resolving it at runtime means evaluating names that were never imported, or parsing the annotation text. Rejected as fragile.
- **Read the subscript at runtime (chosen).** `Generic` sets `__orig_class__` on the instance right after `__init__` returns. `__set_name__` runs later, so the subscript is available from then on.

Rules:

- A quoted subscript (`ForwardRef`) resolves through `Registry`. A real class is used as is.
- A relationship with neither a subscript nor a model argument raises `TypeError` when the owning class is created. The error names the relationship (`Owner.attribute`, or just the relationship class when it is used outside a class body) and suggests only the subscript form.
- Keys are passed by keyword. `BelongsTo["Lexeme"]("word_id")` would read `"word_id"` as the model.
- Morph and through relationships are unchanged. Their first argument is a morph key or a pair of models, which one type parameter cannot express.

Deprecation: passing the model as an argument (`BelongsTo("Lexeme", ...)`) still works and still takes precedence over the subscript. It emits a `DeprecationWarning` and will be removed in 1.x. The warning uses `skip_file_prefixes` so that it points at the user's model file, not the framework. All in-repo fixtures, examples and the database skill have been migrated.

## Implementation

- `relationships/BaseRelationship.py`: `TModel`, `TResult`, `SingleResult`, `ManyResult`, generic base, overloaded `__get__`, `access`.
- `BelongsTo`, `HasOne`, `HasOneThrough`, `MorphOne`, `MorphTo`: `BaseRelationship[TModel, SingleResult[TModel]]`.
- `HasMany`, `BelongsToMany`, `HasManyThrough`, `MorphMany`, `MorphToMany`: `BaseRelationship[TModel, ManyResult[TModel]]`.
- Through and morph relations rename `__get__` to `access`.
- `exceptions.py`: `LazyLoadingViolation`; `access` raises it instead of returning a query.
- `Model.load`, `Collection.load`, `EagerLoadMixin._register_relationships_to_model`, `MorphToMany.map_related`.
- In-repo `await model.relation` usages (framework tests) migrated to `load()`; `example/` has none.
- `pyproject.toml`: `typing-extensions` runtime dependency.
- `BaseRelationship.bind_model(fn)` warns when `fn` is given, stores it, and points `self.fn` at `related_model`, so existing `self.fn()` call sites keep working. `BaseRelationship`, `BelongsTo`, `HasOne` and `BelongsToMany` call it. `related_model()` reads `__orig_class__` from `self.__dict__` because `__getattr__` forwards to the query builder and would recurse. `__set_name__` validates the model at class creation.

## Validation

- `tests/masoniteorm/fixtures/typed/`: two model modules that reference each other only under `TYPE_CHECKING`.
- `tests/masoniteorm/sqlite/relationships/test_generic_relationships.py`: subscripted `BelongsTo`, `HasOne`, `HasMany`, `BelongsToMany` on sqlite: module import succeeds, eager load with `with_`, and `where_has`.
- The same file uses `assert_type` for class access and instance access and is checked with `uv run pyright` and `uv run basedpyright`.
- The same file covers `LazyLoadingViolation` and its message, typed `load()`, and empty relationships registered through `load()`, `with_().get()` and `with_().first()`.
- `test_belongs_to_null_foreign_key.py` covers a `BelongsTo` whose foreign keys are all `NULL`, and mixed with resolvable keys, through `load()`, `Collection.load()`, `with_().get()` and `with_().first()`.
- Each many relationship (`HasMany`, `HasManyThrough`, `BelongsToMany`, `MorphMany`, `MorphToMany`) has sqlite tests asserting that an empty relation is an empty `Collection` through `load()`, `with_().get()` and `with_().first()`.
- `test_inferred_relationship_model.py` covers the following:
  - `BelongsTo`, `HasOne`, `HasMany` and `BelongsToMany` resolve from a quoted subscript.
  - A real-class subscript resolves.
  - An explicit argument wins, with a warning.
  - The deprecation message mentions 1.x and points at the caller's file.
  - An unsubscripted model argument stays `Any`.
  - A relationship with no model raises `TypeError` at class creation.
- Full suite: `uv run pytest --ignore=tests/masoniteorm/postgres --cov` stays above `fail_under`.
