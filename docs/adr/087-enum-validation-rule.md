# 087. Enum validation rule

Date: 2026-11-18

## Status

Accepted

## Problem

`fastapi_startkit.validation` has no equivalent of Laravel's `Rule::enum`. Apps that accept an enum backing value either annotate the field with the enum (pydantic error text, no `only`/`except` restrictions, no custom message through `Field`) or repeat the values in `Field().in_([...])`, which drifts when the enum changes.

## Alternatives

1. **Rely on pydantic enum annotations.** Coerces values, but cannot restrict to a subset of cases conditionally and produces pydantic messages instead of rule messages.
2. **`Field().in_([member.value for member in Status])`.** No enum awareness: member instances, strict typing and `only`/`except` must be rebuilt by hand.
3. **A dedicated `EnumRule` plus `Field.enum()` (chosen).** Fits the existing `Rule`/`Field` design, keeps messages, `msg()` and empty-value skipping consistent with the other rules.

## Decision

Add `EnumRule(Rule)` to `validation/rules.py` and `Field.enum()` to `validation/field.py`; export `EnumRule` from `fastapi_startkit.validation`.

```python
class Order(FormRequest):
    status: Annotated[str, Field().required().enum(Status, except_=[Status.ARCHIVED])]
    channel: Annotated[str, Field().add(EnumRule(Channel).when(lambda data: data.get("beta"), lambda rule: rule.only([Channel.WEB])))]
```

- A value passes when it is a member of the enum, or equals a member's backing value **with the same type** (`type(value) is type(member.value)`), mirroring PHP's strict `tryFrom`: `"1"` does not match an `IntEnum`, `1` does not match a `StrEnum`, and `True` does not match a value of `1`. Members of a different enum fail.
- Values reaching rules are the pydantic-coerced field values, so an `int` field fed `"1"` from a query string is checked as `1`.
- `only(cases)` and `except_(cases)` accept a single case or an iterable of cases (members or backing values, normalised through the enum so an unknown case raises `ValueError` at declaration). Each call replaces the previous list, as in Laravel. When both are set the allowed cases are the intersection: in `only` and not in `except_`. Laravel ignores `except` once `only` is set; the intersection is the less surprising behaviour and is a deliberate deviation.
- `when(condition, callback, default=None)` registers a conditional restriction. `condition` is a bool or a callable receiving the validated data and is evaluated at validation time; `callback` (or `default` when the condition is false) receives a copy of the rule, so declaring rules at class level never leaks restrictions between requests.
- The default message is Laravel's `The selected :attribute is invalid.`; `:values` (the allowed backing values) is available to custom messages.
- Empty values (`None`, `""`) are skipped like every non-implicit rule; combine with `required()` to reject them.

## Validation

Unit tests in `tests/validation/test_enum_rule.py` cover `StrEnum`, `IntEnum` and plain `Enum`, member instances, wrong types, booleans, foreign enums, `only`/`except_` alone and combined, value-based cases, `when` with bool, callable and default branches, isolation between calls, messages and `Field.enum()`. HTTP tests in the same file drive the rule through a `FormRequest` route. The suite runs with `uv run pytest --ignore=tests/masoniteorm/postgres --cov`, keeping coverage at or above 80%.
