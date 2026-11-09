# 076. Harden `Validated` multipart bodies

- Date: 2026-11-09
- Status: Accepted
- Amends: [075](075-validated-form-and-multipart-bodies.md)

## Problem

The post-merge review of ADR 075 (PR #364) and the docs check against v0.75.1 found these gaps in how `Validated` reads multipart bodies:

1. A malformed multipart body on an upload route returned 500. `validated_dependency` called `await request.form()` without a guard. Starlette turns only its own `MultiPartException` (for example a missing boundary) into a 400, so python-multipart's `MultipartParseError` escaped. FastAPI's own `File()`/`Form()` path returns `400 "There was an error parsing the body"`. Any anonymous client could trigger a 500 on every upload route.
2. A route with more than one body parameter, such as `Validated[Upload]` with another `Validated[...]` or with a `Body()` parameter, cannot read multipart. FastAPI embeds the body under each parameter's name and needs a mapping. It receives bytes, reports `Field required` for every embed key, and never calls the dependency. The `embedded and not form` branch in the dependency could never run.
3. `is_multipart` lower-cased the media type, but Starlette compares `b"multipart/form-data"` exactly. With `Content-Type: Multipart/Form-Data`, the dependency took the form branch, Starlette returned an empty `FormData`, and the client got a misleading `title: Field required`.
4. The dependency declares `Body()`, so FastAPI reads the whole request body into memory before `request.form()` spools uploads to temporary files.
5. ADR 075 said a form body sent to a request without an upload field fails "before `authorize`". `validate_input` calls `authorize` first, so it can return 403 before the 422.
6. `declares_upload` treated `dict[str, UploadFile]` as an upload. That opened the multipart surface for a field a flat form can never fill. The status codes for an unreadable body were also inconsistent: missing boundary 400, malformed 500, wrong content type 422.
7. A browser sends an empty file input as a part with `filename=""`. It arrived as a truthy `UploadFile`, not `None`, so `if data.cover:` was true for an optional upload that the user never chose.
8. Annotating a field with `starlette.datastructures.UploadFile` raises `PydanticSchemaGenerationError`. Only `fastapi.UploadFile` defines a pydantic schema.

## Alternatives

- **Malformed body: 422 `ValidationException`.** It would redirect browsers back with an error under `""`. A body that cannot be parsed is a broken client, not a user input error, and FastAPI and Starlette both answer 400. Rejected.
- **Malformed body: catch only python-multipart's `FormParserError`.** Narrower, but FastAPI catches every non-HTTP exception from form parsing. Matching it keeps an upload route the same as a `File()` route if the parser raises something else. Rejected.
- **Several body parameters: support multipart.** FastAPI parses the body and resolves embedded body fields before it calls any dependency. Supporting it would mean declaring the body as something other than `Body()` for upload requests. ADR 075 rejected that because FastAPI then refuses JSON. Rejected.
- **Several body parameters: raise at route registration.** `Validated[...]` builds its dependency before FastAPI knows the route, so it cannot see the other parameters. A route check would need a custom `APIRoute`. Rejected for now.
- **Media type: compare case-insensitively and parse the form ourselves.** RFC 9110 media types are case-insensitive, but a second form parser next to Starlette's would duplicate limits and closing. Rejected.
- **Wrong content type: 415.** A request without an upload field already answers 422 for any non-JSON body (ADR 053), and the 422 goes through `ValidationException`, which redirects browsers back. A 415 only on upload routes would split one behaviour in two. Rejected.
- **Body size limit in the dependency.** FastAPI has already read the body by the time the dependency runs, so a limit there saves no memory. A safe limit needs ASGI middleware that counts the streamed bytes before FastAPI reads them, which is a separate feature. Rejected for this change.
- **Support `starlette.datastructures.UploadFile` annotations.** It would need a pydantic schema hook added to Starlette's class, or a rewrite of annotations, in framework code. `fastapi.UploadFile` is a subclass, behaves the same at runtime, and is what FastAPI documents. Rejected; documented as a limitation.
- **Empty file inputs: keep them and rely on the rules.** The rules already treat an empty file name as empty, but the model still holds a truthy `UploadFile`, and a `list[UploadFile]` gets one empty item. Rejected.

## Decision

- **Malformed bodies are a 400.** `form_input(request)` wraps `await request.form()`. Starlette's own `HTTPException`, such as `Missing boundary in multipart.`, is re-raised unchanged. Any other exception becomes `HTTPException(400, "There was an error parsing the body")`, as in FastAPI.
- **Status codes by cause.** A multipart body that cannot be parsed, malformed or missing a boundary, is a 400 from the HTTP layer. A body in an encoding the request does not accept (urlencoded, `text/plain`, or a mixed-case `Multipart/Form-Data`) is a 422 validation failure with an error under `""`, the same as on a JSON-only request. Rule failures stay 422.
- **One body parameter per multipart route.** A route that reads multipart through `Validated` must have exactly one body parameter: that `Validated[...]`. With a second `Validated[...]` or a `Body()` parameter, FastAPI answers 422 with `Field required` under each parameter's name, rendered by the framework's `RequestValidationError` handler. Browsers are still redirected back, but the form fields are never validated. JSON bodies on such routes work as before. The dead `not form` branch is removed.
- **Media type matches Starlette.** `is_multipart` uses python-multipart's `parse_options_header`, which Starlette uses, and compares the result to `b"multipart/form-data"` exactly. The dependency reads a form only when Starlette will parse one.
- **Only fillable uploads count.** `declares_upload` matches the upload class itself and looks only inside `Annotated`, unions and sequences (`list`, `tuple`, `Sequence`, `set`). `dict[str, UploadFile]` and other mappings do not make a request accept multipart.
- **Empty file inputs are dropped.** Before mapping, `form_input` removes every `UploadFile` part with an empty file name. An optional upload gets its default (`None`), a list upload gets `[]`, and a required upload fails `required` as before. The original form is still closed after the response.
- **Uploads are buffered in memory.** Because the dependency declares `Body()`, FastAPI reads the whole request into memory before Starlette spools file parts to temporary files. The framework sets no total body limit. Applications must limit request size at the proxy or server, for example nginx `client_max_body_size`. Starlette's own `form()` limits still apply: 1000 files, 1000 fields and 1 MiB per non-file part.
- **Annotate uploads with `fastapi.UploadFile`.** `starlette.datastructures.UploadFile` cannot be used as a field annotation because pydantic cannot build a schema for it. Values from the form are Starlette uploads and validate against the FastAPI annotation.
- **ADR 075 wording.** A form body sent to a request without an upload field reaches the model as raw bytes. `authorize` runs first and can answer 403. If it passes, the body fails with 422 before `prepare_for_validation` or the rules run.

## Implementation

- `validation/form_request.py`: `form_input(request)` parses the form, maps non-HTTP parse errors to 400, closes the form after the response and drops empty uploads. `is_multipart` uses `parse_options_header`, and `MULTIPART` is bytes. `declares_upload` recurses only through `Annotated`, unions and sequences. `embedded` no longer depends on the body being a form.
- `docs/adr/075-validated-form-and-multipart-bodies.md`: wording fixed for `authorize`, the multi-body sentence replaced by a link to this ADR, and limitations listed.

## Validation

- `tests/validation/test_fastapi_validation.py`:
  - a malformed multipart body returns `400 "There was an error parsing the body"`, and a missing boundary returns Starlette's 400;
  - `Multipart/Form-Data` is treated as a non-form body (422 under `""`), and `is_multipart` agrees with Starlette for each case;
  - empty file inputs give `None` and `[]` for optional and list uploads, and `required` for a required upload;
  - a multipart request to a route with a `Body()` parameter, or with two `Validated` parameters, returns 422 `Field required` under each parameter name;
  - `declares_upload` accepts tuple, `Sequence | None` and `Annotated` optional lists, and rejects `dict[str, UploadFile]` with or without `| None`.
- The full suite (Postgres and MySQL ignored), `uv run ruff check .`, `uv run ruff format --check .` and `uv run pyrefly check` pass.
