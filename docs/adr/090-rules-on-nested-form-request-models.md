# 090. Rules on nested FormRequest models

Date: 2026-11-19

## Status

Accepted. Supersedes the nested-model restriction in ADR 042, 048 and 078.

## Problem

`FormRequest.__pydantic_init_subclass__` raised `TypeError` when a field's annotation contained a model with `Field` rules, so rules only worked on top-level fields. Apps validating nested payloads, such as an MCP tool receiving `lexeme: LexemeDetails`, re-ran the nested rules by hand in an `after` hook and built dotted error keys themselves.

## Alternatives

1. **Keep refusing nested rules.** Every app keeps hand-written `after` hooks for nested input.
2. **Run nested rules inside pydantic validators.** Rules are async (`exists`, `unique`, `AsyncRule`) and pydantic validators are sync, the reason ADR 048 moved rules out of pydantic.
3. **Walk the validated instance after parsing (chosen).** `apply_rules` already runs after pydantic; it now descends into nested model instances and reports dotted keys.

## Decision

- The class-definition check is removed. A field may hold a model with `Field` rules directly, in `X | None`, in `list[...]`/`tuple[...]`, in `dict[str, ...]`, or nested at any depth. The nested model may be a plain `BaseModel` or a `FormRequest`.
- `apply_rules` iterates `rule_targets(model, data)`: each top-level rule, then the rules of every model instance found in the field's value (lists by index, mappings by key). Errors use dotted keys such as `address.code`, `stops.1.code` and `labelled.home.code`, matching pydantic's nested error keys.
- A nested rule's attribute is its own field name (`The code field is required.`) and its `data` is the nested model's values, so cross-field rules such as `same_as` compare siblings inside the same object.
- `fill_missing` recurses through the same annotation shapes, so a missing nested field with `required()`/`required_if()` gets the rule message instead of pydantic's `Field required`. Unions with more than one non-`None` member are left untouched because the target model is ambiguous.
- When pydantic rejects anything inside a top-level field, that field's nested rules are skipped, as top-level rules already are for failed fields. Rules in other fields still run on coerced values.
- `stop_on_first_failure` covers nested rules. A nested `FormRequest`'s `authorize`, `prepare_for_validation` and `after` hooks do not run; only its `Field` rules do.

## Validation

`tests/validation/test_form_request.py` covers valid nested input, dotted keys for direct, list, dict and doubly nested models, sibling `same_as`, required messages for missing nested fields, type errors skipping only the failing field, nested `FormRequest` models and `stop_on_first_failure`. `tests/validation` and `tests/mcp` pass.
