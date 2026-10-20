# 024. Installer controllers in their own module

- Date: 2026-10-19
- Status: Accepted

## Problem

`fastapi-startkit init` generates `HomeController` inside `routes/api.py`, next to the router. Route files then mix request handling with route registration, and the first controller a user adds has no obvious home. The Inertia PingCRM example keeps controllers under `app/http/controllers/` and route files only import and register them.

## Alternatives

1. **Keep the class in `routes/api.py`.** One file fewer, but the layout the user grows from differs from the examples and from where `make`-style commands would put new controllers.
2. **`controllers/home_controller.py` at the project root.** Short path, but diverges from the `app/http/controllers/` layout the examples already use.
3. **`app/http/controllers/home_controller.py`.** Matches PingCRM; routes import the class.

## Decision

Option 3. The generated controller stays a class (`HomeController` with `index` and `health`) and moves to `app/http/controllers/home_controller.py`. `routes/api.py` imports it, instantiates it once and registers its methods.

## Implementation

- New stubs `base/controller.py.stub` (JSON welcome) and `frontend/controller.py.stub` (Inertia `Home` page); the frontend section overrides the base one at the same path, as it did for routes.
- A single `base/routes.py.stub` replaces the two route stubs; it registers `/` with `response_model=None` so both the JSON and Inertia controllers work.
- `define_web()` adds empty `app/__init__.py`, `app/http/__init__.py` and `app/http/controllers/__init__.py`. Worker-only projects generate none of these.

## Validation

- Section tests check the controller path and that worker-only plans omit `app/`.
- The route binding test writes the rendered project to a temporary directory, imports `routes.api`, and checks `/` and `/health` are bound to one `HomeController` instance for no frontend, React and Vue.
- Generated-application tests (HTTP smoke test, Inertia response, combined web + worker) pass unchanged.
