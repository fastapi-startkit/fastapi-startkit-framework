"""Internal JSON-RPC 2.0 dispatcher for MCP."""

from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .server import Server


MCP_PROTOCOL_VERSION = "2024-11-05"


class Protocol:
    """Dispatches JSON-RPC 2.0 method calls to MCP handlers.

    Handles the following methods:
    - initialize
    - tools/list
    - tools/call
    - prompts/list
    - prompts/get
    - resources/list
    - resources/read
    """

    def __init__(self, server: "Server") -> None:
        self._server = server

    # ------------------------------------------------------------------
    # Public dispatch entry point
    # ------------------------------------------------------------------

    async def dispatch(self, method: str, params: Optional[dict], request_id: Any) -> dict:
        """Dispatch a JSON-RPC method and return a full JSON-RPC response dict."""
        handler = {
            "initialize": self._initialize,
            "tools/list": self._tools_list,
            "tools/call": self._tools_call,
            "prompts/list": self._prompts_list,
            "prompts/get": self._prompts_get,
            "resources/list": self._resources_list,
            "resources/read": self._resources_read,
        }.get(method)

        if handler is None:
            return self._error(request_id, -32601, f"Method not found: {method}")

        try:
            result = await handler(params or {})
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except Exception as exc:  # pragma: no cover
            return self._error(request_id, -32000, str(exc))

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    async def _initialize(self, params: dict) -> dict:
        server = self._server
        result: dict = {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "serverInfo": {"name": server.name, "version": "1.0"},
            "capabilities": {
                "tools": {"listChanged": False},
                "prompts": {"listChanged": False},
                "resources": {"listChanged": False},
            },
        }
        if getattr(server, "description", None):
            result["description"] = server.description
        if getattr(server, "instructions", None):
            result["instructions"] = server.instructions
        return result

    async def _tools_list(self, params: dict) -> dict:
        tools = self._server.tools() or []
        return {"tools": [t().to_json() for t in tools]}

    async def _tools_call(self, params: dict) -> dict:
        name = params.get("name")
        arguments = params.get("arguments") or {}
        tools = self._server.tools() or []
        for tool_cls in tools:
            tool = tool_cls()
            if tool.name == name:
                response = await tool.handle(arguments)
                return {"content": response.to_content()}
        return self._error_result(-32602, f"Tool not found: {name}")

    async def _prompts_list(self, params: dict) -> dict:
        prompts = self._server.prompts() or []
        registered = [p().to_json() for p in prompts if p().should_register()]
        return {"prompts": registered}

    async def _prompts_get(self, params: dict) -> dict:
        name = params.get("name")
        arguments = params.get("arguments") or {}
        prompts = self._server.prompts() or []
        for prompt_cls in prompts:
            prompt = prompt_cls()
            if prompt.name == name and prompt.should_register():
                response = await prompt.handle(arguments)
                messages = [
                    {"role": "user", "content": item}
                    for item in response.to_content()
                ]
                return {"messages": messages}
        return self._error_result(-32602, f"Prompt not found: {name}")

    async def _resources_list(self, params: dict) -> dict:
        resources = self._server.resources() or []
        return {"resources": [r().to_json() for r in resources]}

    async def _resources_read(self, params: dict) -> dict:
        uri = params.get("uri")
        resources = self._server.resources() or []
        for resource_cls in resources:
            resource = resource_cls()
            if resource.uri == uri:
                content = await resource.read()
                return {
                    "contents": [
                        {
                            "uri": resource.uri,
                            "mimeType": resource.mime_type,
                            "text": content,
                        }
                    ]
                }
        return self._error_result(-32602, f"Resource not found: {uri}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _error(request_id: Any, code: int, message: str) -> dict:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }

    @staticmethod
    def _error_result(code: int, message: str) -> dict:
        """Return an error payload as a *result* (for tool/prompt/resource not found)."""
        return {"error": {"code": code, "message": message}}
