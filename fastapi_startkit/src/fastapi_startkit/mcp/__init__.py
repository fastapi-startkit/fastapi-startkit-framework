"""FastAPI Startkit MCP module.

Provides class-based building blocks for Model Context Protocol (MCP) servers
that can be mounted directly on any FastAPI application.
"""

from .argument import Argument
from .prompt import Prompt
from .request import JsonRpcRequest
from .resource import Resource
from .response import Response
from .server import Server
from .tool import Tool

__all__ = [
    "Argument",
    "JsonRpcRequest",
    "Prompt",
    "Resource",
    "Response",
    "Server",
    "Tool",
]
