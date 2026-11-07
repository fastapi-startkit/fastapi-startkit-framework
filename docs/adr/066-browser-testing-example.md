# 066. Browser-testing example app

Date: 2026-11-07

## Problem

ADR 065 needs a real app to show how browser tests are written. The example should be a normal Inertia app: register, log in, log out, and a page only signed-in users can see. It should be built the way the documentation tells users to build one, with no hand-written shortcuts:

- no `user_id` written into a signed cookie;
- no home-made password hashing;
- no `if`-chain validation;
- no auth check copied into every protected controller.

## Alternatives

1. **Hand-rolled sessions, hashing and checks.** No extra dependency, but it teaches a pattern that `docs/authentication.md` tells users not to write, and it skips CSRF.
2. **`fastapi-startkit-auth` with the in-memory session store.** Less setup, but sessions vanish on restart and the example would hide the `sessions` migration a real app needs.
3. **`fastapi-startkit-auth` with the database session store, `FormRequest` validation, and a route guard dependency for protected pages.** The protected pages get an app exception handler that sends guests to the login page.

## Decision

Option 3.

### Authentication

- **Config.** `config/auth.py` declares:
  - `AuthConfig`: guard `web`, a `SessionGuard` over an `async_model` provider for `User`;
  - `SessionConfig`: `driver="database"`, with `secure` taken from `SESSION_SECURE_COOKIE` (default `True`).

  `AuthProvider` and `AuthSessionProvider` are listed in `bootstrap/application.py`.
- **Sessions table.** The package's `sessions` migration is copied into `databases/migrations`.
- **Passwords.** They are hashed by a `Hashed` cast on `User.password` using the auth manager's bcrypt hasher, so the factory, registration and `AsyncAuth.attempt` agree.
- **Flashed errors.** Starlette's `SessionMiddleware` stays, because Inertia flashes validation errors into `request.session`.
- **CSRF.** No frontend change is needed: Inertia sends the `XSRF-TOKEN` cookie back as `X-XSRF-TOKEN`.
- **Logout.** `AsyncAuth.logout()` invalidates the session record, clears the request state and forgets the cookie. Login rotates the session id.

### Controllers and validation

- **Controllers are modules of async functions, not classes.** They hold no state and take no constructor dependencies, so routes register the functions directly, for example `router.get("/login", login_controller.create)`. `Router.resource` already accepts a module.
- **The modules:**
  - `register_controller`: `create`, `store`;
  - `login_controller`: `create`, `store`, `destroy`;
  - `dashboard_controller`: `index`;
  - `home_controller`: `index`, `health`.
- **Validation.** `RegisterRequest` and `LoginRequest` are `FormRequest`s injected with `Validated[...]`.
  - `RegisterRequest` checks that the email is unique in `users` and that the password has at least 8 characters.
  - A failure redirects back with Inertia errors.
- **Return types.** Actions are annotated with `Response` subclasses (`InertiaResponse`, `RedirectResponse`), so FastAPI builds no response model and the routes don't need `response_model=None`.

### Protected pages

- **Routers.** `routes/web.py` keeps register, login and logout on the guest `router`. `/dashboard` lives on `authenticated = Router(dependencies=[Depends(Auth.guard("web"))])`, and `FastAPIProvider` includes both.
- **Auth package source.** `Auth.guard(name)` became a FastAPI dependency in fastapi-startkit-auth PR #39, which isn't released yet. `pyproject.toml` takes the package from its git `main` until a release includes it.
- **Guest handling.** The guard raises `AuthenticationException` (401 JSON) for guests. `app/exceptions/unauthenticated.py` handles it:
  - Inertia requests and requests that accept `text/html` get a `303` to `/login`.
  - Every other caller gets the package's JSON error.

  Starlette resolves handlers through the exception's MRO, so this handler wins over the package's `AuthException` handler.

### Tests

- **Base class.** `tests/browser/test_case.py` defines the app's `TestCase(BrowserTestCase)`, returning `bootstrap.application.app`.
- **Writing tests.** Tests are async. They create users with `UserFactory`, query with the ORM directly, and reset through `DatabaseTruncation`.
- **pytest config.** The example sets:
  - `asyncio_default_fixture_loop_scope = "session"`;
  - `python_classes = ["Test*", "*Test"]`.
- **Environment.** `.env.testing` points at `databases/testing.sqlite`.
- **Frontend.** It is built (`npm run build`) or served with `npm run dev` before the tests run.

## Validation

`cd example/browser-testing && uv run pytest` passes on Chromium and Firefox. The tests cover:

- signing in;
- registering;
- a rejected password;
- a duplicate email showing "The email has already been taken.";
- logging out (a CSRF-protected POST), then landing on `/login` when visiting `/dashboard`;
- a guest who never signed in being redirected from `/dashboard` to `/login`.
