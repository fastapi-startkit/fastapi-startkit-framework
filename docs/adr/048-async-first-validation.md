# 048. Async-first validation: one awaited rule pass, async hooks and closures

Date: 2026-10-30

Supersedes the "Pydantic schema and short-circuit", "Async phase for database rules" and the dependency part of "FastAPI integration" in [ADR 042](042-fluent-validation-rules.md). The rule builder, messages, `MessageBag` and `ValidationException` from ADR 042 are unchanged, and so is ADR 042's 422 body, which is not the body on `main` (see [Response shape](#response-shape)).

## Problem

ADR 042 split validation in two. Synchronous rules ran inside pydantic's `model_validator`, and `AsyncRule`s ran in a second phase, `await model.validate_async(context)`, only after the whole synchronous phase passed. The framework is async-first (async ORM, async providers), and the split leaks into every use:

- The core entry point is synchronous. Anything that needs I/O (a database lookup, the current user, a remote check) can only be a separate `AsyncRule` in a separate phase, so a chain like `Field().required().unique("users").min(3)` does not run in the order it is written: `unique` always runs last, after every field's sync rules.
- There are no FormRequest hooks. Laravel's `authorize`, `prepareForValidation` and `after` callbacks have nowhere to run: the synchronous phase cannot await, and the async phase runs after the model is already built, too late to authorize or to normalise input.
- A rule cannot be a plain function, sync or async. Every check needs a `Rule` or `AsyncRule` subclass.
- Errors from the two phases are reported separately. A request with a bad `username` and a taken `email` reports only `username`, then `email` on the next attempt.

## Alternatives

1. **Sync core with an async adapter (ADR 042).** Pydantic stays the engine for sync rules and an async phase is bolted on. It keeps `model_validate` validating rules, but hooks cannot be async, rule order is not the written order, and every new async feature needs another phase.
2. **Dual sync and async API.** `model_validate` runs every rule, `await validate_input` runs every rule and hook, and async rules raise in the sync path. Every rule, hook and closure needs two code paths and two test matrices, and the sync path either rejects async rules at runtime or silently skips them. Running async rules from the sync path would need `asyncio.run` or a nested loop, which blocks or fails inside a running loop.
3. **Async-only rule engine, pydantic for types only.** Pydantic parses and coerces the input. One awaited pass runs every rule of every field in written order, awaiting a rule's result only when it is awaitable, so sync rules need no boilerplate. Hooks and closures may be sync or async.

## Decision

Option 3. Validation has one entry point, `await Model.validate_input(data, context=None, request=None)`, used by `Validated[Model]`, commands, jobs and tests. Pydantic construction (`Model(...)`, `model_validate`, a plain `data: Model` FastAPI body) only parses types and no longer runs rules.

### The awaited pass

`validate_input` creates a `Validator` for the call (`data`, `context`, `request`, `errors: MessageBag`). Nothing is stored on the class, so concurrent requests validate independently.

1. `await cls.authorize(validator)`. A false result raises `AuthorizationException` (403, "This action is unauthorized.") before the input is read.
2. Input that is not a mapping is parsed by pydantic and its errors are raised as `ValidationException` (the `model_type` error, as before).
3. `await cls.prepare_for_validation(validator)` may change `validator.data` (`validator.merge({...})`), for example to trim or lower-case input.
4. Pydantic parses the prepared data. Missing keys of `required`/`required_if` fields are filled with `None` first, so the rule's message is reported instead of pydantic's `Field required`. Pydantic's type errors are added to the bag. The coerced values of the fields that did parse are recorded through the validation context, so the rest of the request is still checked.
5. `validator.data` becomes the context, then the field defaults, the raw input and the coerced values, in that order. Every field with rules is then checked in declaration order, so cross-field rules see fields declared later. Within a field, rules run in the order they are written. A rule's result is awaited only if it is awaitable. An empty value skips non-implicit rules, and the first failing rule stops the field (Laravel `bail`). A field with a type error runs no rules. With `stop_on_first_failure = True` on the model, no further field is checked after the first error, which keeps invalid input away from later database rules.
6. `await cls.after(validator)` runs last and can add errors (`validator.errors.add(field, message)`) using the validated data.
7. If the bag has errors, `ValidationException(bag)` is raised. Otherwise the parsed model is returned.

Hooks are classmethods with defaults that do nothing. Each may be a plain or an `async` method; the engine awaits the result only when it is awaitable. Fields are checked one after another, not with `asyncio.gather`, because database rules on one request share the task's connection and the error order must follow the declaration order.

### Rules and closures

`BaseRule.passes` returns `bool | Awaitable[bool]`. `Rule` (sync) and `AsyncRule` (async) stay as typed bases for custom rules, but the engine treats both the same way, so `unique` and `exists` sit in the chain where they are written. `Field().using(callback, msg=None)` adds a closure rule: `callback(attribute, value, data)` returns a `bool` or an awaitable `bool`. `unique(..., ignore=...)` also accepts an async callable. `unique` and `exists` still use the async `QueryBuilder` (`where(...).exists()`), so no request blocks the event loop and no sync database access exists in the request path.

### Pydantic schema

`Field.__get_pydantic_core_schema__` is unchanged: `required`/`required_if`/`nullable` accept `None` at the type level and the JSON schema of a `required` field stays non-nullable. The `FormRequest` wrap `model_validator` only marks the scope (so `Field` on a plain `BaseModel` still raises `TypeError`) and records coerced values. It no longer fills missing keys or runs rules. Rules on nested models still raise `TypeError` at class definition.

### FastAPI integration

`Validated[Model]` is still `Annotated[Model, Depends(dependency)]`, and the dependency still reads the route's typed path parameters as context (ADR 042). FastAPI no longer parses the body into the model. The dependency's body parameter is `Annotated[Any, RawInput(Model), Body()]`. `RawInput` gives it a pass-through core schema whose `json_schema_input_schema` is the model's schema, so OpenAPI still shows `$ref: Model` and the embed key under other body parameters is unchanged. The dependency then returns `await Model.validate_input(body, context, request)`. Type errors and rule errors are now reported together in one 422. If a declared path parameter is invalid, the dependency returns `None` without validating, and FastAPI reports its own path 422 before the endpoint runs.

### Several `Validated` parameters on one route

When a route has more than one body parameter, or one declared with `Body(embed=True)`, FastAPI embeds each body under its parameter name. For `Validated` that name is the snake-cased model name (ADR 042), so `async def checkout(billing: Validated[Billing], shipping: Validated[Shipping])` expects `{"billing": {...}, "shipping": {...}}`. Each `Validated` parameter is its own dependency, so before this change the first failing model raised immediately: the second was never validated, and the errors were keyed by the model's field names (`name`), so two models with the same field could not be told apart.

Per route (cached with the path parameters, keyed by `id(route)`), the dependency now records whether the body is embedded (FastAPI's own rule: more than one distinct body parameter name across the dependency tree, or an `embed` body) and which `Validated` dependency FastAPI calls last (post-order over `dependant.dependencies`, the order `solve_dependencies` calls them). Each `Validated` dependency validates its model and merges any errors into a `MessageBag` kept in the request scope, prefixed with its embed key when the body is embedded (`billing.name`, `shipping.name`, the same dotted keys FastAPI's own embedded errors get). Only the last one raises `ValidationException` with every recorded error, so all models are validated and reported in one 422. A non-embedded single `Validated` body keeps unprefixed keys.

FastAPI does not call a dependency whose own parameters failed (for example a missing `shipping` key), and then raises `RequestValidationError` instead. `ValidationExceptionHandler` therefore merges the errors recorded in the request scope in front of FastAPI's own errors, so `{"billing": {"name": "a"}}` returns both `billing.name` and `shipping`. This needs `FastAPIProvider`'s handler; with FastAPI's default handler only FastAPI's errors are returned. Errors of the endpoint's own non-`Validated` parameters are checked by FastAPI after the dependencies run, so they are not added to a 422 already raised by the last `Validated` dependency.

Alternatives considered: one `Validated` per route only (documented limitation), which leaves the collision for any route that needs two payloads; and a custom `APIRoute` class that validates every model before the endpoint, which only works for routers that opt in (as ADR 042 found for path parameters).

### Response shape

The 422 body is ADR 042's, and it differs from `main`. For apps that register `FastAPIProvider`, `ValidationExceptionHandler` renders both `RequestValidationError` (FastAPI's own type and path errors, including routes that do not use `Validated`) and `ValidationException` as:

```json
{"message": "The name field must be at least 3 characters. (and 1 more error)", "errors": {"billing.name": ["..."], "shipping.name": ["..."]}}
```

On `main` the body is `{"errors": {...}}`. The `errors` mapping keeps its keys and lists, and `message` is a new key, so clients that read `errors` keep working, but clients or tests that compare the whole body see the extra key. Inertia and session redirects are unchanged, because they only use `errors`. Apps without `FastAPIProvider` keep FastAPI's default `{"detail": [...]}`.

A plain `data: Model` body parameter only parses types. Validation that should run rules goes through `Validated[Model]` or `await Model.validate_input(...)`. This replaces ADR 042's "a plain body runs only the sync phase", which half-validated without saying so.

`validate_async` is removed. The PR has not been released, so there are no callers to keep working.

## Validation

- `tests/validation/test_form_request.py`: sync rules, custom `Rule`/`AsyncRule`, sync and async closures, written order of mixed sync and async rules, type errors combined with rule errors, cross-field rules regardless of declaration order, non-mapping input, `stop_on_first_failure`, sync and async `authorize` (403), `prepare_for_validation`, `after` adding errors, `model_validate` parsing types only, and two concurrent `validate_input` calls with different inputs and contexts that keep their own errors.
- `tests/validation/test_database_rules.py` and `test_validated_database.py`: `unique`/`exists` against SQLite through the async ORM in the same pass as sync rules, an async `ignore` callable, and the typed path parameter bound as `int`. `tests/masoniteorm/postgres/test_validated_unique.py` keeps the asyncpg case.
- `tests/validation/test_fastapi_validation.py`: the 422 body for sync, async and combined failures, two `Validated` models with the same field name reported together under `billing.name`/`shipping.name`, a missing embedded body merged with the other model's rule errors, the embedded OpenAPI schema for two models, the `update_user.` prefix next to another body parameter, a 403 from an async `authorize` that reads the request, OpenAPI `$ref` and embed key, path-parameter context, an invalid path parameter that never reaches rules, and a plain body that only parses types.
- A grep shows no `asyncio.run`, `run_until_complete` or sync database call in `fastapi_startkit/validation`.
- `uv run pytest --ignore=tests/masoniteorm/postgres --cov` passes with total coverage at least `fail_under`, and `ruff check`, `ruff format --check` and `basedpyright` are clean for the changed files.
