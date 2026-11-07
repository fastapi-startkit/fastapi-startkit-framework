# 066. Session authentication and form requests in the browser-testing example

Date: 2026-11-07

## Problem

The `example/browser-testing` app authenticated by writing `user_id` into Starlette's signed session cookie, hashed passwords with a hand-written PBKDF2 helper, and validated registration and login with `if` chains in one `AuthController`. That duplicates what `fastapi-startkit-auth` and `fastapi_startkit.validation` already provide, so the example taught a pattern the documentation (`docs/authentication.md`) tells users not to write.

## Alternatives

1. **Keep the hand-rolled session and checks.** No new dependency, but the example diverges from the documented way and skips CSRF.
2. **`fastapi-startkit-auth` with the in-memory session store.** Less setup, but sessions vanish on restart and the example would not show the `sessions` migration a real app needs.
3. **`fastapi-startkit-auth` with the database session store, `FormRequest` validation, and one controller per flow.**

## Decision

Option 3.

- `config/auth.py` declares `AuthConfig` (guard `web`, a `SessionGuard` over an `async_model` provider for `User`) and `SessionConfig` (`driver="database"`, `secure` from `SESSION_SECURE_COOKIE`, default `True`). `AuthProvider` and `AuthSessionProvider` are listed in `bootstrap/application.py`. The released 0.7.0 names the store option `driver`; the documentation page already says `store`.
- The `sessions` migration from the package is copied into `databases/migrations`, so `DatabaseTruncation` migrates and empties it with the rest.
- Starlette's `SessionMiddleware` stays: Inertia flashes validation errors into `request.session`, which the auth session (an auth record, not a key-value store) does not replace.
- `AuthController` is split into `RegisterController` (`create`, `store`) and `LoginController` (`create`, `store`, `destroy`). Login uses `AsyncAuth.attempt`, registration `AsyncAuth.login`, logout `AsyncAuth.logout`, and the dashboard `AsyncAuth.user()`.
- `RegisterRequest` (`name` required string, `email` required, valid and unique in `users`, `password` at least 8 characters) and `LoginRequest` are `FormRequest`s injected with `Validated[...]`; failures redirect back with Inertia errors through the framework's validation handler.
- Passwords are hashed with the auth manager's bcrypt hasher (`hash_password` in `app/models/user.py`), so the seeder, registration and `attempt` agree.
- CSRF needs no frontend change: Inertia v3 sends the `XSRF-TOKEN` cookie back as `X-XSRF-TOKEN`.

## Validation

The example's browser tests cover signing in with the seeded user, registering, a rejected password, a duplicate email showing "The email has already been taken.", and logging out (a CSRF-protected POST) followed by the dashboard redirecting to `/login`, on Chromium and Firefox with secure cookies over `http://127.0.0.1`.
