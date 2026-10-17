# 016. Infer the related model from the relationship subscript

- Date: 2026-10-17
- Status: Accepted
- Builds on: [015](015-generic-relationships.md)

## Problem

ADR 015 made relationships generic, so a typed relationship names its model twice:

```python
lexeme = BelongsTo["Lexeme"]("Lexeme", local_key="word_id", foreign_key="id")
```

The subscript drives typing, the argument drives runtime resolution, and nothing checks that they agree. A typo or a rename in one place but not the other gives a relationship typed as one model and querying another.

## Alternatives

- **Keep both.** Rejected: the duplication is the problem.
- **Real class only (`BelongsTo[Lexeme]`).** The subscript is evaluated with the class body, so the class must be imported at runtime. Models usually reference each other (`Word.lexeme`, `Lexeme.words`), so one side of every pair hits a circular import. Supported, but not as the only form.
- **Annotate the attribute (`lexeme: BelongsTo[Lexeme] = BelongsTo(...)`).** The annotation could stay under `TYPE_CHECKING`, but resolving it at runtime means evaluating annotations whose names were never imported (`NameError`), or parsing their text. Rejected as fragile.
- **Read the subscript at runtime.** `Generic` sets `__orig_class__` on the instance right after `__init__` returns; `__set_name__` runs later, when the owning class is created, so the subscript is available there and on every later access. **Chosen.**

## Decision

The model argument of `BelongsTo`, `HasOne`, `HasMany` and `BelongsToMany` is optional:

```python
if TYPE_CHECKING:
    from app.models.lexeme import Lexeme

class Word(Model):
    lexeme = BelongsTo["Lexeme"](local_key="word_id", foreign_key="id")
```

- An explicit model argument wins, so existing code is unchanged.
- Otherwise the subscript is used: a quoted name (`ForwardRef`) is resolved through `Registry` exactly like the string argument; a real class (`BelongsTo[Lexeme]`, when there is no import cycle) is used as is.
- A relationship with neither raises `TypeError` when the owning class is created, naming the relationship and showing both forms.
- Keys must be passed by keyword when the model argument is omitted: `BelongsTo["Lexeme"]("word_id")` reads `"word_id"` as the model, which fails at first use with "Model 'word_id' not found in registry".
- Morph and through relationships are unchanged: their first argument is a morph key or a pair of models, which a single type parameter cannot express.

## Implementation

- `BaseRelationship.bind_model(fn)` stores the optional name and points `self.fn` at `related_model`, so the existing `self.fn()` call sites keep working. `BaseRelationship.__init__`, `BelongsTo`, `HasOne` and `BelongsToMany` call it.
- `related_model()` resolves the explicit name, else the subscript. The subscript is read from `self.__dict__`, not with `getattr`, because `BaseRelationship.__getattr__` forwards unknown attributes to the query builder, which would recurse into `related_model`.
- `BaseRelationship.__set_name__` checks relationships that went through `bind_model`, so a missing model fails at import time instead of at the first query.

## Validation

- sqlite tests: `BelongsTo`, `HasOne`, `HasMany` and `BelongsToMany` declared without the model argument resolve, eager-load and stay typed (`assert_type`); a real-class subscript resolves; an explicit argument wins over the subscript; a relationship with no model raises `TypeError` at class creation.
- Full suite with coverage; basedpyright clean on the changed files.
