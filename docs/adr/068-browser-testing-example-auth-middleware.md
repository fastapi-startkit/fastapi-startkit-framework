# 068. Guard dependency for authenticated pages in the browser-testing example

Date: 2026-11-07

## Problem

The dashboard's `index` action checks `await AsyncAuth.user()` itself and redirects guests to `/login`. Every protected page would repeat that check, and forgetting it leaves a page open. Since PR #39, fastapi-startkit-auth's `main` makes `Auth.guard(name)` a FastAPI dependency. It resolves the user through the named guard and raises `AuthenticationException` (401 JSON) when there is none. That error is right for an API but not for a page a browser navigates to.

## Alternatives

1. **Keep the check in each controller.** Easy to forget, and it mixes access control into rendering.
2. **A hand-written `authenticate` dependency in the app.** Duplicates what `Auth.guard` already does.
3. **`Depends(Auth.guard("web"))` on the protected router, with an app exception handler that turns the guard's `AuthenticationException` into a redirect for page requests.** This works like Laravel's `auth` middleware and its `unauthenticated` redirect.

## Decision

Option 3.

- `pyproject.toml` takes `fastapi-startkit-auth` from its git `main` until a release includes the guard dependency.
- `routes/web.py` keeps register, login and logout on the guest `router`. `/dashboard` moves to `authenticated = Router(dependencies=[Depends(Auth.guard("web"))])`, and `FastAPIProvider` includes both routers.
- `app/exceptions/unauthenticated.py` handles `AuthenticationException`:
  - Inertia requests (`X-Inertia`) and requests accepting `text/html` get a `303` to `/login`.
  - Every other caller gets the auth package's JSON error.
- Starlette resolves handlers through the exception's MRO, so this handler wins over the package's `AuthException` handler whatever the order of registration.
- The dashboard's `index` drops its own check.
- Controllers are modules of async functions rather than classes (`app/http/controllers/login_controller.py` defines `create`, `store`, `destroy`). Routes import the module and register its functions (`router.get("/login", login_controller.create)`). A class added nothing: no state and no constructor dependencies, and every route needed an instance first. `Router.resource` already accepts a module.
- The routes stop passing `response_model=None`. The controllers return `Response` subclasses (`InertiaResponse`, `RedirectResponse`) or are unannotated, so FastAPI infers no response model either way.

## Validation

The example's browser tests pass:

- `test_user_can_log_out` visits `/dashboard` after logging out and lands on `/login`.
- `test_guests_are_redirected_to_login` does the same for a guest who never signed in.
