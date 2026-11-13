import secrets
from abc import ABC, abstractmethod
from typing import Any, Self
from urllib.parse import urlencode

import httpx
from starlette.requests import Request
from starlette.responses import RedirectResponse

from ..exceptions import (
    AuthorizationDeniedException,
    InvalidStateException,
    ProviderRequestException,
    SocialiteException,
)
from ..user import SocialiteUser


class Provider(ABC):
    default_scopes: tuple[str, ...] = ()
    scope_separator: str = ","
    state_session_key: str = "state"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_url: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_url
        self.transport = transport
        self._scopes: list[str] = list(self.default_scopes)
        self._parameters: dict[str, str] = {}
        self._stateless = False

    @abstractmethod
    def get_auth_url(self) -> str: ...

    @abstractmethod
    def get_token_url(self) -> str: ...

    @abstractmethod
    async def get_user_by_token(self, token: str) -> dict[str, Any]: ...

    @abstractmethod
    def map_user_to_object(self, user: dict[str, Any]) -> SocialiteUser: ...

    def scopes(self, *scopes: str) -> Self:
        self._scopes = list(dict.fromkeys([*self._scopes, *scopes]))
        return self

    def set_scopes(self, *scopes: str) -> Self:
        self._scopes = list(dict.fromkeys(scopes))
        return self

    def get_scopes(self) -> list[str]:
        return list(self._scopes)

    def with_(self, parameters: dict[str, str]) -> Self:
        self._parameters = {**self._parameters, **parameters}
        return self

    def redirect_url(self, url: str) -> Self:
        self.redirect_uri = url
        return self

    def stateless(self) -> Self:
        self._stateless = True
        return self

    def is_stateless(self) -> bool:
        return self._stateless

    def redirect(self, request: Request | None = None) -> RedirectResponse:
        state = None
        if not self._stateless:
            state = secrets.token_urlsafe(32)
            self._session(request)[self.state_session_key] = state
        return RedirectResponse(self.build_auth_url(state))

    def build_auth_url(self, state: str | None = None) -> str:
        return f"{self.get_auth_url()}?{urlencode(self.get_code_fields(state))}"

    def get_code_fields(self, state: str | None = None) -> dict[str, str]:
        fields = {"client_id": self.client_id, "redirect_uri": self.redirect_uri}
        if self._scopes:
            fields["scope"] = self.scope_separator.join(self._scopes)
        fields["response_type"] = "code"
        if state is not None:
            fields["state"] = state
        return {**fields, **self._parameters}

    async def user(self, request: Request) -> SocialiteUser:
        if not self._stateless:
            self._validate_state(request)

        response = await self.get_access_token_response(self._authorization_code(request))
        user = await self.user_from_token(response["access_token"])
        user.refresh_token = response.get("refresh_token")
        user.expires_in = response.get("expires_in")
        user.approved_scopes = self.parse_approved_scopes(response)
        return user

    async def user_from_token(self, token: str) -> SocialiteUser:
        user = self.map_user_to_object(await self.get_user_by_token(token))
        user.token = token
        return user

    async def get_access_token_response(self, code: str) -> dict[str, Any]:
        return await self.request_json(
            "POST", self.get_token_url(), data=self.get_token_fields(code), headers={"Accept": "application/json"}
        )

    async def request_json(self, method: str, url: str, **options: Any) -> dict[str, Any]:
        try:
            async with self.http_client() as client:
                response = await client.request(method, url, **options)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as error:
            raise ProviderRequestException(
                f"OAuth request to {url} failed with status {error.response.status_code}.",
                error.response.status_code,
            ) from error
        except httpx.HTTPError as error:
            raise ProviderRequestException(f"OAuth request to {url} failed: {error}") from error
        except ValueError as error:
            raise ProviderRequestException(f"OAuth response from {url} is not valid JSON.") from error

    def get_token_fields(self, code: str) -> dict[str, str]:
        return {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
        }

    def parse_approved_scopes(self, response: dict[str, Any]) -> list[str]:
        scope = response.get("scope")
        if isinstance(scope, list):
            return [str(item) for item in scope]
        return str(scope).split(self.scope_separator) if scope else []

    def http_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=self.transport)

    def _authorization_code(self, request: Request) -> str:
        error = request.query_params.get("error")
        if error:
            raise AuthorizationDeniedException(error, request.query_params.get("error_description"))
        code = request.query_params.get("code")
        if not code:
            raise AuthorizationDeniedException("missing_code", "The callback has no authorization code.")
        return code

    def _validate_state(self, request: Request) -> None:
        expected = self._session(request).pop(self.state_session_key, None)
        given = request.query_params.get("state")
        if not expected or not given or not secrets.compare_digest(str(expected).encode(), given.encode()):
            raise InvalidStateException("The OAuth state is missing or does not match.")

    def _session(self, request: Request | None) -> dict[str, Any]:
        if request is None or "session" not in request.scope:
            raise SocialiteException(
                "A session is required to keep the OAuth state. Add SessionMiddleware or call stateless()."
            )
        return request.session
