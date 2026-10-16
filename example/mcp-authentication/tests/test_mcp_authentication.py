import time

import jwt
from fastapi_startkit.fastapi.testing import HttpTestCase, TestResponse
from fastapi_startkit.masoniteorm.testing import RefreshDatabase

from config.auth import OAuthConfig
from config.mcp import McpConfig


class TestMcpAuthentication(HttpTestCase, RefreshDatabase):
    def get_application(self):
        from bootstrap.application import app

        return app

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.config = McpConfig()

    async def issue_token(self, scopes: str, resource: str | None = None) -> str:
        manager = self.get_application().make("auth_manager")
        client, secret = await manager.client_repository.register(
            name="tests",
            redirect_uris=[],
            confidential=True,
            grant_types=["client_credentials"],
            scopes=scopes.split(),
        )
        data = {"grant_type": "client_credentials", "scope": scopes}
        if resource is not None:
            data["resource"] = resource
        response = await self.post("/oauth/token", data=data, auth=(client.id, secret))
        return response.assert_ok().json()["access_token"]

    def sign_token(self, **claims) -> str:
        now = int(time.time())
        payload = {
            "sub": None,
            "aud": self.config.resource,
            "iss": self.config.app_url,
            "iat": now,
            "exp": now + 60,
        }
        return jwt.encode(payload | claims, OAuthConfig().key, algorithm="HS256")

    async def rpc(
        self, method: str, params: dict | None = None, token: str | None = None
    ) -> TestResponse:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return await self.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
            headers=headers,
        )

    async def test_request_without_token_is_challenged(self):
        response = await self.rpc("tools/list")

        response.assert_status(401)
        assert response.headers["www-authenticate"] == (
            f'Bearer resource_metadata="{self.config.resource_metadata_url}"'
        )

    async def test_protected_resource_metadata_names_the_authorization_server(self):
        for path in (
            "/.well-known/oauth-protected-resource",
            "/.well-known/oauth-protected-resource/mcp",
        ):
            response = await self.get(path)

            response.assert_ok().assert_json(
                exact={
                    "resource": self.config.resource,
                    "authorization_servers": [self.config.app_url],
                    "scopes_supported": ["notes:read", "notes:write"],
                    "bearer_methods_supported": ["header"],
                }
            )

    async def test_valid_token_can_list_and_call_tools(self):
        token = await self.issue_token("notes:read notes:write", self.config.resource)

        initialized = await self.rpc("initialize", token=token)
        listed = await self.rpc("tools/list", token=token)
        added = await self.rpc(
            "tools/call", {"name": "add_note", "arguments": {"text": "Buy milk"}}, token
        )
        read = await self.rpc(
            "tools/call", {"name": "list_notes", "arguments": {}}, token
        )

        initialized.assert_ok().assert_json(
            lambda json: json.where("result.serverInfo.name", "notes").etc()
        )
        listed.assert_ok().assert_json(
            lambda json: (
                json.where("result.tools.0.name", "list_notes")
                .where("result.tools.1.name", "add_note")
                .count("result.tools", 2)
                .etc()
            )
        )
        added.assert_ok().assert_json(
            lambda json: json.where(
                "result.content.0.text", lambda text: text.startswith("Saved note #")
            ).etc()
        )
        read.assert_ok().assert_contents("Buy milk")

    async def test_token_without_the_tool_scope_is_forbidden(self):
        token = await self.issue_token("notes:read", self.config.resource)

        response = await self.rpc(
            "tools/call", {"name": "add_note", "arguments": {"text": "Nope"}}, token
        )

        response.assert_status(403).assert_json(
            lambda json: json.where("error", "insufficient_scope").etc()
        )
        assert response.headers["www-authenticate"] == (
            f'Bearer resource_metadata="{self.config.resource_metadata_url}", '
            'error="insufficient_scope", scope="notes:write"'
        )

    async def test_malformed_token_is_rejected(self):
        response = await self.rpc("tools/list", token="not-a-token")

        response.assert_status(401)
        assert 'error="invalid_token"' in response.headers["www-authenticate"]

    async def test_expired_token_is_rejected(self):
        now = int(time.time())
        token = self.sign_token(iat=now - 120, exp=now - 60)

        response = await self.rpc("tools/list", token=token)

        response.assert_status(401).assert_json(
            lambda json: json.where("error_description", "Signature has expired").etc()
        )

    async def test_token_without_resource_is_rejected(self):
        token = await self.issue_token("notes:read")

        response = await self.rpc("tools/list", token=token)

        response.assert_status(401)
        assert 'error="invalid_token"' in response.headers["www-authenticate"]

    async def test_token_for_another_resource_is_rejected(self):
        token = self.sign_token(aud=f"{self.config.app_url}/reports")

        response = await self.rpc("tools/list", token=token)

        response.assert_status(401).assert_json(
            lambda json: json.where("error_description", "Audience doesn't match").etc()
        )

    async def test_body_that_is_not_json_is_a_parse_error(self):
        token = await self.issue_token("notes:read", self.config.resource)

        response = await self.post(
            "/mcp",
            content="{not json",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )

        response.assert_status(400).assert_json(
            exact={
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            }
        )

    async def test_batch_request_is_an_invalid_request(self):
        token = await self.issue_token("notes:read", self.config.resource)

        response = await self.post(
            "/mcp",
            json=[{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}],
            headers={"Authorization": f"Bearer {token}"},
        )

        response.assert_status(400).assert_json(
            exact={
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32600, "message": "Invalid Request"},
            }
        )
