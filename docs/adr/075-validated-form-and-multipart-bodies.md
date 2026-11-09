# 075. Validated reads form and multipart bodies

- Date: 2026-11-09
- Status: Accepted, amended by [076](076-harden-validated-multipart-bodies.md)

## Problem

`Validated[<FormRequest>]` declares its body as `Body()`, so FastAPI reads JSON and passes any other body through as raw bytes. A `multipart/form-data` or `application/x-www-form-urlencoded` request reached `FormRequest.validate_input` as `bytes` and failed with `422 Input should be a valid dictionary`. A form request could not receive an uploaded file, and applications fell back to bare `UploadFile` endpoint parameters that skip `authorize`, `prepare_for_validation` and the rules.

The rules had no way to check a file either: `size_of` returned `None` for an upload, so `max` always failed, and there was no file or extension rule.

Declaring a required upload also broke `/openapi.json`. A required field is wrapped as nullable so that `None` reaches the `required` rule, and its JSON schema is documented through `handler(schema)`. That handler renders the inner schema by its core type and skips the inner schema's own `pydantic_js_functions`, so `UploadFile`, which documents itself only through that hook, raised `PydanticInvalidForJsonSchema`.

## Alternatives

- **Declare the body as `Form()` when the model has an upload field.** FastAPI then refuses JSON on the same route, so one request class could not serve both an API client and a form.
- **Base64 file contents in a JSON field.** Works today, but every client encodes, payloads grow by a third, and the upload API is bent around a framework gap.
- **A separate `ValidatedForm[...]`.** Two dependencies for one concept; the route author picks the content type the client sends.
- **Read form bodies for every `FormRequest`, keyed on the request's content type.** Breaks [ADR 053](053-validated-reads-query-and-body.md): a `Validated` `POST` could no longer rely on the CORS preflight a JSON body needs, so a cross-site `<form>` could submit to every existing write route.
- **Read form bodies only for a `FormRequest` that opts in with `accepts_form_bodies = True`.** Every upload request needs the same boilerplate line, and a request that declares an `UploadFile` field is unusable without it, so the flag only restates what the field types already say. An earlier revision of this ADR chose it; it was dropped because uploads should work by default.
- **Read multipart bodies only for a `FormRequest` that declares an upload field.** (chosen)

## Decision

A `FormRequest` accepts a file with no extra setup. Declaring an upload field is enough:

```python
class TranscriptRequest(FormRequest):
    transcript: Annotated[UploadFile, Field().required().file().extensions(["srt"])]
```

When `Validated[...]` builds its dependency, it checks whether any field's annotation contains Starlette's `UploadFile`, including `UploadFile | None`, `list[UploadFile]` and `Annotated[UploadFile, ...]`. Mappings such as `dict[str, UploadFile]` do not count, because a flat form cannot fill them. Fields must be annotated with `fastapi.UploadFile`; pydantic cannot build a schema for `starlette.datastructures.UploadFile`. There is no flag to set.

Such a request accepts `multipart/form-data` as well as JSON. It does not accept `application/x-www-form-urlencoded`, because that encoding cannot carry a file: a browser form with a file input must use multipart, so urlencoded support would add a cross-site entry point without enabling uploads.

A `FormRequest` without an upload field stays JSON-only, and ADR 053's guarantee still holds for it: a form body, urlencoded or multipart, reaches the model as raw bytes. `authorize` runs first and can answer 403; if it passes, the body fails with a 422 before `prepare_for_validation` or the rules run. A route whose request declares an upload accepts a multipart body that any cross-site `<form>` can send without a preflight. The application must protect that route with CSRF tokens or a `SameSite=Lax` or `Strict` session cookie. The exposure is limited to routes that take a file, which is unavoidable because browsers upload files only through multipart forms.

For a request with an upload field, the `Validated` dependency checks the request's `content-type`. For `multipart/form-data` it reads `await request.form()` and maps it through `query_input`, the same field-aware mapping query strings use: a field annotated as a sequence gets `getlist`, any other field gets its single value, and keys the model does not declare are dropped. An upload arrives as Starlette's `UploadFile`, which FastAPI's `UploadFile` annotation accepts. The form is closed after the response through FastAPI's `fastapi_middleware_astack`, as FastAPI closes its own `Form()` and `File()` bodies, so an upload stays readable in the endpoint and its temporary file is released afterwards. A multipart route must have exactly one body parameter: FastAPI cannot embed a form body under several parameter names, so a second `Validated[...]` or a `Body()` parameter makes it answer 422 `Field required` before the dependency runs (see [ADR 076](076-harden-validated-multipart-bodies.md)). An unparseable multipart body is a 400, empty file inputs are dropped, and the whole body is buffered in memory, as ADR 076 records. JSON bodies, query methods and failure rendering are unchanged: a failure still raises `ValidationException`, which renders the 422 for JSON clients and redirects browsers back with session errors.

File rules follow Laravel:

- `Field().file()` passes only for an `UploadFile`.
- `Field().extensions([...])` checks the file name's extension, case-insensitively, with or without a leading dot.
- `min`, `max` and `between` measure an upload in kilobytes, with `file` messages ("must not be greater than :max kilobytes").
- An upload with an empty file name, which browsers send for an empty file input, counts as empty, so `required` fails and optional rules skip it.

The required-field JSON schema now renders the inner schema through `handler.generate_json_schema.generate_inner(schema)`, which applies the inner schema's own JSON schema hooks, so a required `UploadFile` is documented as `{"type": "string", "format": "binary"}`.

## Implementation

- `validation/form_request.py`: `declares_upload(annotation, upload)`, `MULTIPART` and `is_multipart(request)`; for a request with an upload field the `Validated` dependency maps `await request.form()` through `query_input` and closes the form after the response. `query_input` accepts `FormData` as well as `QueryParams`.
- `validation/rules.py`: `is_upload`, `File`, `Extensions`, upload sizes in `size_of`, `file` messages on `Min`, `Max` and `Between`, and empty uploads in `is_empty`. Starlette is imported lazily, so validation still works without the `fastapi` extra.
- `validation/field.py`: `file()` and `extensions()`, and the JSON schema fix.

Out of scope: content sniffing (`mimes`), image dimensions, and documenting a multipart request body in OpenAPI; a form route is still documented with its JSON body.

## Validation

- `tests/validation/test_fastapi_validation.py`: a multipart request with fields, a list field and a file reaches the endpoint; extension, size and required-file failures return 422 with field errors; a browser failure redirects back with 303; optional and list uploads work with no setup; an upload request still accepts JSON and refuses urlencoded bodies; a cross-site urlencoded or multipart `POST` to a request without an upload field still fails with 422; `declares_upload` detects plain, optional, list and `Annotated` uploads; uploads stay open in the endpoint and are closed after the response; OpenAPI documents a required upload as binary.
- `tests/validation/test_rules.py`: `File`, `Extensions`, kilobyte sizes and empty uploads.
- The full suite (Postgres and MySQL ignored), `uv run ruff check .` and `uv run pyrefly check` pass.
