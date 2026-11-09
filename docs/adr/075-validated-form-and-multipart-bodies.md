# 075. Validated reads form and multipart bodies

- Date: 2026-11-09
- Status: Accepted

## Problem

`Validated[<FormRequest>]` declares its body as `Body()`, so FastAPI reads JSON and passes any other body through as raw bytes. A `multipart/form-data` or `application/x-www-form-urlencoded` request reached `FormRequest.validate_input` as `bytes` and failed with `422 Input should be a valid dictionary`. A form request could not receive an uploaded file, and applications fell back to bare `UploadFile` endpoint parameters that skip `authorize`, `prepare_for_validation` and the rules.

The rules had no way to check a file either: `size_of` returned `None` for an upload, so `max` always failed, and there was no file or extension rule.

Declaring a required upload also broke `/openapi.json`. A required field is wrapped as nullable so that `None` reaches the `required` rule, and its JSON schema is documented through `handler(schema)`. That handler renders the inner schema by its core type and skips the inner schema's own `pydantic_js_functions`, so `UploadFile`, which documents itself only through that hook, raised `PydanticInvalidForJsonSchema`.

## Alternatives

- **Declare the body as `Form()` when the model has an upload field.** FastAPI then refuses JSON on the same route, so one request class could not serve both an API client and a form.
- **Base64 file contents in a JSON field.** Works today, but every client encodes, payloads grow by a third, and the upload API is bent around a framework gap.
- **A separate `ValidatedForm[...]`.** Two dependencies for one concept; the route author picks the content type the client sends.
- **Read form bodies inside the existing dependency, keyed on the request's content type.** (chosen)

## Decision

The `Validated` dependency checks the request's `content-type`. For `multipart/form-data` and `application/x-www-form-urlencoded` it reads `await request.form()` and maps it through `query_input`, the same field-aware mapping query strings use: a field annotated as a sequence gets `getlist`, any other field gets its single value, and keys the model does not declare are dropped. An upload arrives as Starlette's `UploadFile`, which FastAPI's `UploadFile` annotation accepts. Form bodies are flat, so a route with several body parameters does not embed form errors under the model's name. JSON bodies, query methods and failure rendering are unchanged: a failure still raises `ValidationException`, which renders the 422 for JSON clients and redirects browsers back with session errors.

File rules follow Laravel:

- `Field().file()` passes only for an `UploadFile`.
- `Field().extensions([...])` checks the file name's extension, case-insensitively, with or without a leading dot.
- `min`, `max` and `between` measure an upload in kilobytes, with `file` messages ("must not be greater than :max kilobytes").
- An upload with an empty file name, which browsers send for an empty file input, counts as empty, so `required` fails and optional rules skip it.

The required-field JSON schema now renders the inner schema through `handler.generate_json_schema.generate_inner(schema)`, which applies the inner schema's own JSON schema hooks, so a required `UploadFile` is documented as `{"type": "string", "format": "binary"}`.

## Implementation

- `validation/form_request.py`: `FORM_TYPES` and `is_form(request)`; the `Validated` dependency maps `await request.form()` through `query_input` for form bodies and turns off embedding for them. `query_input` accepts `FormData` as well as `QueryParams`.
- `validation/rules.py`: `is_upload`, `File`, `Extensions`, upload sizes in `size_of`, `file` messages on `Min`, `Max` and `Between`, and empty uploads in `is_empty`. Starlette is imported lazily, so validation still works without the `fastapi` extra.
- `validation/field.py`: `file()` and `extensions()`, and the JSON schema fix.

Out of scope: content sniffing (`mimes`), image dimensions, and documenting a multipart request body in OpenAPI; a form route is still documented with its JSON body.

## Validation

- `tests/validation/test_fastapi_validation.py`: a multipart request with fields, a list field and a file reaches the endpoint; extension, size and required-file failures return 422 with field errors; a browser failure redirects back with 303; urlencoded success and failure; OpenAPI documents a required upload as binary.
- `tests/validation/test_rules.py`: `File`, `Extensions`, kilobyte sizes and empty uploads.
- The full suite (Postgres and MySQL ignored), `uv run ruff check .` and `uv run pyrefly check` pass.
