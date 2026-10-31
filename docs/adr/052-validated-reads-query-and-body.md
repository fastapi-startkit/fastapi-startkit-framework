# 052. `Validated` reads the query string and the body

Date: 2026-10-31

Extends the FastAPI integration of [ADR 048](048-async-first-validation.md).

## Problem

`Validated[Model]` declared its input as a required `Body()`, so a `FormRequest` could only validate a JSON body. A `GET` endpoint with filters (`/lexemes?window=today&page=2`) could not use the same class: FastAPI answered `422 body: Field required` before the dependency ran, even when every query parameter was valid. Applications fell back to binding the model with `Annotated[Model, Query()]`, which only runs pydantic, so `authorize`, `prepare_for_validation`, the fluent rules and `after` were silently skipped.

Laravel's `FormRequest` validates `$request->all()`, the query string and the body together, so one request class serves a `GET` listing and a `POST` form alike.

## Alternatives

1. **A separate `ValidatedQuery[Model]`.** It reads only the query string and documents every field as a query parameter. The same model needs two dependency types depending on where the input comes from, and a route cannot take some fields from the query and the rest from the body.
2. **Infer the source from the HTTP method.** The dependency is built when the annotation is evaluated, before the route and its method are known, and a `POST` with query parameters is valid HTTP.
3. **Merge the query string and the body in `Validated`.** The body becomes optional. The query values of the model's fields are read first and the body's keys override them.

## Decision

Option 3.

- The `Validated` dependency keeps its `Body()` parameter with `RawInput(model)` (OpenAPI still references the model schema) but gives it a `None` default, so a request without a body reaches the dependency.
- `FormRequest.query_input(params)` keeps only query keys that are field names or aliases of the model. A field whose annotation is a `list`, `set`, `frozenset` or `tuple`, also inside `X | None`, receives every repeated value (`?tag=a&tag=b`); any other field receives the last value. Keys the model does not declare are ignored.
- `FormRequest.request_input(params, body)` returns the query input when the body is `None`, `{**query, **body}` when the body is a mapping (the body wins on a clash), and the body unchanged otherwise, so a non-object body still fails with pydantic's `model_type` error.
- `validate_input` is unchanged. Query values arrive as strings and pydantic coerces them (`"2"` to `2`, `"1"` to `True`, a string to an enum) before the rules run, exactly as for JSON values, so type errors and rule errors still share one 422.
- With several body parameters the body stays embedded per model, and the query string is offered to every `Validated` model on the route. Errors keep their embed prefix (`search.term`) wherever the value came from.

### Behaviour changes

- A missing body no longer produces FastAPI's `Field required` error under the empty key `""`. The model is validated with the query input instead, so its `required` rules report each missing field (`email`, `username`, ...), which is Laravel's response. A missing embedded body likewise reports `shipping.name` instead of `shipping`.
- The OpenAPI `requestBody` of a `Validated` route is no longer `required`, and an embedded body no longer lists its models under `required`. Query input is not listed as OpenAPI parameters, because the same fields are already documented by the body schema.

## Validation

`tests/validation/test_fastapi_validation.py` covers a `GET` with `Validated`: model defaults without parameters, coercion of query strings and repeated keys, the Laravel 422 shape, type and rule errors in one response, `required` messages for missing parameters, typed path parameters as context with an async rule, `authorize`, a query model combined with an embedded body model, the body overriding the query, and the query filling fields missing from the body. The existing missing-body and OpenAPI tests are updated for the behaviour changes above. The full framework suite passes.
