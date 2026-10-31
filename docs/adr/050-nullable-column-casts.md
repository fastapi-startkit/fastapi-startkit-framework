# 050. Nullable annotations infer the cast of their inner type

Date: 2026-10-31

## Problem

`Caster.build_casts` (`masoniteorm/models/caster.py`) infers a column's cast from the model annotation through `Caster.normalize_type`, which only recognises bare types (`int`, `float`, `bool`, `datetime`, ...). A nullable annotation is a union: `int | None` is a `types.UnionType`, and `Optional[int]` / `Union[int, None]` are `typing.Union`. None of them matches, so every nullable column falls through to the `"str"` cast and is read back as a string.

With `base_lexeme_id: int | None` on `Lexeme`, `lexeme.base_lexeme_id` is `'1'`, not `1`. Eager loading `examples = HasMany["Lexeme"](local_key="id", foreign_key="base_lexeme_id")` groups children by that foreign key (`'1'`) and looks them up by the parent's `id` (`1`), so no child is attached.

Mapping the union to the inner cast is not enough on its own: the bare casts do not accept `None` (`IntCast.get(None)` raises `TypeError`, `BoolCast.get(None)` returns `False`, `JsonCast.set(None)` writes the string `"null"`), and today a bare `int` attribute that was never assigned raises `TypeError` on access, which a test pins.

## Alternatives

1. **Make every cast accept `None`.** Simple, but it changes bare annotations: an unset `is_admin: bool` would read as `None` instead of `False`, and a bare `dict` column would write `NULL` instead of `"null"`.
2. **Wrap nullable casts in a `NullableCast(inner)`.** Keeps bare types unchanged, but `casts["x"]` stops being an `IntCast`, the wrapper must re-implement the `Caster.get` dispatch for enum and legacy type casts, and field defaults must be forwarded through it.
3. **Unwrap the union to its inner type and record the field as nullable.** The cast is exactly the one the bare type gets; `Caster` short-circuits `None` for nullable fields only.

## Decision

Option 3.

- `Caster.build(model)` returns `(casts, nullable)`, replacing `build_casts`. Before mapping a type, it removes `None` from a top-level union (`X | None`, `Optional[X]`, `Union[X, None]`) and marks the field nullable. `Annotated` is handled on either side of the union: `Annotated[int | None, ...]` and `Optional[Annotated[int, ...]]` both resolve to `int`, and a cast declared in `Annotated` metadata still wins.
- `Caster.get` returns `None` for a `None` value of a nullable field, or the `Field` default/default factory when the field has one (the same fallback a `BaseCast` result of `None` already gets). `Caster.set` returns `None` for a `None` value of a nullable field, so a nullable column writes SQL `NULL`.
- A union of several non-`None` types (`int | str`, `int | str | None`) gets a pass-through `BaseCast`: the value the driver returns is kept as is. Picking the first member would raise on legitimate values of the other members (`int("abc")`), and the old `"str"` cast turned the integer members into strings, which is the bug above.
- Bare annotations are unchanged: same cast, same `None` behaviour.

Relationship key matching (`register_related` comparing the grouped foreign key with the parent key) stays type-strict. With the right casts both sides have the same type; coercing keys there would hide cast bugs and could match unrelated values (`"01"` and `1`).

## Validation

- Unit tests in `tests/masoniteorm/models/test_caster.py`: `int | None`, `Optional[int]`, `Union[int, None]` infer `IntCast` (and the same for `float`, `bool`, `datetime`, `dict`), `Annotated` on either side of the union, declared casts inside an optional `Annotated`, multi-type unions pass values through, `None` stays `None` on get and set, a nullable `Field` default still applies, bare types keep their behaviour.
- SQLite tests in `tests/masoniteorm/sqlite/models/test_sqlite_nullable_casts.py`: nullable `int`/`float`/`bool`/`datetime`/`dict` columns round-trip with the right Python type and `NULL` stays `None`.
- SQLite test in `tests/masoniteorm/sqlite/relationships/test_nullable_foreign_key_eager_load.py`: the `Lexeme.examples` self-relation through `base_lexeme_id: int | None` attaches children when eager loaded.
- Full suite with coverage and basedpyright.
