import time

import jwt
from fastapi_startkit.fastapi.testing import HttpTestCase
from fastapi_startkit.masoniteorm.migrations import Migrator
from fastapi_startkit.masoniteorm.models import Model

from config.mcp import McpConfig


class TestMcpAuthentication(HttpTestCase):
    migrated = False

    def get_application(self):
        from bootstrap.application import app

        return app

    async def asyncSetUp(self):
        for connection in list(Model.db_manager.connections.values()):
            await connection.engine.dispose()
        Model.db_manager.connections.clear()
        await super().asyncSetUp()
        if not TestMcpAuthentication.migrated:
            await Migrator(migration_directory="databases/migrations").fresh(
                ignore_fk=True
            )
            TestMcpAuthentication.migrated = True
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
        response = await self.client.post(
            "/oauth/token", data=data, auth=(client.id, secret)
        )
        assert response.status_code == 200, response.text
        return response.json()["access_token"]

    def sign_token(self, **claims) -> str:
        now = int(time.time())
        payload = {
            "sub": None,
            "aud": self.config.resource,
            "iss": self.config.app_url,
            "iat": now,
            "exp": now + 60,
        }
        return jwt.encode(payload | claims, self.config.oauth2_key, algorithm="HS256")

    async def rpc(
        self, method: str, params: dict | None = None, token: str | None = None
    ):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return await self.client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
            headers=headers,
        )

    async def test_request_without_token_is_challenged(self):
        response = await self.rpc("tools/list")

        assert response.status_code == 401
        assert response.headers["www-authenticate"] == (
            f'Bearer resource_metadata="{self.config.resource_metadata_url}"'
        )

    async def test_protected_resource_metadata_names_the_authorization_server(self):
        for path in (
            "/.well-known/oauth-protected-resource",
            "/.well-known/oauth-protected-resource/mcp",
        ):
            response = await self.client.get(path)

            assert response.status_code == 200
            assert response.json() == {
                "resource": self.config.resource,
                "authorization_servers": [self.config.app_url],
                "scopes_supported": ["notes:read", "notes:write"],
                "bearer_methods_supported": ["header"],
            }

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

        assert initialized.json()["result"]["serverInfo"]["name"] == "notes"
        assert [tool["name"] for tool in listed.json()["result"]["tools"]] == [
            "list_notes",
            "add_note",
        ]
        assert added.json()["result"]["content"][0]["text"].startswith("Saved note #")
        assert "Buy milk" in read.json()["result"]["content"][0]["resource"]["text"]

    async def test_token_without_the_tool_scope_is_forbidden(self):
        token = await self.issue_token("notes:read", self.config.resource)

        response = await self.rpc(
            "tools/call", {"name": "add_note", "arguments": {"text": "Nope"}}, token
        )

        assert response.status_code == 403
        assert response.json()["error"] == "insufficient_scope"
        assert response.headers["www-authenticate"] == (
            f'Bearer resource_metadata="{self.config.resource_metadata_url}", '
            'error="insufficient_scope", scope="notes:write"'
        )

    async def test_malformed_token_is_rejected(self):
        response = await self.rpc("tools/list", token="not-a-token")

        assert response.status_code == 401
        assert 'error="invalid_token"' in response.headers["www-authenticate"]

    async def test_expired_token_is_rejected(self):
        now = int(time.time())
        token = self.sign_token(iat=now - 120, exp=now - 60)

        response = await self.rpc("tools/list", token=token)

        assert response.status_code == 401
        assert response.json()["error_description"] == "Signature has expired"

    async def test_token_without_resource_is_rejected(self):
        token = await self.issue_token("notes:read")

        response = await self.rpc("tools/list", token=token)

        assert response.status_code == 401
        assert 'error="invalid_token"' in response.headers["www-authenticate"]

    async def test_token_for_another_resource_is_rejected(self):
        token = self.sign_token(aud=f"{self.config.app_url}/reports")

        response = await self.rpc("tools/list", token=token)

        assert response.status_code == 401
        assert response.json()["error_description"] == "Audience doesn't match"

    async def test_body_that_is_not_json_is_a_parse_error(self):
        token = await self.issue_token("notes:read", self.config.resource)

        response = await self.client.post(
            "/mcp",
            content="{not json",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )

        assert response.status_code == 400
        assert response.json() == {
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32700, "message": "Parse error"},
        }

    async def test_batch_request_is_an_invalid_request(self):
        token = await self.issue_token("notes:read", self.config.resource)

        response = await self.client.post(
            "/mcp",
            json=[{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}],
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400
        assert response.json() == {
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32600, "message": "Invalid Request"},
        }
