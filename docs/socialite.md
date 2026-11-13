---
title: Socialite
description: Sign users in with Google through OAuth 2.0, Laravel Socialite style.
---

# Socialite

Socialite signs users in with an OAuth 2.0 provider. It builds the consent redirect, checks the `state` value, exchanges the authorization code for a token and returns the user's profile. Google is the built-in driver; other providers are added with `extend()`.

## Installation

```bash
uv add "fastapi-startkit[socialite]"
```

The extra installs FastAPI, `httpx` and `itsdangerous` (used by Starlette's `SessionMiddleware`).

Register the provider:

```python
from fastapi_startkit.socialite import SocialiteProvider

app = Application(base_path=..., providers=[SocialiteProvider])
```

## Configuration

Create an OAuth client in the [Google Cloud console](https://console.cloud.google.com/apis/credentials) and set:

```dotenv
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=https://example.com/auth/google/callback
```

They are read into `services.google`:

```python
from fastapi_startkit.configuration import config

config("services.google.client_id")
```

Publish `config/services.py` to change the defaults, or pass your own config dataclass to the provider: `providers=[(SocialiteProvider, ServicesConfig)]`. A missing value raises `DriverMissingConfigurationException` naming the key and environment variable when the driver is first used.

## Routing

Socialite keeps the `state` value in the session, so add Starlette's `SessionMiddleware`:

```python
from fastapi import FastAPI, Request
from starlette.middleware.sessions import SessionMiddleware

from fastapi_startkit.facades import Socialite

api = FastAPI()
api.add_middleware(SessionMiddleware, secret_key="change-me")


@api.get("/auth/google/redirect")
async def redirect(request: Request):
    return Socialite.driver("google").redirect(request)


@api.get("/auth/google/callback")
async def callback(request: Request):
    google_user = await Socialite.driver("google").user(request)

    user = await User.where("google_id", google_user.id).first()
    if user is None:
        user = await User.create({"google_id": google_user.id, "name": google_user.name, "email": google_user.email})
    ...
```

`redirect()` returns a `RedirectResponse`. `user()` raises `InvalidStateException` when the `state` query parameter is missing or does not match the session.

## The user

`user()` and `user_from_token()` return a `SocialiteUser`:

| Attribute | Google source |
|---|---|
| `id` | `sub` |
| `nickname` | always `None` for Google |
| `name` | `name` |
| `email` | `email` |
| `avatar` | `picture` |
| `raw` | the full profile payload |
| `token` | access token |
| `refresh_token` | refresh token, when Google returns one |
| `expires_in` | token lifetime in seconds |
| `approved_scopes` | scopes granted by the user |

### Retrieving a user from a token

```python
user = await Socialite.driver("google").user_from_token(access_token)
```

## Scopes and parameters

Google requests `openid profile email` by default.

```python
Socialite.driver("google").scopes("https://www.googleapis.com/auth/calendar.readonly").redirect(request)

Socialite.driver("google").set_scopes("openid", "email").redirect(request)
```

`with_()` adds query parameters to the consent URL. Ask for a refresh token with:

```python
Socialite.driver("google").with_({"access_type": "offline", "prompt": "consent"}).redirect(request)
```

`redirect_url(url)` overrides the configured callback URL for one request.

## Stateless authentication

APIs and single-page apps without a session can skip the state check:

```python
Socialite.driver("google").stateless().redirect()
await Socialite.driver("google").stateless().user(request)
```

Without `stateless()`, `redirect()` raises `SocialiteException` when no session is available.

Every `Socialite.driver()` call returns a new provider, so `scopes()`, `with_()` and `stateless()` never leak between requests.

## Custom drivers

Subclass `Provider` and register it with `extend()`. The factory receives the `services.<name>` config dict, and `build_provider()` checks `client_id`, `client_secret` and `redirect`:

```python
from typing import Any

from fastapi_startkit.facades import Socialite
from fastapi_startkit.socialite import Provider, SocialiteUser


class GitLabProvider(Provider):
    default_scopes = ("read_user",)
    scope_separator = " "

    def get_auth_url(self) -> str:
        return "https://gitlab.com/oauth/authorize"

    def get_token_url(self) -> str:
        return "https://gitlab.com/oauth/token"

    async def get_user_by_token(self, token: str) -> dict[str, Any]:
        async with self.http_client() as client:
            response = await client.get("https://gitlab.com/api/v4/user", headers={"Authorization": f"Bearer {token}"})
            response.raise_for_status()
            return response.json()

    def map_user_to_object(self, user: dict[str, Any]) -> SocialiteUser:
        return SocialiteUser(
            id=str(user["id"]),
            nickname=user["username"],
            name=user["name"],
            email=user.get("email"),
            avatar=user.get("avatar_url"),
            raw=user,
        )


Socialite.extend("gitlab", lambda config: Socialite.build_provider(GitLabProvider, config, "gitlab"))
```

Call `extend()` from a provider's `boot()` and add a `gitlab` entry to `services`.

## Testing

Point the manager at an `httpx.MockTransport` to fake Google's token and profile endpoints:

```python
import httpx


def google(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/oauth2/v4/token":
        return httpx.Response(200, json={"access_token": "token", "expires_in": 3599})
    return httpx.Response(200, json={"sub": "1", "name": "Jane", "email": "jane@example.com"})


app.make("socialite").transport = httpx.MockTransport(google)

user = await Socialite.driver("google").user_from_token("token")
```
