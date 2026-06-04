"""JSON-RPC 2.0 dispatcher for MCP Streamable HTTP transport."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .server import Server
    from .tool import Tool
    from .prompt import Prompt
    from .resource import Resource

PROTOCOL_VERSION = "2024-11-05"


class Protocol:
    """Dispatches JSON-RPC 2.0 method calls to the appropriate MCP handler."""

    def __init__(self, server: Server):
        self.server = server
        self._tools: dict = {}
        self._prompts: dict = {}
        self._resources: dict = {}

        self._methods = {
            "initialize": self._initialize,
            "tools/list": self._tools_list,
            "tools/call": self._tools_call,
            "prompts/list": self._prompts_list,
            "prompts/get": self._prompts_get,
            "resources/list": self._resources_list,
            "resources/read": self._resources_read,
        }

    # ── builder ──────────────────────────────────────────────────────────

    def tools(self, tools: list[Tool]) -> Protocol:
        """Register tool instances; returns ``self`` for chaining."""
        self._tools.update((t.name, t) for t in tools)
        return self

    def prompts(self, prompts: list[Prompt]) -> Protocol:
        """Register prompt instances; returns ``self`` for chaining."""
        self._prompts.update((p.name, p) for p in prompts)
        return self

    def resources(self, resources: list[Resource]) -> Protocol:
        """Register resource instances; returns ``self`` for chaining."""
        self._resources.update((r.uri, r) for r in resources)
        return self

    # ── JSON-RPC helpers ─────────────────────────────────────────────────

    @staticmethod
    def ok(rpc_id, result: dict) -> dict:
        return {"jsonrpc": "2.0", "id": rpc_id, "result": result}

    @staticmethod
    def err(rpc_id, code: int, message: str) -> dict:
        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "error": {"code": code, "message": message},
        }

    # ── method handlers ──────────────────────────────────────────────────

    async def _initialize(self, rpc_id, params: dict, **ctx) -> dict:
        return self.ok(rpc_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "serverInfo": {
                "name": self.server.name or "mcp-server",
                "version": "1.0.0",
            },
            "capabilities": self.server.capabilities(),
        })

    async def _tools_list(self, rpc_id, params: dict, **ctx) -> dict:
        tools = [t.to_json() for t in self._tools.values()]
        return self.ok(rpc_id, {"tools": tools})

    async def _tools_call(self, rpc_id, params: dict, **ctx) -> dict:
        name = params.get("name", "")
        arguments = params.get("arguments") or {}

        tool = self._tools.get(name)
        if not tool:
            return self.err(rpc_id, -32601, f"Unknown tool: {name}")

        try:
            response = await tool.handle(arguments)
            return self.ok(rpc_id, {"content": response.to_content()})
        except Exception as exc:
            return self.ok(rpc_id, {
                "content": [{"type": "text", "text": f"Error: {exc}"}],
            })

    async def _prompts_list(self, rpc_id, params: dict, **ctx) -> dict:
        prompts = [p.to_json() for p in self._prompts.values()]
        return self.ok(rpc_id, {"prompts": prompts})

    async def _prompts_get(self, rpc_id, params: dict, **ctx) -> dict:
        name = params.get("name", "")
        arguments = params.get("arguments") or {}

        prompt = self._prompts.get(name)
        if not prompt:
            return self.err(rpc_id, -32601, f"Unknown prompt: {name}")

        try:
            response = await prompt.handle(arguments)
            return self.ok(rpc_id, {
                "description": prompt.description,
                "messages": [
                    {
                        "role": "user",
                        "content": response.to_content(),
                    }
                ],
            })
        except Exception as exc:
            return self.ok(rpc_id, {
                "messages": [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": f"Error: {exc}"}],
                    }
                ],
            })

    async def _resources_list(self, rpc_id, params: dict, **ctx) -> dict:
        resources = [r.to_json() for r in self._resources.values()]
        return self.ok(rpc_id, {"resources": resources})

    async def _resources_read(self, rpc_id, params: dict, **ctx) -> dict:
        uri = params.get("uri", "")

        resource = self._resources.get(uri)
        if not resource:
            return self.err(rpc_id, -32602, f"Unknown resource URI: {uri}")

        try:
            text = await resource.read(**ctx)
            return self.ok(rpc_id, {
                "contents": [
                    {
                        "uri": resource.uri,
                        "mimeType": resource.mime_type,
                        "text": text,
                    }
                ],
            })
        except Exception as exc:
            return self.err(rpc_id, -32603, f"Error reading resource: {exc}")

    # ── dispatcher ───────────────────────────────────────────────────────

    async def dispatch(self, method: str, rpc_id, params: dict, **context) -> dict:
        """Route a JSON-RPC method to the appropriate handler."""
        fn = self._methods.get(method)
        if not fn:
            return self.err(rpc_id, -32601, f"Method not found: {method}")
        return await fn(rpc_id, params, **context)
