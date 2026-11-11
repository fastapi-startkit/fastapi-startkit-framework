# 080. MCP tools receive the validated FormRequest

- Date: 2026-11-11
- Status: Accepted

## Problem

ADR 078 made `Tool.call` validate a `FormRequest` schema and hand `handle` the dict `validated.model_dump(mode="json", exclude_unset=True)`. The validated instance is lost there:

- Enums arrive as their values and dates as ISO strings, so a tool comparing `status is Status.DRAFT` sees `"draft"`.
- `model_fields_set` is gone. Omitted keys are absent from the dict, but helpers on the request that read `model_fields_set` cannot run on a dict.
- Request methods and properties are unavailable.

To get them back, a tool has to rebuild the request with `Schema.model_validate(arguments)`. That parses the input a second time, outside `validate_input`, which applications that keep all validation inside `FormRequest` cannot accept. `model_construct` keeps the JSON values, so enums stay strings.

## Alternatives

- **Pass the instance to `handle` for `FormRequest` tools.** (chosen) One entry point: a tool declares its request as the `handle` parameter and works with it directly. A tool written against 0.75.2 that reads `arguments["x"]` from a `FormRequest` schema must change to `arguments.x`.
- **A `handle_request(request)` hook whose default dumps and calls `handle`.** Backward compatible, but a typed tool overrides a second entry point and still defines a `handle` it never uses for that schema. An earlier revision of this ADR chose it; it was dropped in favour of a single entry point.
- **Inspect `handle`'s signature.** `call` would pass the instance when the parameter is annotated with a `FormRequest`. It needs annotations resolvable at runtime, breaks under decorators and string annotations, and hides the behaviour in a type hint.

## Decision

- `Tool.call` runs `authorize()`, then `validate_input` when `schema()` is a `FormRequest` subclass, and passes the instance `validate_input` returned to `handle`. Without a `FormRequest` schema, `handle(arguments)` receives the raw dict as before.
- The instance keeps enums, dates and nested models typed, `model_fields_set` lists the fields the caller sent (plus those `prepare_for_validation` merged), and request methods work. Nothing is parsed twice.
- `Tool.handle` is declared `handle(self, arguments: Any)`. Subclasses annotate the parameter as their own `FormRequest` or as `dict[str, Any]`; a union in the base would make both of those overrides narrower than the base and fail type checking.
- A tool that needs the JSON dict of ADR 078 calls `arguments.model_dump(mode="json", exclude_unset=True)` itself.

This amends step 3 ("Handling") of ADR 078. Authorization order, validation and exception rendering are unchanged.

## Validation

`tests/mcp/test_tool.py` covers, through `Tool.call`:

- `handle` receiving the schema's instance;
- enums arriving as members (`status is Status.PUBLISHED`), an omitted enum as its default member, and dates as `date`;
- a value outside the enum refused with `-32000` and `data` naming the field, before `handle` runs;
- `validate_input` itself returning the typed values, since `FormRequest.parse` builds the instance with `model_validate`;
- `model_fields_set` excluding omitted fields and including a field sent as `null`;
- prepared values reaching the instance;
- a tool without a `FormRequest` schema receiving `arguments` unchanged;
- a refused `authorize()` stopping the call before validation and `handle`.

The ADR 078 tests in `tests/mcp/test_exceptions.py` now dump the instance inside the test tool; the test that asserted JSON values in `handle` is removed.
