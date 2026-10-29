# 042. Fluent validation rules with an async phase and a Laravel 422 shape

Date: 2026-10-29

## Problem

Request models are plain pydantic models. Pydantic covers types, but Laravel-style rules (`required`, `min:3`, `same:password`, `required_if:is_business,true`, `unique:users,email,{id}`) need hand-written validators, and their error messages do not follow one shape. Three things do not fit pydantic directly:

- `unique` and `exists` query the database. Pydantic validators are synchronous and the ORM is async. Calling `asyncio.run` or a nested loop inside a validator would block the event loop or fail inside a running one.
- Cross-field rules (`same_as`, `required_if`) read other fields through `info.data`, which only holds the fields declared before the current one.
- A missing optional field must not run `min`/`max`, and a failing `required` must not also report `min`/`max`.

## Alternatives

1. **Pydantic `Field` constraints and `field_validator`/`model_validator` only.** No new API, but every message, cross-field rule and database check is hand-written per model, and database checks still have no async place to run.
2. **A string-rule DSL (`"required|email|max:255"`).** Familiar from Laravel, but rules are untyped strings parsed at runtime, custom messages and custom rule classes need a second mechanism, and typos are only found when a request arrives.
3. **A separate `Validator(data, rules)` class.** Async-friendly, but the rules live away from the model, the model's types and the rules can drift, and the request body would be parsed twice.
4. **A fluent builder used as `Annotated` metadata on a pydantic model**, with the synchronous rules running during pydantic validation and the async rules in a second awaited phase.

## Decision

Option 4, in a new `fastapi_startkit.validation` package that depends only on pydantic. The ORM and FastAPI are imported lazily, only by the rules and the dependency that use them.

```python
from typing import Annotated
from fastapi_startkit.validation import Email, Field, FormRequest, Validated

class RegisterUser(FormRequest):
    email: Annotated[str, Email().required().unique("users")]
    username: Annotated[str, Field().required().string().min(3).max(10)]
    password: Annotated[str, Field().required().password()]
    password_confirmation: Annotated[str, Field().required().same_as("password")]
    is_business: bool = False
    tax_id: Annotated[str | None, Field().required_if("is_business", True)] = None

@router.post("/register")
async def register(data: Validated[RegisterUser]): ...
```

### Rules and the builder

- `Rule` (sync, `passes(attribute, value, data) -> bool`) and `AsyncRule` (`async passes(...)`) share `BaseRule`, which holds the message. Custom rules subclass one of them and set `message`. A rule with `implicit = True` also runs on empty values (`required`, `required_if`).
- `Field()` is the builder. Every method appends a rule and returns the builder: `required`, `nullable`, `string`, `integer`, `numeric`, `boolean`, `min`, `max`, `between`, `email`, `url`, `regex`, `in_`, `not_in`, `same_as`, `confirmed`, `required_if`, `password` (`min(8)`), `unique`, `exists`, `add(rule)` and `msg(message)` (replaces the message of the last rule). `Email()` is a `Field()` that starts with the `email` rule.
- `min`/`max`/`between` measure string and list length, and numeric value, with Laravel's per-kind messages. When the chain also has `numeric` or `integer`, they compare the numeric value, so `Field().numeric().max(10)` rejects `"25"` on a `str` field (Laravel's `getSize`).
- `in_`/`not_in` treat an unhashable value (a list or dict checked against a set) as not in the collection, so it is a validation error, not a `TypeError`.
- Messages are a string or a callable `(field, value, data) -> str`. In strings, `:attribute` becomes the humanized field name (`password_confirmation` → `password confirmation`), and each rule adds its own placeholders (`:min`, `:max`, `:other`, `:value`). Booleans render in lowercase, so `required_if("is_business", True)` reads "... when is business is true."

### Pydantic schema and short-circuit

`Field.__get_pydantic_core_schema__` keeps the annotated type's schema. When the chain contains `required`, `required_if` or `nullable`, `None` is accepted at the type level. For `required`/`required_if` fields, `FormRequest`'s wrap `model_validator` fills a missing key with `None` before pydantic runs, so a missing key reaches the rule and gets the rule's message instead of pydantic's `Field required`, and the field stays required in the OpenAPI schema. For `required` fields without `nullable`, the JSON schema shows the plain annotated type rather than `anyOf [type, null]`, because a `null` is always rejected by the rule. Without those rules the annotation is enforced as plain pydantic, so `Annotated[str, Field().max(3)]` still rejects `None`.

Rules do not run per field. A wildcard `field_validator` on `FormRequest` records every field's coerced value in a `ContextVar` opened by the wrap validator. After pydantic has validated every field, the wrap validator runs the synchronous rules of every field in declaration order against the whole model (`dict(instance)`). If pydantic reported type errors, the rules still run for the other fields, against the field defaults, then the raw input, then the recorded coerced values. Input that is not a mapping only reports pydantic's type error, because no field values exist to check. This removes the declaration-order problem: `same_as` and `required_if` see fields declared later. Within a field:

- An empty value (`None`, `""`, `[]`, `{}`) skips every non-implicit rule, so a missing optional field never runs `min`/`max`.
- The first failing rule stops the field (Laravel `bail`), so a failing `required` does not also report `min`.
- A field with a pydantic type error runs no rules.

Rule failures and pydantic's own errors are raised together as one `ValidationError`, so FastAPI turns them into a single `RequestValidationError`. `Field` metadata on a plain `BaseModel` raises `TypeError` when a value is validated, because the rules would silently never run. Inside a `FormRequest` the outer model's `ContextVar` hides that check for nested models, so `FormRequest.__pydantic_init_subclass__` raises `TypeError` when a field's annotation (including `list[...]`, `X | None` and other generic arguments) contains a model with `Field` rules. Nested rules with dotted keys stay a follow-up. Raising keeps the guarantee that rules never silently fail to run.

### Async phase for database rules

`AsyncRule`s (`unique`, `exists`, custom ones) never run inside pydantic. `await model.validate_async(context)` runs them after the model is built, in declaration order, with the same empty-value and bail behaviour, and raises `ValidationException` with a `MessageBag`. It only runs when the synchronous phase passed, so invalid input does not reach the database.

- `unique(table, column=None, ignore=None, ignore_column="id")` and `exists(table, column=None)` take a table name (queried through `DB.table`) or a `Model` class (`Model.query()`), and use the async `QueryBuilder` (`where(...).exists()`). `column` defaults to the field name.
- `ignore` is a value or a callable receiving the validation data. The data is the model's fields over the `context` mapping. `Validated[...]` passes the route's typed path parameters as context, so an update route `PUT /users/{user_id}` uses `unique("users", ignore=lambda data: data["user_id"])`, which is Laravel's `unique:users,email,{id}`.
- `await RegisterUser.validate_input(data, context=None)` runs both phases outside FastAPI (commands, jobs, tests) and raises `ValidationException` for either phase.

### FastAPI integration

`Validated[Model]` is `Annotated[Model, Depends(dependency)]`, where the dependency takes `request: Request` and the body as `Model`. FastAPI parses the body (the OpenAPI schema is kept), the sync phase runs, then the dependency awaits `validate_async(context)`. A body parameter typed as the plain model still works but runs only the sync phase.

FastAPI solves sub-dependencies before it validates the endpoint's own path parameters, and `request.path_params` only holds strings. Passing those strings made `unique(..., ignore=lambda data: data["user_id"])` bind `'1'` against an integer column, which asyncpg rejects with a `DataError` (a 500; SQLite hides it through type affinity), and `PUT /users/abc` queried the database before the `user_id: int` error was reported. The dependency now reads the matched `APIRoute` from `request.scope["route"]` and converts the raw values with FastAPI's own `request_params_to_args` over every path parameter declared on the route (`get_flat_dependant(route.dependant).path_params`). The context is the converted values over the raw ones, so undeclared path parameters stay strings. If any declared path parameter is invalid, the dependency returns the model without running the async phase, and FastAPI then reports its normal path-parameter 422 when it validates the endpoint. Alternatives considered: coercing in user code (`int(data["user_id"])`) moves the bug to every caller and still queries with invalid input; a custom `APIRoute` class only covers routers that use it, so async rules would silently not run elsewhere.

The dependency's body parameter is named after the model in snake case (`UpdateUser` → `update_user`). With a single body parameter the name is invisible because FastAPI does not embed the body. When the endpoint has other body parameters, FastAPI embeds each body under its parameter name, and for `Validated` that is the dependency's parameter, not the endpoint's: FastAPI builds a dependency's signature without the name of the parameter that declares it, so the endpoint's name cannot be used. `async def note(data: Validated[UpdateUser], note: Annotated[str, Body()])` therefore expects `{"update_user": {...}, "note": "..."}`, and OpenAPI shows the same keys. Naming the key after the model (instead of a fixed `payload`) keeps it predictable and lets two different `Validated` models on one endpoint coexist. An endpoint that needs its own key can declare `data: Model` and call `await data.validate_async(context)`.

The response comes from the existing `ValidationExceptionHandler` that `FastAPIProvider` registers for `RequestValidationError` (ADR 017, ADR 037). `fastapi_startkit.exceptions` already had an unused `ValidationException(errors: dict)`. It is reused instead of adding a second class with the same name: it now subclasses the dependency-free `HttpException` (status 422, `get_response()` is the summary), accepts a `MessageBag` or a `{field: [messages]}` mapping, and keeps `errors` as that mapping. A string value counts as one message, so the old call shape `ValidationException({"email": "Taken."})` still gives `{"email": ["Taken."]}`. `fastapi_startkit.validation` re-exports it. `FastAPIProvider` registers the same handler for it, so the async phase gets the same JSON, Inertia and session-redirect negotiation. The JSON body becomes `MessageBag.to_dict()`:

```json
{"message": "The username field is required. (and 2 more errors)", "errors": {"username": ["..."], "email": ["..."]}}
```

This is scoped to apps that register `FastAPIProvider`. They already get `{"errors": {...}}` instead of FastAPI's default `{"detail": [...]}` body, and this change only adds the `message` key. FastAPI's default handler, and apps without `FastAPIProvider`, are not touched.

### Out of scope (follow-ups)

Docs page; `sometimes`, `array`, `date`/`before`/`after`, `alpha`/`alpha_num`, `digits`, `size`, `different`, `required_with`/`required_without`, `prohibited`, `file`/`image`/`mimes`; rules on nested models and list items with dotted keys; `Field` combined with the form-encoded `RequestModel`; alias-aware error keys; per-rule database connection; translated messages.

## Validation

- `tests/validation/` covers each rule's pass and fail cases, default, string and callable messages, `msg()`, `:attribute` humanization, empty-value skipping and bail, `same_as`/`required_if`/`confirmed` regardless of declaration order, type errors combined with rule errors, `TypeError` on a plain `BaseModel`, `MessageBag`, custom `Rule`/`AsyncRule` subclasses, and `unique`/`exists` against SQLite through the async ORM (table name and `Model`, with and without `ignore`).
- A FastAPI app with `FastAPIProvider` checks the 422 body for sync and async failures, the path-parameter `ignore` on an update route (the context holds the typed `int`), an invalid path parameter that returns the path error without running async rules, a multi-body endpoint with the model-name embed key, and a successful request.
- A real `unique(..., ignore=lambda data: data[...])` through `Validated` runs against SQLite with the bound query parameter asserted to be an `int`, and against Postgres (asyncpg) in `tests/masoniteorm/postgres/test_validated_unique.py`, where the old string context failed with `DataError`. An invalid path parameter never reaches the database.
- Rules on a nested model (direct, `list[...]`, optional) raise `TypeError` at class definition; `in_` with unhashable values, string messages in `MessageBag`, lowercase boolean placeholders, numeric `max`, plain JSON schema for required fields, and non-mapping input are covered.
- Existing `ValidationExceptionHandler` tests are updated for the added `message` key.
- 100% coverage of `fastapi_startkit/validation`, total coverage at least 80%, `ruff check`, `ruff format --check` and `basedpyright` clean for the new files.
