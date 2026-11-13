import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest import IsolatedAsyncioTestCase, mock
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from fastapi import FastAPI, Request
from starlette.middleware.sessions import SessionMiddleware

from fastapi_startkit.application import Application
from fastapi_startkit.configuration import config
from fastapi_startkit.facades import Socialite
from fastapi_startkit.socialite import (
    AuthorizationDeniedException,
    DriverMissingConfigurationException,
    GoogleProvider,
    GoogleServiceConfig,
    InvalidStateException,
    Provider,
    ProviderRequestException,
    SocialiteException,
    SocialiteManager,
    SocialiteProvider,
    SocialiteUser,
)

ENV = ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI")

GOOGLE = {"client_id": "client-id", "client_secret": "client-secret", "redirect": "https://app.test/callback"}

PROFILE = {
    "sub": "1234567890",
    "name": "Jane Doe",
    "email": "jane@example.com",
    "picture": "https://lh3.googleusercontent.com/jane.png",
    "email_verified": True,
}


class GoogleApi:
    def __init__(self, token_response: dict[str, Any] | None = None):
        self.requests: list[httpx.Request] = []
        self.token_response = token_response or {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "expires_in": 3599,
            "scope": "openid https://www.googleapis.com/auth/userinfo.email",
            "token_type": "Bearer",
        }

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path == "/oauth2/v4/token":
            return httpx.Response(200, json=self.token_response)
        if request.url.path == "/oauth2/v3/userinfo":
            if request.headers["Authorization"] != "Bearer access-token":
                return httpx.Response(401, json={"error": "invalid_token"})
            return httpx.Response(200, json=PROFILE)
        return httpx.Response(404)

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self)


def make_request(query: dict[str, str] | None = None, session: dict[str, Any] | None = None) -> Request:
    scope: dict[str, Any] = {
        "type": "http",
        "method": "GET",
        "path": "/callback",
        "headers": [],
        "query_string": urlencode(query or {}).encode(),
    }
    if session is not None:
        scope["session"] = session
    return Request(scope)


def query_of(location: str) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(urlparse(location).query).items()}


class TestGoogleProvider(IsolatedAsyncioTestCase):
    def setUp(self):
        self.api = GoogleApi()
        self.manager = SocialiteManager({"google": GOOGLE}, transport=self.api.transport)

    def test_maps_raw_profile_to_user(self):
        user = GoogleProvider("id", "secret", "https://app.test/callback").map_user_to_object(PROFILE)

        self.assertEqual(
            user,
            SocialiteUser(
                id="1234567890",
                nickname=None,
                name="Jane Doe",
                email="jane@example.com",
                avatar="https://lh3.googleusercontent.com/jane.png",
                raw=PROFILE,
            ),
        )

    def test_redirect_stores_state_and_builds_consent_url(self):
        session: dict[str, Any] = {}

        response = self.manager.driver("google").redirect(make_request(session=session))

        self.assertEqual(response.status_code, 307)
        location = response.headers["location"]
        self.assertTrue(location.startswith("https://accounts.google.com/o/oauth2/auth?"))
        self.assertEqual(
            query_of(location),
            {
                "client_id": "client-id",
                "redirect_uri": "https://app.test/callback",
                "scope": "openid profile email",
                "response_type": "code",
                "state": session["state"],
            },
        )
        self.assertGreaterEqual(len(session["state"]), 32)

    def test_scopes_parameters_and_redirect_url(self):
        driver = (
            self.manager.driver("google")
            .scopes("email", "https://www.googleapis.com/auth/calendar.readonly")
            .with_({"access_type": "offline", "prompt": "consent"})
            .redirect_url("https://app.test/other")
            .stateless()
        )

        query = query_of(driver.redirect().headers["location"])

        self.assertEqual(query["scope"], "openid profile email https://www.googleapis.com/auth/calendar.readonly")
        self.assertEqual(query["access_type"], "offline")
        self.assertEqual(query["prompt"], "consent")
        self.assertEqual(query["redirect_uri"], "https://app.test/other")
        self.assertNotIn("state", query)
        self.assertTrue(driver.is_stateless())

    def test_set_scopes_replaces_defaults(self):
        driver = self.manager.driver("google").set_scopes("openid", "openid")

        self.assertEqual(driver.get_scopes(), ["openid"])

    def test_each_driver_call_is_a_fresh_provider(self):
        self.manager.driver("google").scopes("extra").stateless()

        driver = self.manager.driver("google")

        self.assertEqual(driver.get_scopes(), ["openid", "profile", "email"])
        self.assertFalse(driver.is_stateless())

    def test_stateful_redirect_without_session_fails(self):
        with self.assertRaisesRegex(SocialiteException, "SessionMiddleware or call stateless"):
            self.manager.driver("google").redirect(make_request())

        with self.assertRaises(SocialiteException):
            self.manager.driver("google").redirect()

    async def test_user_exchanges_code_and_fetches_profile(self):
        session = {"state": "abc"}

        user = await self.manager.driver("google").user(make_request({"code": "the-code", "state": "abc"}, session))

        self.assertEqual(user.id, "1234567890")
        self.assertEqual(user.email, "jane@example.com")
        self.assertEqual(user.token, "access-token")
        self.assertEqual(user.refresh_token, "refresh-token")
        self.assertEqual(user.expires_in, 3599)
        self.assertEqual(user.approved_scopes, ["openid", "https://www.googleapis.com/auth/userinfo.email"])
        self.assertEqual(user.raw, PROFILE)
        self.assertNotIn("state", session)

        token_request = self.api.requests[0]
        self.assertEqual(str(token_request.url), "https://www.googleapis.com/oauth2/v4/token")
        self.assertEqual(token_request.method, "POST")
        self.assertEqual(
            dict(httpx.QueryParams(token_request.content.decode())),
            {
                "grant_type": "authorization_code",
                "client_id": "client-id",
                "client_secret": "client-secret",
                "code": "the-code",
                "redirect_uri": "https://app.test/callback",
            },
        )

    async def test_missing_state_raises(self):
        with self.assertRaises(InvalidStateException):
            await self.manager.driver("google").user(make_request({"code": "c"}, {"state": "abc"}))

        with self.assertRaises(InvalidStateException):
            await self.manager.driver("google").user(make_request({"code": "c", "state": "abc"}, {}))

        self.assertEqual(self.api.requests, [])

    async def test_wrong_state_raises_and_is_consumed(self):
        session = {"state": "abc"}

        with self.assertRaises(InvalidStateException):
            await self.manager.driver("google").user(make_request({"code": "c", "state": "xyz"}, session))

        self.assertNotIn("state", session)

    async def test_non_ascii_state_raises_invalid_state(self):
        with self.assertRaises(InvalidStateException):
            await self.manager.driver("google").user(make_request({"code": "c", "state": "é"}, {"state": "abc"}))

        self.assertEqual(self.api.requests, [])

    async def test_stateless_skips_state_check(self):
        user = await self.manager.driver("google").stateless().user(make_request({"code": "c"}))

        self.assertEqual(user.id, "1234567890")

    async def test_list_scope_and_missing_optional_token_fields(self):
        self.api.token_response = {"access_token": "access-token", "scope": ["openid", "email"]}

        user = await self.manager.driver("google").stateless().user(make_request({"code": "c"}))

        self.assertEqual(user.approved_scopes, ["openid", "email"])
        self.assertIsNone(user.refresh_token)
        self.assertIsNone(user.expires_in)

    async def test_user_from_token(self):
        user = await self.manager.driver("google").user_from_token("access-token")

        self.assertEqual(user.name, "Jane Doe")
        self.assertEqual(user.token, "access-token")
        self.assertEqual(user.approved_scopes, [])
        self.assertEqual(self.api.requests[0].headers["Authorization"], "Bearer access-token")

    async def test_rejected_userinfo_raises_provider_request_exception(self):
        with self.assertRaises(ProviderRequestException) as raised:
            await self.manager.driver("google").user_from_token("expired")

        self.assertEqual(raised.exception.status_code, 401)
        self.assertIsInstance(raised.exception.__cause__, httpx.HTTPStatusError)
        self.assertIn("/oauth2/v3/userinfo", str(raised.exception))

    async def test_rejected_token_exchange_raises_provider_request_exception(self):
        manager = SocialiteManager(
            {"google": GOOGLE},
            transport=httpx.MockTransport(lambda request: httpx.Response(400, json={"error": "invalid_grant"})),
        )

        with self.assertRaises(ProviderRequestException) as raised:
            await manager.driver("google").stateless().user(make_request({"code": "used"}))

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIsInstance(raised.exception.__cause__, httpx.HTTPStatusError)

    async def test_transport_failure_raises_provider_request_exception(self):
        def fail(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        manager = SocialiteManager({"google": GOOGLE}, transport=httpx.MockTransport(fail))

        with self.assertRaises(ProviderRequestException) as raised:
            await manager.driver("google").user_from_token("token")

        self.assertIsNone(raised.exception.status_code)
        self.assertIsInstance(raised.exception.__cause__, httpx.ConnectError)

    async def test_non_json_response_raises_provider_request_exception(self):
        manager = SocialiteManager(
            {"google": GOOGLE}, transport=httpx.MockTransport(lambda request: httpx.Response(200, text="<html>"))
        )

        with self.assertRaisesRegex(ProviderRequestException, "not valid JSON"):
            await manager.driver("google").user_from_token("token")

    async def test_denied_consent_raises_without_token_request(self):
        session = {"state": "abc"}
        request = make_request(
            {"error": "access_denied", "error_description": "The user denied access", "state": "abc"}, session
        )

        with self.assertRaises(AuthorizationDeniedException) as raised:
            await self.manager.driver("google").user(request)

        self.assertIsInstance(raised.exception, SocialiteException)
        self.assertEqual(raised.exception.error, "access_denied")
        self.assertEqual(raised.exception.error_description, "The user denied access")
        self.assertIn("access_denied", str(raised.exception))
        self.assertEqual(self.api.requests, [])

    async def test_denied_consent_without_description(self):
        with self.assertRaises(AuthorizationDeniedException) as raised:
            await self.manager.driver("google").stateless().user(make_request({"error": "access_denied"}))

        self.assertIsNone(raised.exception.error_description)
        self.assertEqual(str(raised.exception), "OAuth authorization failed: access_denied")

    async def test_missing_code_raises_without_token_request(self):
        with self.assertRaises(AuthorizationDeniedException) as raised:
            await self.manager.driver("google").stateless().user(make_request())

        self.assertEqual(raised.exception.error, "missing_code")
        self.assertEqual(self.api.requests, [])

    def test_scope_is_omitted_without_scopes(self):
        query = query_of(self.manager.driver("google").set_scopes().stateless().redirect().headers["location"])

        self.assertNotIn("scope", query)
        self.assertEqual(query["response_type"], "code")


class GitLabProvider(Provider):
    scope_separator = " "
    default_scopes = ("read_user",)

    def get_auth_url(self) -> str:
        return "https://gitlab.test/oauth/authorize"

    def get_token_url(self) -> str:
        return "https://gitlab.test/oauth/token"

    async def get_user_by_token(self, token: str) -> dict[str, Any]:
        return {"id": 7, "username": "jane", "token": token}

    def map_user_to_object(self, user: dict[str, Any]) -> SocialiteUser:
        return SocialiteUser(id=str(user["id"]), nickname=user["username"], raw=user)


class TestSocialiteManager(IsolatedAsyncioTestCase):
    def test_unknown_driver(self):
        with self.assertRaisesRegex(SocialiteException, r"Socialite driver \[github\] is not supported"):
            SocialiteManager({}).driver("github")

    def test_missing_configuration_names_keys_and_env(self):
        manager = SocialiteManager({"google": {"client_id": "id", "client_secret": None}})

        with self.assertRaisesRegex(
            DriverMissingConfigurationException,
            r"\[google\]: client_secret \(GOOGLE_CLIENT_SECRET\), redirect \(GOOGLE_REDIRECT_URI\)",
        ):
            manager.driver("google")

    def test_missing_service_block(self):
        with self.assertRaises(DriverMissingConfigurationException):
            SocialiteManager({}).driver("google")

    async def test_extend_with_build_provider(self):
        manager = SocialiteManager({"gitlab": GOOGLE})
        returned = manager.extend("gitlab", lambda config: manager.build_provider(GitLabProvider, config, "gitlab"))

        driver = manager.driver("gitlab")
        user = await driver.user_from_token("t")

        self.assertIs(returned, manager)
        self.assertIsInstance(driver, GitLabProvider)
        self.assertEqual(query_of(driver.stateless().redirect().headers["location"])["scope"], "read_user")
        self.assertEqual((user.id, user.nickname, user.token), ("7", "jane", "t"))

    def test_build_provider_error_uses_class_name_without_driver_name(self):
        with self.assertRaisesRegex(DriverMissingConfigurationException, r"\[GitLabProvider\]"):
            SocialiteManager({}).build_provider(GitLabProvider, {})

    def test_extend_overrides_google(self):
        manager = SocialiteManager({})
        manager.extend("google", lambda config: GitLabProvider("a", "b", "c"))

        self.assertIsInstance(manager.driver("google"), GitLabProvider)


@dataclass
class FakeServicesConfig:
    google: dict = field(default_factory=lambda: dict(GOOGLE))


class TestSocialiteProvider(IsolatedAsyncioTestCase):
    def setUp(self):
        self.enterContext(mock.patch.dict(os.environ))
        for name in ENV:
            os.environ.pop(name, None)
        self.base_path = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def make_app(self, provider: Any = SocialiteProvider) -> Application:
        return Application(base_path=self.base_path, providers=[provider])

    def test_reads_google_env(self):
        os.environ.update(
            {
                "GOOGLE_CLIENT_ID": "env-id",
                "GOOGLE_CLIENT_SECRET": "env-secret",
                "GOOGLE_REDIRECT_URI": "https://env.test/callback",
            }
        )

        app = self.make_app()

        self.assertIsInstance(app.make("socialite"), SocialiteManager)
        self.assertEqual(config("services.google.client_id"), "env-id")
        self.assertEqual(GoogleServiceConfig().redirect, "https://env.test/callback")
        driver = Socialite.driver("google")
        self.assertEqual((driver.client_id, driver.redirect_uri), ("env-id", "https://env.test/callback"))

    def test_missing_env_gives_clear_error(self):
        self.make_app()

        self.assertIsNone(config("services.google.client_id"))
        with self.assertRaisesRegex(DriverMissingConfigurationException, "GOOGLE_CLIENT_ID"):
            Socialite.driver("google")

    def test_publishes_services_config(self):
        app = self.make_app()

        published = app.published_resources["services"]
        self.assertEqual(list(published.values()), ["config/services.py"])

    async def test_end_to_end_login_through_fastapi_sessions(self):
        app = self.make_app((SocialiteProvider, FakeServicesConfig))
        app.make("socialite").transport = GoogleApi().transport

        web = FastAPI()
        web.add_middleware(SessionMiddleware, secret_key="secret")

        @web.get("/auth/redirect")
        async def redirect(request: Request):
            return Socialite.driver("google").redirect(request)

        @web.get("/auth/callback")
        async def callback(request: Request):
            user = await Socialite.driver("google").user(request)
            return {"id": user.id, "email": user.email}

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=web), base_url="https://app.test") as client:
            await client.get("/auth/redirect")
            with self.assertRaises(InvalidStateException):
                await client.get("/auth/callback", params={"code": "c", "state": "forged"})

            redirect_response = await client.get("/auth/redirect")
            state = query_of(redirect_response.headers["location"])["state"]
            callback_response = await client.get("/auth/callback", params={"code": "c", "state": state})

        self.assertEqual(callback_response.json(), {"id": "1234567890", "email": "jane@example.com"})
