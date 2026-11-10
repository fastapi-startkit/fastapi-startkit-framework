# 079. MCP tools receive the validated FormRequest

- Date: 2026-11-10
- Status: Accepted

## Problem

ADR 078 made `Tool.call` validate a `FormRequest` schema and hand `handle` the dict `validated.model_dump(mode="json", exclude_unset=True)`. The validated instance is lost there:

- Enums arrive as their values and dates as ISO strings, so a tool comparing `status is Status.DRAFT` sees `"draft"`.
- `model_fields_set` is gone. Omitted keys are absent from the dict, but helpers on the request that read `model_fields_set` cannot run on a dict.
- Request methods and properties are unavailable.

To get them back, a tool has to rebuild the request with `Schema.model_validate(arguments)`. That parses the input a second time, outside `validate_input`, which applications that keep all validation inside `FormRequest` cannot accept. `model_construct` keeps the JSON values, so enums stay strings.

## Alternatives

- **Pass the instance to `handle` for `FormRequest` tools.** One entry point, but `handle(arguments: dict)` would take two shapes depending on `schema()`, and every tool written against 0.75.2 that reads `arguments["x"]` breaks.
- **Inspect `handle`'s signature.** `call` would pass the instance when the parameter is annotated with a `FormRequest`. It needs annotations resolvable at runtime, breaks under decorators and string annotations, and hides the behaviour in a type hint.
- **A `handle_request(request)` hook.** (chosen) `call` hands a validated `FormRequest` to `handle_request`. Its default dumps the request as before and calls `handle`, so existing tools are unchanged. A tool that wants the instance overrides `handle_request`.

## Decision

`Tool.handle_request(self, request: FormRequest) -> Response` is added:

- The default is `await self.handle(request.model_dump(mode="json", exclude_unset=True))`, the ADR 078 behaviour.
- `Tool.call` runs `authorize()`, then `validate_input` when `schema()` is a `FormRequest` subclass, and passes the validated instance to `handle_request`. Without a `FormRequest` schema, `handle(arguments)` is called as before.
- A tool overriding `handle_request` receives the instance `validate_input` returned: enums, dates and nested models keep their types, `model_fields_set` lists the fields the caller sent (plus those `prepare_for_validation` merged), and request methods work. Nothing is parsed twice.
- `handle` stays abstract and keeps its signature. A tool that overrides `handle_request` still defines `handle`, which serves calls without a `FormRequest` schema.

## Validation

`tests/mcp/test_tool.py` covers, through `Tool.call`:

- an overriding tool receiving the schema's instance;
- enums and dates keeping their types;
- `model_fields_set` excluding omitted fields and including a field sent as `null`;
- prepared values reaching the instance;
- a tool that does not override `handle_request` still receiving the `exclude_unset` JSON dict;
- a tool without a `FormRequest` schema receiving `arguments` unchanged;
- a refused `authorize()` stopping the call before validation and `handle_request`.

The ADR 078 tests in `tests/mcp/test_exceptions.py` pass unchanged.
