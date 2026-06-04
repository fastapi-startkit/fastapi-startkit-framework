"""Dev-tools MCP server example.

Demonstrates a practical MCP server with tools, a prompt, and a resource,
built with fastapi-startkit's Application class and FastAPIProvider.

Run with:
    uv run uvicorn app:app --reload
"""

from fastapi_startkit import Application
from fastapi_startkit.fastapi import FastAPIProvider

from mcp.server import DevToolsServer

mcp_server = DevToolsServer()

app = Application(providers=[FastAPIProvider])
app.include_router(mcp_server.router(prefix="/mcp"))


@app.get("/")
async def index():
    return {"message": "Dev-Tools MCP server is running.", "mcp_endpoint": "/mcp"}
