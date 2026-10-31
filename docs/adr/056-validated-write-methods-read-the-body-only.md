# 056. `Validated` write methods read the body only, with an opt-in query merge

Date: 2026-10-31

Amends [ADR 053](053-validated-reads-query-and-body.md).

## Problem

Since ADR 053, `Validated[Model]` merges the query string into the input of every request that has a JSON body, on every method. Two consequences on write methods:

- **Secrets in URLs.** `POST /login?password=secret` with `{"email": "a@b.c"}` validates. The client learns that the URL is an accepted channel, and the password ends up in access logs, proxy logs and browser history.
- **Mass assignment from the URL.** `PATCH /profile?role=admin` with `{"name": "n"}` validates with `role == "admin"` and `role` in `model_fields_set`, so `update(data.model_dump(exclude_unset=True))` writes it. ADR 053 asked developers to keep sensitive fields off such models, which is easy to forget. The PR #336 review flagged it.

Write payloads belong in the body. The query string is the natural input of safe methods, where ADR 053 keeps working well.

## Alternatives

1. **Keep the merge, document the risk (ADR 053).** Safe only when every model is written with the risk in mind.
2. **Drop query input on write methods with no way back.** Breaks applications that rely on Laravel's `$request->all()` parity, for example a `POST /search?page=2` with filters in the body.
3. **Body only on write methods by default, with a class-level opt-in.** A `FormRequest` that wants the merge says so once, next to its fields. Per-request control is already possible with `prepare_for_validation`, so no extra hook is needed.
4. **A per-request hook (`merges_query(request) -> bool`).** More API for a rare need that `prepare_for_validation` covers.

## Decision

Option 3.

- **Safe methods** (`GET`, `HEAD`, `OPTIONS`) keep ADR 053's behaviour: the query input alone without a body, `{**query, **body}` with an object body.
- **Body-less `DELETE`** keeps reading the query input. A `DELETE` with a body is a write and reads the body only.
- **Write methods with a body** (`POST`, `PUT`, `PATCH`, a `DELETE` with a body, and any other method) validate the body alone. Query keys are ignored, so they never reach `model_fields_set`.
- **Opt-in:** `merge_query: ClassVar[bool] = False` on `FormRequest`. With `merge_query = True`, write methods validate `{**query_input, **body}` (the body wins on a clash), as ADR 053 did. The name says what happens (the query is merged under the body) and follows the existing `stop_on_first_failure` class setting. `query_on_write` and `accepts_query` were rejected: the first hides that the body wins, the second suggests the query is accepted alone.
- **Per request:** `prepare_for_validation` receives the `Validator` with the request, so a model can merge the query only when it wants: `validator.data = {**cls.query_input(validator.request.query_params), **validator.data}`.
- **Embedded models.** With several body parameters, a model whose embed key is absent or `null` in a present body validates an empty object on write methods, so its `required` rules report under its prefix (`search.term`). With `merge_query = True`, or on a safe method, it reads the query input as before.
- Unchanged: a body-less write method still reports `"": ["Field required"]` (per embed key when embedded) before `authorize` runs, so the CSRF protection of ADR 053 stands. A non-object body (a list, a string, a JSON `null`) still fails with `model_type` under `""`. Aliases, repeated keys for sequences, the error shapes and the OpenAPI query parameters of query methods are unchanged.

### Implementation

- `form_request.py` adds `SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}`. `QUERY_METHODS` (safe methods plus `DELETE`) still decides which body-less requests read the query.
- `FormRequest.request_input(params, body=ABSENT, *, method)` takes the HTTP method as a required keyword. Without a body it returns `query_input`. A non-object body passes through. An object body is merged with the query input when `merge_query` is set or the method is safe, and returned alone otherwise. The keyword is required so a direct caller cannot fall back to the merge by accident.
- The `Validated` dependency passes `request.method` and turns a missing or `null` embed key in a present body into `{}`.
- `document_query_input` is unchanged. Write methods never listed query parameters. With `merge_query = True` the merged fields are still documented only by the body schema.

### Behaviour changes

- `POST`/`PUT`/`PATCH` (and a `DELETE` with a body) no longer read the query string unless the model sets `merge_query = True`. A field sent only in the URL is now missing: a required field reports its `required` message, an optional field keeps its default.
- On those methods, an embedded model whose key is absent from the body no longer reads the query; it reports its `required` rules.

## Validation

`tests/validation/test_fastapi_validation.py` covers: `POST`, `PUT` and `PATCH` with a JSON body and query parameters ignoring the query by default; the same routes with a `merge_query` model merging the query with the body winning; `model_fields_set` without query keys on a `PATCH`; a `DELETE` with a body reading the body only; `GET` still reading the query and merging it with a body; the per-request merge in `prepare_for_validation`; an embedded model with an absent key on a `POST` reporting its `required` rules by default and reading the query when it opts in. The body-less CSRF tests, the non-object body tests and the OpenAPI tests of ADR 053 still pass. The full framework suite passes with coverage above the threshold, and `ruff` and `basedpyright` are clean.
