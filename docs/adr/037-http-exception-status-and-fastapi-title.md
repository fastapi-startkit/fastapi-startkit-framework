# 037. HTTP exceptions keep their status, and the FastAPI title comes from config

- Date: 2026-10-25
- Status: Accepted

## Problem

1. Every `HTTPException` raised in a route was rendered as `500 {"message": "Server Error"}`. `FastAPIProvider` routed `HTTPException` through the exception manager to `HTTPExceptionHandler`, whose `render` always built a 500 response. `ModelNotFoundException` (and the other framework exceptions marked `is_http_exception`, such as `AuthorizationException`) fell through to the same 500 path. Because they only matched the bare `Exception` handler, Starlette served them from `ServerErrorMiddleware`, which re-raises after responding.
2. `/docs` showed the title `Jobins AI Agent (LangChain)`. That string was hard-coded in `FastAPIProvider.register`, but the instance was never used: `Application.__init__` reset `_fastapi` to `None` after `register_providers()`, so the lazy getter built a plain `FastAPI()` titled `FastAPI`. That reset also dropped any instance a provider passed to `use_fastapi` in `register`.

## Alternatives

- Duck-type on `is_http_exception` inside `HTTPExceptionHandler` only. This fixes the status code, but Starlette still dispatches these exceptions through `ServerErrorMiddleware`, which re-raises them as server errors.
- Have `DatabaseProvider` register a FastAPI handler for `ModelNotFoundException`. That couples the ORM provider to FastAPI and to the order in which providers run, and it leaves the other framework HTTP exceptions unhandled.
- Add a small, dependency-free `HttpException` base in `fastapi_startkit.exceptions` and register it with FastAPI as a dedicated handler (chosen).

## Decision

- New `fastapi_startkit.exceptions.HttpException(Exception)` with `is_http_exception = True`, `get_status()`, `get_response()` and `get_headers()` (which defaults to `None`). `RouteNotFoundException`, `MethodNotAllowedException`, `AuthorizationException`, `ThrottleRequestsException` and `masoniteorm.ModelNotFoundException` now subclass it. `ThrottleRequestsException` therefore returns 429 and passes on any headers it carries, such as `Retry-After`. Its `headers` default changes from a shared mutable `{}` to `None`.
- `HTTPExceptionHandler.report` skips client errors: a Starlette `HTTPException` or a framework `HttpException` with a status below 500. Everything else, including 5xx HTTP exceptions, goes to `exception_manager.report_exception`. This check lives in the FastAPI layer, not in the core `ExceptionHandler`. The core handler cannot import Starlette, and matching on a `status_code` attribute alone would also silence outbound client errors that carry one (for example SDK `APIStatusError`s), which are real server-side failures.
- `HTTPExceptionHandler.render` delegates any Starlette `HTTPException` (which covers FastAPI's subclass) to FastAPI's `http_exception_handler`. A framework `HttpException` is converted to a Starlette `HTTPException` built from its status, response and headers. The result keeps FastAPI's response shape: `{"detail": ...}`, the status code, and the headers. Any other exception still renders as the debug trace or `Server Error` with a 500.
- `FastAPIProvider` registers the handler on Starlette's `HTTPException`, not FastAPI's subclass, so routing 404s and 405s use the same path and carry the request-id header. It also registers the handler on `HttpException`.
- `FastAPIConfig.title = env("APP_NAME", "FastAPI Startkit")` sets the FastAPI title. `Application.__init__` now initialises `_fastapi` before `register_providers()`, so the instance a provider creates in `register` is kept.

## Validation

- `tests/fastapi/test_http_exception_rendering.py` uses `HttpTestCase` to check that:
  - `HTTPException(400, "Email taken")` returns 400 with `json()["detail"] == "Email taken"` and its custom header;
  - a Starlette `HTTPException(418)` keeps its status;
  - an unknown route returns 404 `Not Found`;
  - `ModelNotFoundException` returns 404 with its message;
  - `APP_NAME` sets the OpenAPI title;
  - the default title is `FastAPI Startkit`.
- `tests/fastapi/test_exceptions.py` covers:
  - `MethodNotAllowedException` (405 plus the `Allow` header);
  - `AuthorizationException` (403);
  - `ThrottleRequestsException` (429 plus `Retry-After`);
  - `report()` skipping 4xx Starlette/FastAPI/framework HTTP exceptions while still reporting a 503 `HTTPException` and a plain `RuntimeError`.
- The full suite runs with coverage of at least 80%. Ruff and basedpyright are clean on the changed files.
