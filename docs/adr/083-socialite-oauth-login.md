# 083. Socialite OAuth login with a Google driver

- Date: 2026-11-13
- Status: Accepted

## Problem

Applications that sign users in with Google write the OAuth 2.0 authorization code flow by hand: build the consent URL, keep a `state` value, exchange the code for a token, fetch the profile and map it to their user. Laravel ships this as [Socialite](https://laravel.com/docs/socialite). The framework has no equivalent: no OAuth, no social login and no `Socialite` facade.

The scope is Google only. Other drivers (GitHub, Facebook, ...) must be addable later without changing the core, and applications must be able to register their own drivers.

## Alternatives

- **A Socialite port on `httpx`.** (chosen) A small abstract OAuth 2.0 provider, one `GoogleProvider`, a manager with `extend()` and a facade. `httpx` is already installed with the `fastapi` extra and accepts a transport, so tests fake the token and profile endpoints without a network.
- **Authlib's Starlette integration.** Complete and maintained, but it brings its own registry, OpenID discovery and session layout, and its API is not Socialite's. Wrapping it would hide most of it and still add a dependency.
- **`fastapi-sso`.** Covers many providers but returns its own user model, owns the callback flow and is sync-first in places; it does not fit the manager/facade pattern used by `Mail` and `Cache`.
- **Caching provider instances in the manager, as Laravel does.** Socialite providers are configured fluently (`scopes()`, `stateless()`, `with_()`). In an async server one cached instance is shared by concurrent requests, so one request's scopes would leak into another. A new provider is built on every `driver()` call instead.

## Decision

### API

```python
from fastapi import Request
from fastapi_startkit.facades import Socialite


async def redirect(request: Request):
    return Socialite.driver("google").scopes("https://www.googleapis.com/auth/calendar.readonly").redirect(request)


async def callback(request: Request):
    user = await Socialite.driver("google").user(request)
    user.id, user.name, user.email, user.avatar, user.token, user.refresh_token, user.expires_in
```

- `redirect(request=None)` returns a Starlette `RedirectResponse` to the consent screen with `client_id`, `redirect_uri`, `scope`, `response_type=code` and `state`.
- `user(request)` checks `state`, exchanges `code` for a token, fetches the profile and returns a `SocialiteUser` (`id`, `nickname`, `name`, `email`, `avatar`, `raw`, `token`, `refresh_token`, `expires_in`, `approved_scopes`).
- `user_from_token(token)` fetches the profile for an existing access token.
- `scopes(*scopes)` adds to the defaults, `set_scopes(*scopes)` replaces them, `with_(params)` adds query parameters (for example `{"access_type": "offline", "prompt": "consent"}`), `redirect_url(url)` overrides the configured callback and `stateless()` disables the state check.
- `Socialite.extend("name", factory)` registers a driver; the factory receives the `services.<name>` config dict. `Socialite.build_provider(ProviderClass, config)` builds an OAuth 2.0 provider from a config dict, so a custom driver is one class plus one line.

### State

`redirect()` stores a random `state` in `request.session` (Starlette `SessionMiddleware`) and `user()` pops it and compares it with the `state` query parameter using `secrets.compare_digest`. A missing or different value raises `InvalidStateException`. A stateful `redirect()` without a session raises `SocialiteException` up front, because the callback could never pass. `stateless()` skips both, for APIs and SPAs that keep the state themselves.

### Configuration

`SocialiteProvider` merges `ServicesConfig` under `services`, with `services.google` read from `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` and `GOOGLE_REDIRECT_URI`. Any key missing when `driver("google")` is called raises `DriverMissingConfigurationException` naming the key and the environment variable. An unknown driver raises `SocialiteException`.

### Google

Consent URL `https://accounts.google.com/o/oauth2/auth`, token URL `https://www.googleapis.com/oauth2/v4/token`, profile `https://www.googleapis.com/oauth2/v3/userinfo`; default scopes `openid profile email`, space separated. The profile maps `sub` to `id`, `name`, `email` and `picture` to `avatar`, with `nickname` left empty as Google has none.

### Packaging

New package `fastapi_startkit.socialite` (`manager.py`, `providers/abstract.py`, `providers/google.py`, `user.py`, `exceptions.py`, `config/`, `provider.py`), the `Socialite` facade and `.pyi` stub, and a `socialite` extra that installs `fastapi-startkit[fastapi]` (Starlette, `httpx`, `itsdangerous` for sessions). The manager's `transport` attribute is passed to every built-in provider's `httpx.AsyncClient`, so tests set an `httpx.MockTransport`.

Out of scope: other drivers, OAuth 1.0, PKCE, refreshing tokens and OpenID `id_token` verification.

## Validation

- Unit tests map a raw Google profile to `SocialiteUser`.
- The redirect URL contains `client_id`, `redirect_uri`, the scopes, extra `with_()` parameters and the `state` saved in the session.
- The callback flow runs against `httpx.MockTransport` for the token and profile endpoints, including `approved_scopes` and `user_from_token`.
- Missing or wrong `state` raises `InvalidStateException`; `stateless()` skips it.
- Unknown drivers, missing configuration and stateful redirects without a session raise clear errors; `extend()` and `build_provider()` register a custom driver.
- A FastAPI app with `SessionMiddleware` runs redirect and callback end to end.
- `uv run pytest --ignore=tests/masoniteorm/postgres --cov` stays above the 80% threshold.
