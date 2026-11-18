"""FastAPI Startkit MCP module.

Provides class-based building blocks for Model Context Protocol (MCP) servers
that can be mounted directly on any FastAPI application.
"""

import warnings

from .argument import Argument
from .exceptions import JsonRpcError, McpExceptionHandler, ValidationExceptionRenderer
from .prompt import Prompt
from .request import MCPRequest
from .resource import Resource
from .response import Response
from .server import Server
from .tool import Tool
from .providers.mcp_provider import McpProvider

__all__ = [
    "Argument",
    "JsonRpcError",
    "MCPRequest",
    "McpExceptionHandler",
    "McpProvider",
    "Prompt",
    "Resource",
    "Response",
    "Server",
    "Tool",
    "ValidationExceptionRenderer",
]


def __getattr__(name: str):
    if name == "JsonRpcRequest":
        warnings.warn("JsonRpcRequest is deprecated; use MCPRequest instead", DeprecationWarning, stacklevel=2)
        return MCPRequest
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
