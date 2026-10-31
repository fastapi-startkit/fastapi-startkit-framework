# 053. `Validated` reads the query string and the body

Date: 2026-10-31

Extends the FastAPI integration of [ADR 048](048-async-first-validation.md).

Status: amended by [ADR 056](056-validated-write-methods-read-the-body-only.md). Write methods with a body now read the body only, unless the model sets `merge_query = True`.

## Problem

`Validated[Model]` declared its input as a required `Body()`, so a `FormRequest` could only validate a JSON body. A `GET` endpoint with filters (`/lexemes?window=today&page=2`) could not use the same class: FastAPI answered `422 body: Field required` before the dependency ran, even when every query parameter was valid. Applications fell back to binding the model with `Annotated[Model, Query()]`, which only runs pydantic, so `authorize`, `prepare_for_validation`, the fluent rules and `after` were silently skipped.

Laravel's `FormRequest` validates `$request->all()`, the query string and the body together, so one request class serves a `GET` listing and a `POST` form alike.

Reading the query string must not weaken write routes. A JSON body needs a CORS preflight, so before this change a `Validated` `POST` could not be forged by a cross-site `<form>`: the form sends `application/x-www-form-urlencoded` or `text/plain`, which never produces a JSON object. If a body-less `POST` fell back to the query string, `<form method="post" action="https://app/transfer?to=attacker&amount=100">` without inputs would pass validation without a preflight.

## Alternatives

1. **A separate `ValidatedQuery[Model]`.** It reads only the query string and documents every field as a query parameter. The same model needs two dependency types depending on where the input comes from, and a route cannot take some fields from the query and the rest from the body.
2. **Choose the source from the route's methods when the dependency is built.** The dependency is created when the annotation is evaluated, before the route and its methods are known, and one function can be mounted on several routes.
3. **Merge the query string and the body in `Validated`, and choose by `request.method` at request time.** The body becomes optional in the signature. Inside the dependency, `request.method` and the raw body are known, so a missing body can still be rejected on write methods.

## Decision

Option 3.

- The `Validated` dependency keeps its `Body()` parameter with `RawInput(model)` but gives it a `None` default, so a request without a body reaches the dependency.
- The dependency reads `await request.body()`, which FastAPI has already cached. The request has no body when those bytes are empty.
- **Query methods** are `GET`, `HEAD`, `OPTIONS` and `DELETE`. Without a body they validate the query input. `DELETE` is included because its target and options live in the URL, RFC 9110 gives a `DELETE` body no defined semantics, and a cross-origin `DELETE` always needs a CORS preflight (only `GET`, `HEAD` and `POST` are CORS-safelisted, and HTML forms can only send `GET` and `POST`). The framework has no method-override middleware that could turn a form `POST` into a `DELETE`.
- **Write methods** (`POST`, `PUT`, `PATCH` and any other method) without a body report the missing body exactly as FastAPI did before this ADR: `"": ["Field required"]`, or `"<embed key>": ["Field required"]` for each embedded model. `authorize` and the rules do not run, as before. A cross-site form with an empty body therefore still gets a 422.
- When a body is present, `FormRequest.request_input(params, body)` merges `{**query_input, **body}` if the body is an object (the body wins on a clash), and passes any other body through unchanged, so `[1]`, a `text/plain` string or a JSON `null` fails with pydantic's `model_type` error under `""`. A JSON `null` is a body that is not an object. It is not a missing body, on every method.
- With several body parameters the body stays embedded per model. A model whose embed key is absent from a present body, or is `null` (FastAPI passes both as `None`), reads the query input. This needs a JSON body, so it does not reopen the cross-site case. Errors keep their embed prefix (`search.term`) wherever the value came from.
- `FormRequest.query_input(params)` keeps only the query keys that the model accepts. `FormRequest.query_fields()` builds them the way pydantic validates: every `validation_alias` (a string, a single-key `AliasPath`, every choice of `AliasChoices`), which also covers `alias` and `alias_generator`. It adds the field name when the field has no alias or when `validate_by_name`/`populate_by_name` is set, and drops the aliases when `validate_by_alias=False`. Keys the model does not declare are ignored.
- A field whose annotation is a `collections.abc.Sequence` or `collections.abc.Set` (`list`, `tuple`, `set`, `frozenset`, `Sequence[...]`, `AbstractSet[...]`, also inside `X | None` or `Annotated`), but not `str`, `bytes` or `bytearray`, receives every repeated value (`?tag=a&tag=b`). Any other field receives the last value.
- `validate_input` is unchanged. Query values arrive as strings and pydantic coerces them (`"2"` to `2`, `"1"` to `True`, a string to an enum) before the rules run, exactly as for JSON values, so type errors and rule errors still share one 422.

### Query input on write methods

Amended by [ADR 056](056-validated-write-methods-read-the-body-only.md): this merge now needs `merge_query = True`.

Write methods with a JSON body still merge the query, as Laravel's `$request->all()` does. As a result, a declared field can be set from the URL: `PATCH /profile?role=admin` with `{"name": "n"}` validates with `role == "admin"`, and `role` is in `model_fields_set`, so `update(data.model_dump(exclude_unset=True))` writes it. This gives the client no new power. The same client can put `role` in the body, the model's declared fields remain the only assignable fields, and the cross-site path is closed because the merge needs a JSON body. URLs end up in access logs and proxies, so a sensitive field (a role or a password) must not be accepted from the query. Exclude the field from the model, or reject it in `prepare_for_validation` or `after`. Keeping the merge lets one model take its filters from the URL and its payload from the body.

### OpenAPI

FastAPI documents a `Validated` model as a request body on every method, because the dependency declares a `Body()` parameter. Swagger UI and generated clients cannot send a body on `GET`, so `document_query_input(fastapi)` (installed by `FastAPIProvider`) post-processes the generated schema once. For each `APIRoute` operation on a query method whose body parameters all come from `Validated`, it removes `requestBody` and adds one `in: query` parameter for each property of the model's component schema, with `required` taken from the component. Embedded models contribute their properties in route order, the first declaration of a name wins, and existing path parameters are kept. Write methods keep the body schema unchanged. Limitations:

- A query-method route that also declares a plain `Body()` parameter keeps the generated `requestBody`, because the body cannot be dropped for one part.
- The query input that write methods merge is not listed as parameters. The same fields are already documented by the body.
- A `DELETE` that does send a body is accepted, but only the query parameters are documented.
- A `FastAPI()` instance that was not created by `FastAPIProvider` must call `document_query_input` itself.

### Behaviour changes

- The OpenAPI `requestBody` of a `Validated` write route is no longer `required`, and an embedded body no longer lists its models under `required`. Query-method routes document query parameters instead of a body.
- A present body with an absent embedded key reports that model's `required` rules (`shipping.name`) instead of `shipping: Field required`.
- Declared fields can be filled from the query string on write methods that send a JSON body (see above).

## Validation

`tests/validation/test_fastapi_validation.py` covers a `GET` with `Validated`: model defaults, coercion and repeated keys, the Laravel 422 shape, type and rule errors in one response, `required` messages, typed path parameters as context with an async rule, `authorize`, a query model combined with an embedded body model, the body overriding the query and the query filling missing body fields. Regression tests cover a body-less cross-site `POST` (form-urlencoded, `text/plain` and no content type), body-less `PUT`/`PATCH`, missing embedded bodies, a non-JSON body, a non-object body and a JSON `null` body combined with a valid query, a body-less `DELETE`, query values set on a `PATCH`, aliases, `AliasChoices` and `populate_by_name`, abstract sequences and sets, embedded query models, and the OpenAPI parameters for query methods, path parameters, write methods and mixed bodies. Unit tests cover `is_sequence` and `alias_keys`. The full framework suite passes with coverage above the threshold, and `ruff` and `basedpyright` are clean.
